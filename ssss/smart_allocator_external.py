"""
MCX Silver Smart Allocator — External Credentials (No Mock Data)
=================================================================
Paper-first backend allocator that uses real Angel One SmartAPI to:
  - Search futures contracts
  - Fetch FULL quotes (LTP + OHLC + volume/tradeVolume when available)
  - Compute volatility level (ATR% approximation)
  - Compute lot allocation using balance + volatility-based risk bands

Important:
  - No local mock price/volatility data is used.
  - All credentials come from environment variables.
  - **Never places orders** — responses are sizing-only for paper / simulation.
    Live brokerage must stay behind PAPER_TRADE_ENABLED and the trading bot.
"""

import os
import re
import math
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import requests
import pyotp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from SmartApi import SmartConnect

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

API_KEY = os.getenv("ANGEL_ONE_API_KEY")
CLIENT_ID = os.getenv("ANGEL_ONE_CLIENT_ID")
PASSWORD = os.getenv("ANGEL_ONE_PASSWORD")
TOTP_KEY = os.getenv("ANGEL_ONE_TOTP_SECRET")

if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_KEY]):
    log.warning("Missing Angel One credentials in environment (.env). Allocator will fail until set.")

LOT_SIZES = {"SILVER": 30, "SILVERM": 5, "SILVERMIC": 1}
# When margin for the requested family exceeds budget, try smaller lot contracts (sizing only; no orders).
SYMBOL_FALLBACK_CHAIN = {
    "SILVER": ["SILVER", "SILVERM", "SILVERMIC"],
    "SILVERM": ["SILVERM", "SILVERMIC"],
    "SILVERMIC": ["SILVERMIC"],
}
VOLATILITY_THRESHOLDS = {"HIGH": 2.0, "NORMAL": 1.0}
RISK_PCT = {
    "HIGH": (0.30, 0.40),
    "NORMAL": (0.40, 0.50),
    "LOW": (0.60, 0.70),
}


app = FastAPI(
    title="MCX Silver Smart Allocator (External)",
    description="External credentials allocator for MCX Silver futures (no mock pricing).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Session / SmartAPI helpers
# -----------------------------
_session: Dict[str, object] = {}

_angel_api_lock = threading.Lock()
_last_angel_api_mono = 0.0


def _angel_api_min_interval_sec() -> float:
    try:
        return max(0.0, float(os.getenv("ANGEL_API_MIN_INTERVAL_SEC", "0.55") or 0.55))
    except ValueError:
        return 0.55


def angel_api_throttle() -> None:
    """Space out Angel REST / SmartAPI calls to reduce 'exceeding access rate' errors."""
    gap = _angel_api_min_interval_sec()
    if gap <= 0:
        return
    global _last_angel_api_mono
    with _angel_api_lock:
        now = time.monotonic()
        wait = _last_angel_api_mono + gap - now
        if wait > 0:
            time.sleep(wait)
        _last_angel_api_mono = time.monotonic()


def clear_angel_session() -> None:
    """Drop cached SmartConnect session (e.g. after Invalid Token on quote)."""
    _session.clear()


def _normalize_jwt_token(token: Optional[str]) -> str:
    """Strip accidental 'Bearer ' prefix so Authorization is never 'Bearer Bearer …'."""
    if not token:
        return ""
    t = str(token).strip()
    if t.lower().startswith("bearer "):
        return t[7:].strip()
    return t


def _search_scrip_via_rest(exchange: str, searchscrip: str) -> dict:
    """
    Direct REST search (same route as SmartApi). Use when SmartApi.searchScrip raises
    KeyError('status') on malformed JSON bodies or missing 'status' in the payload.
    """
    angel_api_throttle()
    obj, jwt = get_session()
    jwt = _normalize_jwt_token(jwt)
    url = "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/searchScrip"
    headers = dict(obj.requestHeaders())
    headers["Authorization"] = f"Bearer {jwt}"
    headers["Content-Type"] = headers.get("Content-type", "application/json")
    r = requests.post(
        url,
        json={"exchange": exchange, "searchscrip": searchscrip},
        headers=headers,
        timeout=15,
    )
    text = (r.text or "").strip()
    if "access denied" in text.lower() or "exceeding access rate" in text.lower():
        return {"status": False, "message": "Angel rate limit (search)", "data": []}
    if r.status_code != 200:
        return {"status": False, "message": f"Search HTTP {r.status_code}: {text[:280]}", "data": []}
    try:
        data = r.json()
    except ValueError:
        return {"status": False, "message": f"Search non-JSON: {text[:200]}", "data": []}
    if not isinstance(data, dict):
        return {"status": False, "message": f"Search unexpected response type {type(data).__name__}", "data": []}
    if "status" not in data:
        return {
            "status": False,
            "message": "Search response missing 'status' "
            + f"(keys: {list(data.keys())[:14]})",
            "data": data.get("data") if isinstance(data.get("data"), list) else [],
        }
    return data


def angel_search_scrip(obj: SmartConnect, exchange: str, searchscrip: str) -> dict:
    """searchScrip with pacing; REST fallback if SmartApi fails on missing 'status' in body."""
    angel_api_throttle()
    try:
        raw = obj.searchScrip(exchange, searchscrip)
    except KeyError as e:
        if e.args and e.args[0] == "status":
            log.warning("SmartApi searchScrip: missing 'status' in response; using REST search.")
            return _search_scrip_via_rest(exchange, searchscrip)
        raise
    except Exception as e:
        err = str(e).lower()
        if "exceeding access rate" in err or "access denied" in err or "couldn't parse the json" in err:
            if "access denied" in err or "exceeding" in err:
                raise RuntimeError(
                    "Angel One API rate limit exceeded (search). "
                    "Increase ANGEL_API_MIN_INTERVAL_SEC (e.g. 0.8–1.2) or wait before retrying."
                ) from e
        raise
    if not isinstance(raw, dict):
        log.warning("searchScrip returned non-dict (%s); REST search fallback", type(raw).__name__)
        return _search_scrip_via_rest(exchange, searchscrip)
    if "status" not in raw:
        log.warning("searchScrip dict missing 'status'; REST search fallback")
        return _search_scrip_via_rest(exchange, searchscrip)
    return raw


def _quote_api_post(
    mode: str,
    tokens: List[str],
    *,
    invalidate_and_retry: bool = True,
) -> dict:
    """
    Market quote via SmartConnect.getMarketData (same headers/IP/MAC as login).
    Raw requests with 127.0.0.1 often return AG8001 Invalid Token on Angel.
    """
    if not tokens:
        return {"status": True, "data": {"fetched": []}}

    angel_api_throttle()
    obj, _ = get_session()
    str_tokens = [str(t).strip() for t in tokens if str(t).strip()]
    if not str_tokens:
        return {"status": True, "data": {"fetched": []}}

    exchange_tokens = {"MCX": str_tokens}

    try:
        result = obj.getMarketData(mode, exchange_tokens)
    except Exception as e:
        msg = str(e).lower()
        if invalidate_and_retry and ("invalid token" in msg or "ag8001" in msg):
            log.warning("getMarketData error (retry after fresh login): %s", e)
            clear_angel_session()
            return _quote_api_post(mode, tokens, invalidate_and_retry=False)
        if "access denied" in msg or "exceeding access rate" in msg or "rate" in msg:
            raise RuntimeError(
                "Angel One API rate limit exceeded (quote). "
                "Increase ANGEL_API_MIN_INTERVAL_SEC or wait before retrying."
            ) from e
        raise

    if not isinstance(result, dict):
        raise RuntimeError(f"Quote unexpected response type: {type(result).__name__}")

    if not result.get("status"):
        msg = str(result.get("message") or result)
        err_l = msg.lower()
        errcode = str(result.get("errorcode", "") or "").lower()
        if invalidate_and_retry and (
            "invalid token" in err_l or "ag8001" in err_l or "ag8001" in errcode
        ):
            log.warning("Angel quote rejected; refreshing session once: %s", msg[:120])
            clear_angel_session()
            return _quote_api_post(mode, tokens, invalidate_and_retry=False)
        raise RuntimeError(f"Quote {mode} failed: {msg}")

    return result


def _require_creds() -> None:
    if not all([API_KEY, CLIENT_ID, PASSWORD, TOTP_KEY]):
        raise RuntimeError("Missing Angel One credentials (ANGEL_ONE_API_KEY/CLIENT_ID/PASSWORD/TOTP_SECRET).")


def get_session():
    """
    Create (or reuse) SmartAPI session.
    Caches the SmartConnect obj and jwt token in-memory.
    """
    _require_creds()

    if _session.get("obj") and _session.get("auth_token"):
        return _session["obj"], _session["auth_token"]

    log.info("Angel One: logging in for SmartAPI session...")
    obj = SmartConnect(api_key=API_KEY)
    totp = pyotp.TOTP(TOTP_KEY).now()
    data = obj.generateSession(CLIENT_ID, PASSWORD, totp)
    if not data.get("status"):
        raise RuntimeError(data.get("message", "Login failed"))

    _session["obj"] = obj
    _session["auth_token"] = _normalize_jwt_token(data["data"].get("jwtToken"))
    return obj, _session["auth_token"]


def _safe_float(val, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _mcx_ltp_scale() -> float:
    """Angel MCX quote/LTP payloads often use paise-style ints (÷100 for ₹). Set ANGEL_MCX_LTP_DIVISOR=1 if already rupees."""
    try:
        raw = os.getenv("ANGEL_MCX_LTP_DIVISOR", "100").strip()
        if not raw:
            return 100.0
        v = float(raw)
        return v if v > 0 else 100.0
    except ValueError:
        return 100.0


def normalize_mcx_angel_quote_row(q: Optional[dict]) -> None:
    """In-place: divide common MCX price fields by ANGEL_MCX_LTP_DIVISOR (default 100)."""
    if not q or not isinstance(q, dict):
        return
    div = _mcx_ltp_scale()
    if div == 1.0:
        return
    price_keys = (
        "ltp",
        "LTP",
        "open",
        "high",
        "low",
        "close",
        "openPriceOfTheDay",
        "highPriceOfTheDay",
        "lowPriceOfTheDay",
        "closedPrice",
        "lastTradedPrice",
        "lastTradePrice",
        "netPrice",
        "averageTradePrice",
        "avgPrice",
        "averageTradedPrice",
    )
    for k in price_keys:
        if k not in q or q[k] is None or q[k] == "":
            continue
        try:
            v = float(q[k])
            if v != 0.0:
                q[k] = v / div
        except (TypeError, ValueError):
            pass
    depth = q.get("depth")
    if isinstance(depth, dict):
        for side in ("buy", "sell"):
            arr = depth.get(side)
            if not isinstance(arr, list):
                continue
            for row in arr:
                if isinstance(row, dict) and row.get("price") is not None:
                    try:
                        pv = float(row["price"])
                        if pv:
                            row["price"] = pv / div
                    except (TypeError, ValueError):
                        pass


def scrip_token_from_item(it: dict) -> str:
    tok = it.get("symboltoken")
    if tok is None:
        tok = it.get("symbolToken")
    if tok is None:
        return ""
    return str(tok).strip()


def tradingsymbol_from_item(it: dict) -> str:
    s = it.get("tradingsymbol") or it.get("tradingSymbol") or ""
    return str(s).strip()


def extract_ltp_from_quote(q: dict) -> float:
    """Angel quote payloads vary; probe common keys (and BUY depth) for a positive LTP."""
    if not q:
        return 0.0
    for key in (
        "ltp",
        "LTP",
        "lastTradedPrice",
        "last_traded_price",
        "close",
        "open",
        "netPrice",
    ):
        v = _safe_float(q.get(key), 0.0)
        if v > 0:
            return v
    depth = q.get("depth") if isinstance(q.get("depth"), dict) else None
    if depth:
        buy = depth.get("buy")
        if isinstance(buy, list) and buy:
            v = _safe_float((buy[0] or {}).get("price"), 0.0)
            if v > 0:
                return v
    return 0.0


def parse_expiry_date(it: dict) -> Optional[datetime]:
    exp = (it.get("expiry") or "").strip()
    for fmt in ["%d%b%Y", "%d%B%Y", "%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d-%b-%y"]:
        try:
            return datetime.strptime(exp, fmt)
        except Exception:
            pass

    ts = tradingsymbol_from_item(it).upper()
    # Example tradingsymbol: SILVERM24APR F... (varies by broker format)
    m = re.search(r"(\d{2})([A-Z]{3})(\d{2,4})FUT", ts)
    if m:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        yr = "20" + yr if len(yr) == 2 else yr
        try:
            return datetime.strptime(f"{day}{mon}{yr}", "%d%b%Y")
        except Exception:
            pass
    return None


def _tradingsymbol_embeds_may_or_july(tradingsymbol: str) -> bool:
    """MCX-style month in symbol: ...28MAY2026FUT or ...05JUL2025FUT (case-insensitive)."""
    u = (tradingsymbol or "").upper()
    return bool(re.search(r"\d{1,2}MAY\d{2,4}FUT", u) or re.search(r"\d{1,2}JUL\d{2,4}FUT", u))


def resolve_token_for_tradingsymbol(tradingsymbol: str, exchange: str = "MCX") -> Tuple[str, str]:
    """
    Resolve Angel symboltoken for an exact MCX tradingsymbol (e.g. SILVER05MAY26FUT)
    via searchScrip, case-insensitive match.
    """
    target = (tradingsymbol or "").strip().upper()
    if not target:
        raise ValueError("tradingsymbol is required")

    obj, _ = get_session()
    search_keys = []
    if target not in search_keys:
        search_keys.append(target)
    stem = target.replace("FUT", "").strip()
    if stem and stem not in search_keys:
        search_keys.append(stem[: min(len(stem), 16)])
    if stem[:8] not in search_keys:
        search_keys.append(stem[:8])
    if "SILVER" not in search_keys:
        search_keys.append("SILVER")

    last_err = None
    for q in search_keys:
        try:
            search_data = angel_search_scrip(obj, exchange, q)
            if not search_data.get("status"):
                last_err = search_data.get("message") or search_data
                continue
            items = search_data.get("data") or []
            for it in items:
                if tradingsymbol_from_item(it).upper() == target:
                    tok = scrip_token_from_item(it)
                    if tok:
                        return str(tok).strip(), tradingsymbol_from_item(it)
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Could not resolve token for {target!r} (last: {last_err})")


def fetch_full_quote(tokens: List[str]) -> Dict[str, dict]:
    """
    Fetch FULL quotes for a list of MCX tokens using Angel One REST quote endpoint.
    Returns dict keyed by symbolToken.
    """
    if not tokens:
        return {}

    result = _quote_api_post("FULL", tokens)

    fetched = result.get("data", {}).get("fetched", []) or []
    out: Dict[str, dict] = {}
    for item in fetched:
        token = str(item.get("symbolToken") or item.get("symboltoken") or "").strip()
        if token:
            out[token] = item
    return out


def fetch_ltp_quote(tokens: List[str]) -> Dict[str, dict]:
    """LTP-only quote batch (fallback when FULL mode omits ltp)."""
    if not tokens:
        return {}

    result = _quote_api_post("LTP", [str(t) for t in tokens])

    fetched = result.get("data", {}).get("fetched", []) or []
    out: Dict[str, dict] = {}
    for item in fetched:
        token = str(item.get("symbolToken") or item.get("symboltoken") or "").strip()
        if token:
            normalize_mcx_angel_quote_row(item)
            out[token] = item
    return out


def enrich_quotes_with_ltp(quotes: Dict[str, dict], tokens: List[str]) -> None:
    missing = [t for t in tokens if extract_ltp_from_quote(quotes.get(t, {}) or {}) <= 0]
    if not missing:
        return
    try:
        ltp_batch = fetch_ltp_quote(missing)
    except Exception as ex:
        log.warning("LTP enrichment failed: %s", ex)
        return
    for t in missing:
        row = ltp_batch.get(str(t)) or ltp_batch.get(t) or {}
        ltp = extract_ltp_from_quote(row)
        if ltp > 0:
            q = quotes.setdefault(str(t), {})
            q["ltp"] = ltp


def suggest_risk_amount(available_amount: float, vol_data: dict) -> dict:
    level = vol_data.get("level", "NORMAL")
    rng = RISK_PCT[level]
    pct_mid = (rng[0] + rng[1]) / 2
    return {
        "risk_amount": round(available_amount * pct_mid, 2),
        "risk_pct_min": rng[0] * 100,
        "risk_pct_max": rng[1] * 100,
        "risk_pct_mid": pct_mid * 100,
        "level": level,
        "reasoning": {
            "HIGH": f"Volatility HIGH — Using 30-40% risk range (midpoint 35%)",
            "NORMAL": f"Volatility NORMAL — Using 40-50% risk range (midpoint 45%)",
            "LOW": f"Volatility LOW — Using 60-70% risk range (midpoint 65%)",
        }[level],
    }


def calculate_volatility_from_quote(q: dict) -> dict:
    """
    Volatility estimation based on OHLC from FULL quote.
    Uses ATR% approximation: (high-low)/close*100.
    """
    high = _safe_float(q.get("high"), 0.0)
    low = _safe_float(q.get("low"), 0.0)
    close = _safe_float(q.get("close"), 0.0) or extract_ltp_from_quote(q)
    open_ = _safe_float(q.get("open"), 0.0)
    if high > 0 and low > 0 and close > 0:
        atr_pct = ((high - low) / close) * 100.0
    else:
        atr_pct = 0.0

    level = (
        "HIGH" if atr_pct >= VOLATILITY_THRESHOLDS["HIGH"] else
        "NORMAL" if atr_pct >= VOLATILITY_THRESHOLDS["NORMAL"] else
        "LOW"
    )
    return {
        "level": level,
        "atr_pct": round(atr_pct, 3),
        "atr_source": "full_quote_ohlc",
        "high": high,
        "low": low,
        "close": close,
        "open": open_,
        "ticks_used": 0,
    }


def pick_best_contract(symbol_type: str) -> dict:
    """
    Search and pick best contract by highest volume among the nearest valid expiries.
    Only filters by SILVER / SILVERM / SILVERMIC family.
    """
    symbol_type = (symbol_type or "SILVER").upper()
    if symbol_type not in LOT_SIZES:
        raise HTTPException(status_code=400, detail="symbol_type must be SILVER, SILVERM, or SILVERMIC")

    obj, _ = get_session()

    # Query string to search; broker returns many contracts.
    search_data = angel_search_scrip(obj, "MCX", symbol_type)
    if not search_data.get("status"):
        raise RuntimeError(f"searchScrip failed: {search_data}")

    items = search_data.get("data") or []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Filter futures for the specific family.
    futs: List[dict] = []
    for it in items:
        s = tradingsymbol_from_item(it).upper()
        if not s.endswith("FUT"):
            continue
        if symbol_type == "SILVERMIC" and s.startswith("SILVERMIC"):
            futs.append(it)
        elif symbol_type == "SILVERM" and s.startswith("SILVERM") and not s.startswith("SILVERMIC"):
            futs.append(it)
        elif symbol_type == "SILVER" and s.startswith("SILVER") and not s.startswith("SILVERM"):
            futs.append(it)

    if not futs:
        raise RuntimeError(f"No futures contracts found for {symbol_type}")

    expiry_rows: List[tuple] = []
    for it in futs:
        exp_dt = parse_expiry_date(it)
        if exp_dt is None:
            continue
        days = (exp_dt - today).days
        expiry_rows.append((it, exp_dt, days))

    if not expiry_rows:
        raise RuntimeError(f"No parseable expiry dates for {symbol_type} futures")

    expiry_rows.sort(key=lambda x: x[1])
    near: List[tuple] = [row for row in expiry_rows if row[2] >= 10]
    if not near:
        near = [row for row in expiry_rows if row[2] >= 0]
    if not near:
        raise RuntimeError(f"No non-expired contracts for {symbol_type}")

    cand_limit = 12
    for it, exp_dt, days in near[:cand_limit]:
        it["_expiry_dt"] = exp_dt
        it["_days_to_expiry"] = days
    candidates = [row[0] for row in near[:cand_limit]]

    tokens = [scrip_token_from_item(f) for f in candidates if scrip_token_from_item(f)]
    if not tokens:
        raise RuntimeError(f"No tokens found for {symbol_type}")

    quotes = fetch_full_quote(tokens)
    enrich_quotes_with_ltp(quotes, tokens)

    best = None
    best_vol = -1.0
    for fut in candidates:
        token = scrip_token_from_item(fut)
        if not token:
            continue
        q = quotes.get(token, {}) or {}
        vol = _safe_float(q.get("tradeVolume"), 0.0) or _safe_float(q.get("volume"), 0.0)
        if vol > best_vol:
            best_vol = vol
            best = {
                "symboltoken": scrip_token_from_item(fut) or fut.get("symboltoken"),
                "tradingsymbol": tradingsymbol_from_item(fut),
                "expiry": fut.get("expiry", ""),
                "days_to_expiry": fut.get("_days_to_expiry"),
                "volume": vol,
                "quote": q,
            }

    if not best:
        raise RuntimeError(f"Could not pick best contract for {symbol_type}")

    # Attach quote-derived fields for convenience
    q = best["quote"]
    best["ltp"] = extract_ltp_from_quote(q)
    best["open"] = _safe_float(q.get("open"), 0.0)
    best["high"] = _safe_float(q.get("high"), 0.0)
    best["low"] = _safe_float(q.get("low"), 0.0)
    best["close"] = _safe_float(q.get("close"), 0.0)
    best["openInterest"] = int(_safe_float(q.get("openInterest"), 0.0))

    return best


def pick_contract_for_expiry_months(
    symbol_type: str = "SILVER",
    months: Optional[Set[int]] = None,
) -> dict:
    """
    Pick an MCX Silver-family future whose calendar expiry is in one of the given months
    (default May=5 or July=7), choosing the **nearest** such expiry then **highest volume**
    among a small candidate set — same FULL quote path as pick_best_contract.

    This targets the contract month you care about (e.g. May / Jul) rather than an arbitrary
    far-month symbol. The returned quote fields (ltp/ohlc) are the current market for that future.
    """
    months = months or {5, 7}
    symbol_type = (symbol_type or "SILVER").upper()
    if symbol_type not in LOT_SIZES:
        raise HTTPException(status_code=400, detail="symbol_type must be SILVER, SILVERM, or SILVERMIC")

    obj, _ = get_session()
    search_data = angel_search_scrip(obj, "MCX", symbol_type)
    if not search_data.get("status"):
        raise RuntimeError(f"searchScrip failed: {search_data}")

    items = search_data.get("data") or []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    futs: List[dict] = []
    for it in items:
        s = tradingsymbol_from_item(it).upper()
        if not s.endswith("FUT"):
            continue
        if symbol_type == "SILVERMIC" and s.startswith("SILVERMIC"):
            futs.append(it)
        elif symbol_type == "SILVERM" and s.startswith("SILVERM") and not s.startswith("SILVERMIC"):
            futs.append(it)
        elif symbol_type == "SILVER" and s.startswith("SILVER") and not s.startswith("SILVERM"):
            futs.append(it)

    if not futs:
        raise RuntimeError(f"No futures contracts found for {symbol_type}")

    month_rows: List[tuple] = []
    for it in futs:
        sym = tradingsymbol_from_item(it)
        u = sym.upper()
        exp_dt = parse_expiry_date(it)
        sym_mj = _tradingsymbol_embeds_may_or_july(sym)

        include = False
        days = (exp_dt - today).days if exp_dt else None
        if exp_dt is not None:
            if exp_dt.month in months and days is not None and days >= 0:
                include = True
        if not include and sym_mj:
            if exp_dt is None:
                include = True
            elif days is not None and days >= 0:
                include = True

        if not include:
            continue

        sort_dt = exp_dt if exp_dt is not None else today
        eff_days = days if days is not None else 0
        month_rows.append((it, sort_dt, eff_days))

    if not month_rows:
        log.warning(
            "No May/Jul %s futures from broker search; falling back to nearest liquid contract",
            symbol_type,
        )
        return pick_best_contract(symbol_type)

    month_rows.sort(key=lambda x: x[1])
    cand_limit = 12
    for it, exp_dt, days in month_rows[:cand_limit]:
        it["_expiry_dt"] = exp_dt
        it["_days_to_expiry"] = days
    candidates = [row[0] for row in month_rows[:cand_limit]]

    tokens = [scrip_token_from_item(f) for f in candidates if scrip_token_from_item(f)]
    if not tokens:
        raise RuntimeError(f"No tokens for {symbol_type} May/Jul candidates")

    quotes = fetch_full_quote(tokens)
    enrich_quotes_with_ltp(quotes, tokens)

    best = None
    best_vol = -1.0
    for fut in candidates:
        token = scrip_token_from_item(fut)
        if not token:
            continue
        q = quotes.get(token, {}) or {}
        vol = _safe_float(q.get("tradeVolume"), 0.0) or _safe_float(q.get("volume"), 0.0)
        if vol > best_vol:
            best_vol = vol
            best = {
                "symboltoken": scrip_token_from_item(fut) or fut.get("symboltoken"),
                "tradingsymbol": tradingsymbol_from_item(fut),
                "expiry": fut.get("expiry", ""),
                "days_to_expiry": fut.get("_days_to_expiry"),
                "expiry_month": fut.get("_expiry_dt").month if fut.get("_expiry_dt") else None,
                "volume": vol,
                "quote": q,
            }

    if not best:
        fut0 = candidates[0]
        t0 = scrip_token_from_item(fut0)
        if t0:
            quotes0 = fetch_full_quote([t0])
            enrich_quotes_with_ltp(quotes0, [t0])
            q0 = quotes0.get(t0, {}) or {}
            best = {
                "symboltoken": scrip_token_from_item(fut0) or fut0.get("symboltoken"),
                "tradingsymbol": tradingsymbol_from_item(fut0),
                "expiry": fut0.get("expiry", ""),
                "days_to_expiry": fut0.get("_days_to_expiry"),
                "expiry_month": fut0.get("_expiry_dt").month if fut0.get("_expiry_dt") else None,
                "volume": 0.0,
                "quote": q0,
            }

    if not best:
        return pick_best_contract(symbol_type)

    q = best["quote"]
    best["ltp"] = extract_ltp_from_quote(q)
    best["open"] = _safe_float(q.get("open"), 0.0)
    best["high"] = _safe_float(q.get("high"), 0.0)
    best["low"] = _safe_float(q.get("low"), 0.0)
    best["close"] = _safe_float(q.get("close"), 0.0)
    best["openInterest"] = int(_safe_float(q.get("openInterest"), 0.0))

    return best


# -----------------------------
# API Models
# -----------------------------
class SmartAllocateRequest(BaseModel):
    available_amount: float
    product_type: str = "CARRYFORWARD"
    symbol_type: str = "SILVER"


def _allocate_for_symbol_family(body: "SmartAllocateRequest", alloc_symbol: str) -> dict:
    """
    Build allocation dict for one futures family (SILVER / SILVERM / SILVERMIC).
    Uses live quotes only; never orders. Raises RuntimeError if sizing is not possible.
    """
    alloc_symbol = (alloc_symbol or "SILVER").upper()
    best = pick_best_contract(alloc_symbol)

    q = best.get("quote") or {}
    ltp = extract_ltp_from_quote(q)
    if ltp <= 0:
        ltp = _safe_float(best.get("ltp"), 0.0)
    if ltp <= 0:
        raise RuntimeError("Could not fetch live LTP for selected contract.")

    vol_data = calculate_volatility_from_quote(q)
    risk_data = suggest_risk_amount(body.available_amount, vol_data)

    budget = min(body.available_amount, risk_data["risk_amount"])
    lot_size = LOT_SIZES[alloc_symbol]

    # Paper margin estimate only (not a broker margin API — no money movement here).
    margin_per_lot = float(ltp) * lot_size * 0.12
    if margin_per_lot <= 0:
        raise RuntimeError("Invalid margin_per_lot computed.")

    max_lots_cap = 5
    lots = int(min(max_lots_cap, math.floor(budget / margin_per_lot)))
    if lots < 1:
        raise RuntimeError("Insufficient balance to allocate at least 1 lot for this contract size.")

    total_kg = lots * lot_size
    total_margin = lots * margin_per_lot
    remaining_cash = round(budget - total_margin, 2)
    utilization = round((total_margin / budget) * 100, 1) if budget > 0 else 0.0

    tok = best.get("symboltoken")
    buy_orders = [
        {
            "action": "BUY",
            "intent": "paper_simulation",
            "contract": best["tradingsymbol"],
            "symbol_token": str(tok) if tok is not None else "",
            "lots": lots,
            "lot_size_kg": lot_size,
            "total_kg": total_kg,
            "ltp": float(ltp),
            "margin_per_lot": round(margin_per_lot, 2),
            "total_margin": round(total_margin, 2),
            "exposure_value": round(total_kg * float(ltp), 2),
        }
    ]

    requested = (body.symbol_type or "SILVER").upper()
    summary = {
        "available_capital": round(body.available_amount, 2),
        "requested_symbol_type": requested,
        "allocation_symbol_type": alloc_symbol,
        "volatility_level": vol_data["level"],
        "risk_pct_used": f"{risk_data['risk_pct_mid']}%",
        "risk_amount": risk_data["risk_amount"],
        "budget_deployed": round(budget, 2),
        "live_price_Rs": float(ltp),
        "total_lots": lots,
        "total_silver_kg": total_kg,
        "total_margin_used": round(total_margin, 2),
        "remaining_cash": remaining_cash,
        "capital_utilization": f"{utilization}%",
        "reasoning": risk_data["reasoning"],
        "paper_trading_note": "Sizing only from live quotes — this API does not place orders.",
    }

    return {
        "status": True,
        "summary": summary,
        "buy_orders": buy_orders,
        "errors": [],
        "execution_mode": "paper_sizing_only",
        "orders_placed": False,
    }


@app.get("/health")
def health():
    return {
        "status": True,
        "message": "MCX Silver Smart Allocator is running (External SmartAPI)",
        "execution_mode": "paper_sizing_only",
        "orders_placed": False,
    }


@app.post("/api/smart-allocate")
def smart_allocate(body: SmartAllocateRequest):
    if body.available_amount <= 0:
        raise HTTPException(status_code=400, detail="available_amount is required")

    symbol_type = (body.symbol_type or "SILVER").upper()
    if symbol_type not in LOT_SIZES:
        raise HTTPException(status_code=400, detail="symbol_type must be SILVER, SILVERM, or SILVERMIC")

    chain = SYMBOL_FALLBACK_CHAIN.get(symbol_type, [symbol_type])
    errors: List[str] = []
    last_exc: Optional[Exception] = None

    for sym in chain:
        try:
            out = _allocate_for_symbol_family(body, sym)
            if sym != symbol_type:
                out["summary"]["symbol_cascade_note"] = (
                    f"Requested {symbol_type}; allocated using {sym} so at least one lot fits the paper budget."
                )
            return out
        except HTTPException:
            raise
        except Exception as e:
            last_exc = e
            errors.append(f"{sym}: {e}")
            log.warning("Allocate attempt failed for %s: %s", sym, e)

    if last_exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "External allocator failed (all symbol tiers)",
                "errors": errors,
                "execution_mode": "paper_sizing_only",
                "orders_placed": False,
            },
        )
    raise HTTPException(status_code=500, detail="External allocator failed")

