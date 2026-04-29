"""
MCX Trading Integration Service
Connects frontend with Smart Allocator and Trading Systems
"""

import os
import copy
import time
from datetime import datetime, timezone, date, time as dt_time
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
from typing import Optional
import threading

from smart_allocator_external import (
    fetch_full_quote,
    enrich_quotes_with_ltp,
    extract_ltp_from_quote,
    _safe_float,
    pick_contract_for_expiry_months,
    pick_best_contract,
    resolve_token_for_tradingsymbol,
)
from trading_bot import SilverFuturesTradingBot


def _dashboard_fixed_tradingsymbol(query_override: Optional[str]) -> str:
    """Exact MCX symbol for dashboard live quote (env LIVE_QUOTE_TRADINGSYMBOL or SILVER05MAY26FUT)."""
    if query_override is not None and str(query_override).strip():
        return str(query_override).strip().upper()
    return (os.getenv("LIVE_QUOTE_TRADINGSYMBOL") or "SILVER05MAY26FUT").strip().upper()


_market_live_cache_lock = threading.Lock()
_market_live_cache: dict = {}
IST_TZ = ZoneInfo("Asia/Kolkata")


def _parse_market_holidays() -> set:
    """
    Read market holidays from env:
    MARKET_HOLIDAYS=2026-01-26,2026-03-14
    """
    raw = (os.getenv("MARKET_HOLIDAYS") or "").strip()
    out = set()
    if not raw:
        return out
    for token in raw.split(","):
        s = token.strip()
        if not s:
            continue
        try:
            out.add(date.fromisoformat(s))
        except ValueError:
            continue
    return out


def _market_window():
    start_h = int(float(os.getenv("MARKET_OPEN_HOUR_IST", "9") or 9))
    start_m = int(float(os.getenv("MARKET_OPEN_MINUTE_IST", "0") or 0))
    end_h = int(float(os.getenv("MARKET_CLOSE_HOUR_IST", "23") or 23))
    end_m = int(float(os.getenv("MARKET_CLOSE_MINUTE_IST", "30") or 30))
    start = dt_time(hour=max(0, min(23, start_h)), minute=max(0, min(59, start_m)))
    end = dt_time(hour=max(0, min(23, end_h)), minute=max(0, min(59, end_m)))
    return start, end


def _market_status_snapshot(now_utc: Optional[datetime] = None) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST_TZ)
    d = now_ist.date()
    t = now_ist.time().replace(tzinfo=None)
    start_t, end_t = _market_window()
    holidays = _parse_market_holidays()
    is_weekend = now_ist.weekday() >= 5  # Sat/Sun
    is_holiday = d in holidays
    in_hours = start_t <= t <= end_t
    is_open = (not is_weekend) and (not is_holiday) and in_hours
    if is_weekend:
        reason = "Weekend holiday"
    elif is_holiday:
        reason = "Government holiday"
    elif not in_hours:
        reason = f"Outside market hours ({start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')} IST)"
    else:
        reason = "Market open"
    return {
        "market_open": is_open,
        "market_reason": reason,
        "market_timezone": "Asia/Kolkata",
        "market_now_ist": now_ist.isoformat(),
        "market_open_time_ist": start_t.strftime("%H:%M"),
        "market_close_time_ist": end_t.strftime("%H:%M"),
        "is_weekend": is_weekend,
        "is_holiday": is_holiday,
    }


def _attach_market_status(payload: dict, status_snapshot: Optional[dict] = None) -> dict:
    ms = status_snapshot or _market_status_snapshot()
    return {**payload, **ms}


def _market_live_cache_ttl() -> float:
    try:
        return max(0.5, float(os.getenv("MARKET_LIVE_CACHE_TTL_SEC", "8") or 8))
    except ValueError:
        return 8.0


def _market_live_cache_key(
    tok: str,
    tsym: Optional[str],
    balance: Optional[float],
    family: str,
    prefer_may_jul: bool,
    use_allocation_token: bool,
    live_tradingsymbol: Optional[str],
) -> str:
    b = "" if balance is None else f"{float(balance):.6g}"
    return "|".join(
        [
            tok or "",
            tsym or "",
            b,
            family or "",
            "1" if prefer_may_jul else "0",
            "1" if use_allocation_token else "0",
            (live_tradingsymbol or "").strip().upper(),
        ]
    )


def _try_market_live_cache(key: str):
    with _market_live_cache_lock:
        hit = _market_live_cache.get(key)
        if not hit:
            return None
        if (time.monotonic() - hit["t"]) >= _market_live_cache_ttl():
            return None
        out = copy.deepcopy(hit["resp"])
        if isinstance(out.get("data"), dict):
            out["data"] = {**out["data"], "integration_cache_hit": True}
        return out


def _store_market_live_cache(key: str, resp: dict) -> dict:
    if resp.get("status") and resp.get("data"):
        with _market_live_cache_lock:
            _market_live_cache[key] = {"t": time.monotonic(), "resp": copy.deepcopy(resp)}
    return resp


def _stale_market_live_response(key: str, error_message: str):
    with _market_live_cache_lock:
        hit = _market_live_cache.get(key)
    if hit and hit["resp"].get("status") and hit["resp"].get("data"):
        out = copy.deepcopy(hit["resp"])
        out["data"] = {
            **out["data"],
            "integration_stale_fallback": True,
            "integration_stale_reason": (error_message or "")[:600],
        }
        return out
    return None


def _is_angel_rate_limit_message(msg: str) -> bool:
    s = (msg or "").lower()
    return "rate limit" in s or "exceeding access rate" in s or "access denied" in s


def _quote_snapshot(token: str, tradingsymbol: str, quotes: dict) -> dict:
    q = quotes.get(str(token), {}) or quotes.get(token, {}) or {}
    ltp = extract_ltp_from_quote(q)
    if not ltp or ltp <= 0:
        ltp = (
            _safe_float(q.get("open"), 0.0)
            or _safe_float(q.get("close"), 0.0)
            or _safe_float(q.get("lastTradedPrice"), 0.0)
        )
    close = _safe_float(q.get("close"), 0.0) or (ltp if ltp else 0.0)
    high = _safe_float(q.get("high"), 0.0)
    low = _safe_float(q.get("low"), 0.0)
    open_ = _safe_float(q.get("open"), 0.0)
    vol = _safe_float(q.get("tradeVolume"), 0.0) or _safe_float(q.get("volume"), 0.0)
    oi = int(_safe_float(q.get("openInterest"), 0.0) or _safe_float(q.get("oi"), 0.0))
    chg = None
    if close and ltp:
        chg = round((ltp - close) / close * 100.0, 3)
    return {
        "symbol_token": token,
        "tradingsymbol": tradingsymbol or "",
        "ltp": round(ltp, 2) if ltp else None,
        "open": round(open_, 2) if open_ else None,
        "high": round(high, 2) if high else None,
        "low": round(low, 2) if low else None,
        "close": round(close, 2) if close else None,
        "volume": int(vol),
        "open_interest": oi,
        "change_pct": chg,
        "as_of": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

app = FastAPI(
    title="MCX Trading Integration",
    description="Integration service for Smart Allocator and Trading Systems",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TradingStartRequest(BaseModel):
    strategy: str
    balance: float
    symbol: str = "SILVER"
    tradingsymbol: Optional[str] = None
    symbol_token: Optional[str] = None
    max_lots: Optional[int] = None
    user_id: Optional[str] = None
    username: Optional[str] = None

class TradingStatusResponse(BaseModel):
    status: bool
    message: str
    system_type: str
    active: bool

# ============================================================================
# SMART ALLOCATOR INTEGRATION
# ============================================================================

SMART_ALLOCATOR_URL = "http://localhost:5000"

def get_smart_allocation(balance: float, symbol_type: str = "SILVER"):
    """Get smart allocation from Smart Allocator API"""
    req_symbol_type = (symbol_type or "SILVER").upper()
    if req_symbol_type not in ("SILVER", "SILVERM", "SILVERMIC"):
        req_symbol_type = "SILVER"
    try:
        response = requests.post(
            f"{SMART_ALLOCATOR_URL}/api/smart-allocate",
            json={
                "available_amount": balance,
                "symbol_type": req_symbol_type,
                "product_type": "CARRYFORWARD"
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        detail = {}
        try:
            detail = response.json()
        except Exception:
            detail = {"message": (response.text or "").strip()[:400]}
        return {
            "status": False,
            "error": (
                detail.get("detail", {}).get("message")
                if isinstance(detail.get("detail"), dict)
                else detail.get("detail")
                or detail.get("message")
                or f"Allocator HTTP {response.status_code}"
            ),
            "details": detail,
        }
    except Exception as e:
        return {"status": False, "error": str(e)}

# ============================================================================
# TRADING SYSTEM STATUS
# ============================================================================

trading_systems = {
    "ml": {
        "name": "ML Model Trading",
        "status": False,
        "pid": None,
        "last_started": None,
        "description": "Machine learning based systematic trading"
    },
    "llm": {
        "name": "LLM Powered Trading", 
        "status": False,
        "pid": None,
        "last_started": None,
        "description": "Language model adaptive trading"
    },
    "hybrid": {
        "name": "Hybrid (ML + LLM verify)",
        "status": False,
        "pid": None,
        "last_started": None,
        "description": "ML proposes trades; LLM verifies before execution (paper)",
    },
}

_user_engines = {}


def _normalize_owner_key(user_id: Optional[str], username: Optional[str]) -> str:
    uid = (user_id or "").strip()
    uname = (username or "").strip().lower()
    return uid or uname


def _owner_bucket(owner_key: str, owner_username: Optional[str] = None) -> dict:
    owner = _user_engines.setdefault(owner_key, {"username": owner_username or owner_key, "engines": {}})
    if owner_username:
        owner["username"] = owner_username
    return owner


def _runtime(owner_key: str, strategy: str) -> Optional[dict]:
    owner = _user_engines.get(owner_key) or {}
    engines = owner.get("engines") or {}
    return engines.get(strategy)


def _stop_active_bot():
    # legacy no-op (kept for backward compatibility)
    return None


def _stop_runtime(owner_key: str, strategy: str) -> bool:
    owner = _user_engines.get(owner_key)
    if not owner:
        return False
    engines = owner.get("engines") or {}
    runtime = engines.get(strategy)
    if not runtime:
        return False
    bot = runtime.get("bot")
    if bot is not None:
        try:
            bot.stop()
        except Exception:
            pass
    engines.pop(strategy, None)
    if not engines:
        _user_engines.pop(owner_key, None)
    return True


def _runtime_alive(owner_key: str, strategy: str) -> bool:
    runtime = _runtime(owner_key, strategy)
    thread = (runtime or {}).get("thread")
    return thread is not None and thread.is_alive()


def start_trading_bot(
    balance: float,
    strategy: str,
    symbol_family: str = "SILVER",
    tradingsymbol: Optional[str] = None,
    symbol_token: Optional[str] = None,
    max_lots: Optional[int] = None,
    owner_key: Optional[str] = None,
    owner_username: Optional[str] = None,
):
    """
    Start ML or LLM trading on the same live Angel feed + paper Dhan execution.
    Lot count and instrument come from smart allocation (balance-driven tier: SILVER / SILVERM / SILVERMIC).
    """
    if not owner_key:
        return {"status": False, "message": "Missing owner identity", "system": strategy}
    strategy = (strategy or "ml").lower()
    if strategy not in ("ml", "llm", "hybrid"):
        return {"status": False, "message": "Invalid strategy", "system": strategy}

    if _runtime_alive(owner_key, strategy):
        return {
            "status": True,
            "message": f"{strategy.upper()} trading already running",
            "system": strategy,
            "balance": balance,
            "owner": owner_username or owner_key,
        }

    direct_lots = int(max_lots or 0)
    ts = (tradingsymbol or "").strip() or None
    tok = (symbol_token or "").strip() or None
    sym_family = symbol_family or "SILVER"

    if direct_lots < 1 or not ts:
        alloc = get_smart_allocation(balance, symbol_family)
        if not isinstance(alloc, dict) or not alloc.get("status"):
            return {
                "status": False,
                "message": f"Smart allocator unavailable: {alloc.get('error', 'unknown') if isinstance(alloc, dict) else 'unknown'}",
                "system": strategy,
            }

        buy_orders = alloc.get("buy_orders") or []
        order0 = buy_orders[0] if buy_orders else {}
        resolved_lots = 0
        for item in buy_orders:
            lots = int(item.get("lots") or 0)
            if lots > resolved_lots:
                resolved_lots = lots

        if resolved_lots <= 0:
            try:
                resolved_lots = int((alloc.get("summary") or {}).get("total_lots") or 0)
            except Exception:
                resolved_lots = 0

        if resolved_lots < 1:
            return {
                "status": False,
                "message": "Smart allocation returned 0 lots; increase balance.",
                "system": strategy,
            }

        direct_lots = resolved_lots
        ts = ts or (order0.get("contract") or "").strip() or None
        tok = tok or (order0.get("symbol_token") or "").strip() or None
        sym_family = (
            (alloc.get("summary") or {}).get("allocation_symbol_type")
            or symbol_family
            or "SILVER"
        )

    if not ts:
        ts = sym_family

    try:
        bot = SilverFuturesTradingBot(
            max_position_size=direct_lots,
            trading_symbol=ts,
            angel_instrument_token=tok,
            decision_engine=strategy,
            user_id=owner_key,
            username=owner_username,
        )
    except Exception as e:
        return {
            "status": False,
            "message": f"Failed to create trading bot: {e}",
            "system": strategy,
        }

    thread = threading.Thread(target=bot.start, daemon=True)
    thread.start()

    import time as _time

    # WebSocket setup inside AngelOneConnector can take a few seconds.
    # Don't fail the API call just because `running=True` wasn't set yet.
    max_wait_sec = float(os.getenv("TRADING_BOT_START_WAIT_SEC", "12") or 12)
    poll = 0.5
    waited = 0.0
    while waited < max_wait_sec:
        if getattr(bot, "running", False):
            break
        if not thread.is_alive():
            break
        _time.sleep(poll)
        waited += poll

    if not getattr(bot, "running", False):
        try:
            bot.stop()
        except Exception:
            pass
        return {
            "status": False,
            "message": "Trading bot failed to start (check Angel/Dhan credentials or feed token).",
            "system": strategy,
        }
    owner = _owner_bucket(owner_key, owner_username)
    owner["engines"][strategy] = {
        "bot": bot,
        "thread": thread,
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    trading_systems[strategy]["status"] = True
    trading_systems[strategy]["pid"] = thread.ident
    trading_systems[strategy]["last_started"] = "now"

    return {
        "status": True,
        "message": f"{strategy.upper()} trading started (paper mode, live Angel quotes)",
        "system": strategy,
        "balance": balance,
        "max_lots": direct_lots,
        "tradingsymbol": ts,
        "symbol_token_set": bool(tok),
        "allocation_symbol_type": sym_family,
        "owner": owner_username or owner_key,
    }

# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/")
async def root():
    return {
        "message": "MCX Trading Integration Service",
        "systems": list(trading_systems.keys()),
        "smart_allocator": SMART_ALLOCATOR_URL
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "smart_allocator": "connected" if requests.get(f"{SMART_ALLOCATOR_URL}/health", timeout=5).status_code == 200 else "disconnected",
        "trading_systems": trading_systems
    }

@app.get("/api/allocation/{balance}")
async def get_allocation(
    balance: float,
    symbol_type: str = Query("SILVER", description="Requested family: SILVER | SILVERM | SILVERMIC"),
):
    """Get smart allocation for given balance"""
    allocation = get_smart_allocation(balance, symbol_type)
    return allocation


@app.get("/api/market/live")
async def market_live(
    token: Optional[str] = Query(None, description="Override: Angel MCX instrument token (numeric)"),
    tradingsymbol: Optional[str] = Query(None, description="Override: display symbol"),
    balance: Optional[float] = Query(None, description="With use_allocation_token=1, resolve token from smart allocation"),
    symbol_family: str = Query(
        "SILVER",
        description="SILVER | SILVERM | SILVERMIC — used for May/Jul or fallback search",
    ),
    prefer_may_jul: bool = Query(
        True,
        description="If true (default), quote nearest active future expiring in May or July",
    ),
    use_allocation_token: bool = Query(
        False,
        description="If true, use allocator contract from balance= instead of May/Jul",
    ),
    live_tradingsymbol: Optional[str] = Query(
        None,
        description="Exact MCX symbol for quotes, e.g. SILVER05MAY26FUT (default from env or SILVER05MAY26FUT)",
    ),
):
    """
    Dashboard market data: by default resolves **nearest MCX Silver-family future expiring in May or July**,
    then returns a **FULL** session quote (ltp/open/high/low/close/volume/OI). That LTP is the current
    traded price for that contract month—not a generic “silver” spot.

    Override with token=, or use_allocation_token=1&balance= to mirror your allocated lot.

    **Default dashboard path:** tries fixed symbol `SILVER05MAY26FUT` (or `LIVE_QUOTE_TRADINGSYMBOL` in `.env`,
    or `live_tradingsymbol=` query) first, then falls back to May/Jul / family cascade.
    """
    tok = (token or "").strip()
    tsym = (tradingsymbol or "").strip() or None
    family = (symbol_family or "SILVER").upper()
    if family not in ("SILVER", "SILVERM", "SILVERMIC"):
        family = "SILVER"
    market_status = _market_status_snapshot()

    if not market_status["market_open"]:
        closed_payload = _attach_market_status(
            {
                "symbol_token": tok or None,
                "tradingsymbol": tsym or "",
                "ltp": None,
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "volume": 0,
                "open_interest": 0,
                "change_pct": None,
                "as_of": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "contract_selection": "market_closed",
            },
            market_status,
        )
        return {"status": True, "data": closed_payload}

    cache_key = _market_live_cache_key(
        tok,
        tsym,
        balance,
        family,
        prefer_may_jul,
        use_allocation_token,
        live_tradingsymbol,
    )
    cached = _try_market_live_cache(cache_key)
    if cached is not None:
        if isinstance(cached.get("data"), dict):
            cached["data"] = _attach_market_status(cached["data"], market_status)
        return cached

    # 1) Explicit token
    if tok.isdigit():
        try:
            quotes = fetch_full_quote([tok])
            enrich_quotes_with_ltp(quotes, [tok])
            snap = _quote_snapshot(tok, tsym or "", quotes)
            snap["contract_selection"] = "client_token"
            if not snap.get("ltp"):
                return {"status": False, "message": "Broker returned no usable LTP for this token."}
            snap = _attach_market_status(snap, market_status)
            return _store_market_live_cache(cache_key, {"status": True, "data": snap})
        except Exception as e:
            msg = str(e)
            if _is_angel_rate_limit_message(msg):
                stale = _stale_market_live_response(cache_key, msg)
                if stale:
                    return stale
            return {"status": False, "message": msg}

    # 2) Allocated instrument (optional)
    if use_allocation_token and balance is not None and float(balance) > 0:
        alloc = get_smart_allocation(float(balance))
        if alloc.get("status"):
            bo = (alloc.get("buy_orders") or [{}])[0]
            tok = (bo.get("symbol_token") or "").strip()
            if not tsym:
                tsym = (bo.get("contract") or "").strip() or None
        if tok.isdigit():
            try:
                quotes = fetch_full_quote([tok])
                enrich_quotes_with_ltp(quotes, [tok])
                snap = _quote_snapshot(tok, tsym or "", quotes)
                snap["contract_selection"] = "allocation"
                if not snap.get("ltp"):
                    return {"status": False, "message": "Broker returned no usable LTP for allocation token."}
                snap = _attach_market_status(snap, market_status)
                return _store_market_live_cache(cache_key, {"status": True, "data": snap})
            except Exception as e:
                msg = str(e)
                if _is_angel_rate_limit_message(msg):
                    stale = _stale_market_live_response(cache_key, msg)
                    if stale:
                        return stale
                return {"status": False, "message": msg}

    # 3) Fixed MCX symbol (default SILVER05MAY26FUT) — user-requested contract for live quote
    if prefer_may_jul and not tok.isdigit():
        sym_fixed = _dashboard_fixed_tradingsymbol(live_tradingsymbol)
        if sym_fixed:
            try:
                tok_f, tsym_f = resolve_token_for_tradingsymbol(sym_fixed)
                quotes_f = fetch_full_quote([tok_f])
                enrich_quotes_with_ltp(quotes_f, [tok_f])
                snap_f = _quote_snapshot(tok_f, tsym_f, quotes_f)
                snap_f["contract_selection"] = "fixed_tradingsymbol"
                snap_f["fixed_tradingsymbol"] = sym_fixed
                if snap_f.get("ltp"):
                    snap_f = _attach_market_status(snap_f, market_status)
                    return _store_market_live_cache(cache_key, {"status": True, "data": snap_f})
            except Exception:
                pass

    # 4) May / July expiry series, trying full Silver then mini/micro if fixed symbol failed
    if prefer_may_jul:
        families_order: list = []
        for fam in (family, "SILVER", "SILVERM", "SILVERMIC"):
            if fam not in ("SILVER", "SILVERM", "SILVERMIC"):
                continue
            if fam not in families_order:
                families_order.append(fam)

        best = None
        sel = None
        err_notes: list = []

        for fam in families_order:
            try:
                best = pick_contract_for_expiry_months(fam, {5, 7})
                sel = "may_or_july"
                break
            except Exception as e:
                err_notes.append(f"{fam} may/jul: {e}")
                if _is_angel_rate_limit_message(str(e)):
                    break
                try:
                    best = pick_best_contract(fam)
                    sel = "fallback_nearest_liquid"
                    break
                except Exception as e2:
                    err_notes.append(f"{fam} fallback: {e2}")
                    if _is_angel_rate_limit_message(str(e2)):
                        break
                    continue

        if not best:
            msg = "Could not load Angel quote for SILVER/SILVERM/SILVERMIC. " + (
                " | ".join(err_notes) if err_notes else "Unknown error"
            )
            if _is_angel_rate_limit_message(msg):
                stale = _stale_market_live_response(cache_key, msg)
                if stale:
                    return stale
            return {"status": False, "message": msg}

        tok = str(best.get("symboltoken") or "").strip()
        tsym = (best.get("tradingsymbol") or "").strip()
        if not tok.isdigit():
            return {"status": False, "message": "Resolved contract has no numeric token."}
        quotes = {tok: best.get("quote") or {}}
        enrich_quotes_with_ltp(quotes, [tok])
        snap = _quote_snapshot(tok, tsym, quotes)
        snap["contract_selection"] = sel
        snap["expiry_month"] = best.get("expiry_month")
        if not snap.get("ltp"):
            return {
                "status": False,
                "message": "Broker returned no usable price (ltp/ohlc) for "
                + (tsym or tok)
                + ". Check session / market hours.",
            }
        snap = _attach_market_status(snap, market_status)
        return _store_market_live_cache(cache_key, {"status": True, "data": snap})

    return {
        "status": False,
        "message": "Set prefer_may_jul=true (default), pass token=, or use_allocation_token=1 with balance=.",
    }


@app.get("/api/market/status")
async def market_status():
    """Exchange timing status (IST hours + weekends + configured holidays)."""
    return {"status": True, "data": _market_status_snapshot()}


@app.post("/api/trading/start")
async def start_trading_system(request: TradingStartRequest):
    """Start trading system (ML or LLM)"""
    
    if request.strategy not in ["ml", "llm", "hybrid"]:
        raise HTTPException(
            status_code=400,
            detail="Strategy must be 'ml', 'llm', or 'hybrid'",
        )
    
    if request.balance <= 0:
        raise HTTPException(status_code=400, detail="Balance must be greater than 0")
    
    owner_key = _normalize_owner_key(request.user_id, request.username)
    if not owner_key:
        raise HTTPException(status_code=400, detail="Missing user identity for trading session")

    result = start_trading_bot(
        request.balance,
        request.strategy,
        symbol_family=request.symbol,
        tradingsymbol=request.tradingsymbol,
        symbol_token=request.symbol_token,
        max_lots=request.max_lots,
        owner_key=owner_key,
        owner_username=request.username,
    )
    return result

@app.get("/api/trading/status/{strategy}")
async def get_trading_status(strategy: str, user_id: Optional[str] = Query(None), username: Optional[str] = Query(None)):
    """Get status of trading system"""
    
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")

    system = trading_systems[strategy]
    owner_key = _normalize_owner_key(user_id, username)
    alive = bool(owner_key) and _runtime_alive(owner_key, strategy)
    active = bool(alive)

    return TradingStatusResponse(
        status=active,
        message=f"{system['name']} is {'active' if active else 'inactive'}",
        system_type=strategy,
        active=active,
    )


@app.get("/api/trading/metrics/{strategy}")
async def get_trading_metrics(strategy: str, user_id: Optional[str] = Query(None), username: Optional[str] = Query(None)):
    """Live runtime metrics for ML/LLM engine activity."""
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")

    owner_key = _normalize_owner_key(user_id, username)
    runtime = _runtime(owner_key, strategy) if owner_key else None
    bot = (runtime or {}).get("bot")
    active = bool(owner_key and runtime and _runtime_alive(owner_key, strategy) and bot)
    if not active:
        return {
            "status": True,
            "active": False,
            "strategy": strategy,
            "metrics": {
                "engine": strategy,
                "trade_state": "IDLE",
                "block_reason": None,
                "state_machine_trade": None,
                "state_machine_history_count": 0,
                "cooldown_remaining_secs": None,
                "consecutive_quote_failures": 0,
                "consecutive_engine_failures": 0,
                "running": False,
                "quote_count": 0,
                "signal_count": 0,
                "last_quote_at": None,
                "last_signal_at": None,
                "last_quote_ltp": None,
                "last_signal_action": None,
                "last_engine_action": None,
                "last_engine_confidence": None,
                "last_engine_reason": None,
                "last_engine_reject_reason": None,
                "open_position": False,
                "open_entry_price": None,
                "open_sl_price": None,
                "open_target_price": None,
                "open_quantity": 0,
                "price_change_since_entry": 0.0,
                "entries_count": 0,
                "exits_count": 0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_pnl": 0.0,
            },
        }

    try:
        metrics = bot.get_runtime_metrics() if hasattr(bot, "get_runtime_metrics") else {}
        return {
            "status": True,
            "active": True,
            "strategy": strategy,
            "metrics": metrics,
        }
    except Exception as e:
        return {
            "status": False,
            "active": True,
            "strategy": strategy,
            "message": f"Failed to read metrics: {e}",
        }

@app.get("/api/trading/status")
async def get_all_trading_status():
    """Get status of all trading systems"""
    per_strategy_counts = {"ml": 0, "llm": 0, "hybrid": 0}
    for owner_key, owner in list(_user_engines.items()):
        engines = owner.get("engines") or {}
        for s in ("ml", "llm", "hybrid"):
            if s in engines and _runtime_alive(owner_key, s):
                per_strategy_counts[s] += 1
    return {
        "status": True,
        "systems": trading_systems,
        "active_users": len(_user_engines),
        "active_counts": per_strategy_counts,
    }


@app.get("/api/trading/history")
async def get_trade_history(
    limit: int = Query(500, ge=1, le=5000, description="Max persisted events (most recent kept)"),
    user_id: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
):
    """Persisted OPEN/CLOSED events from the trading bot (JSONL) plus current session trade_log when bot is running."""
    owner_key = _normalize_owner_key(user_id, username)
    if not owner_key:
        raise HTTPException(status_code=400, detail="Missing user identity for history request")
    path = (os.getenv("TRADE_HISTORY_FILE") or "trade_history.jsonl").strip()
    events: list = []
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    row_uid = (str(row.get("user_id") or "") or "").strip()
                    row_un = (str(row.get("username") or "") or "").strip().lower()
                    row_owner = row_uid or row_un
                    if row_owner != owner_key:
                        continue
                    events.append(row)
        except OSError:
            pass
    if len(events) > limit:
        events = events[-limit:]

    session_trades: list = []
    active_strategies: list = []
    owner = _user_engines.get(owner_key) or {}
    engines = owner.get("engines") or {}
    for s in ("ml", "llm", "hybrid"):
        runtime = engines.get(s)
        if not runtime:
            continue
        bot = runtime.get("bot")
        if not bot or not _runtime_alive(owner_key, s):
            continue
        active_strategies.append(s)
        try:
            rows = [
                json.loads(json.dumps(t, default=str))
                for t in getattr(bot, "trade_log", []) or []
            ]
            for r in rows:
                if "decision_engine" not in r:
                    r["decision_engine"] = s
                session_trades.append(r)
        except Exception:
            continue
    bot_active = len(active_strategies) > 0

    return {
        "status": True,
        "events": events,
        "event_count": len(events),
        "session_trades": session_trades,
        "bot_active": bot_active,
        "active_strategies": active_strategies,
        "history_file": path or None,
    }


@app.get("/api/trading/performance-summary")
async def get_performance_summary(
    limit: int = Query(5000, ge=10, le=50000),
    user_id: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
):
    """
    Compare model performance from persisted CLOSED trade events.
    Output is ready for UI charts (win%, total profit, total loss).
    """
    owner_key = _normalize_owner_key(user_id, username)
    if not owner_key:
        raise HTTPException(status_code=400, detail="Missing user identity for performance summary")
    path = (os.getenv("TRADE_HISTORY_FILE") or "trade_history.jsonl").strip()
    rows: list = []
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = (line or "").strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    row_uid = (str(row.get("user_id") or "") or "").strip()
                    row_un = (str(row.get("username") or "") or "").strip().lower()
                    row_owner = row_uid or row_un
                    if row_owner != owner_key:
                        continue
                    if str(row.get("lifecycle") or "").upper() != "CLOSED":
                        continue
                    rows.append(row)
        except OSError:
            pass
    if len(rows) > limit:
        rows = rows[-limit:]

    engines = {
        "ml": {"engine": "ml", "trades": 0, "wins": 0, "win_rate": 0.0, "profit": 0.0, "loss": 0.0},
        "llm": {"engine": "llm", "trades": 0, "wins": 0, "win_rate": 0.0, "profit": 0.0, "loss": 0.0},
        "hybrid": {"engine": "hybrid", "trades": 0, "wins": 0, "win_rate": 0.0, "profit": 0.0, "loss": 0.0},
    }
    for row in rows:
        eng = str(row.get("decision_engine") or "").lower()
        if eng not in engines:
            continue
        pnl = float(row.get("pnl") or 0.0)
        engines[eng]["trades"] += 1
        if pnl > 0:
            engines[eng]["wins"] += 1
            engines[eng]["profit"] += pnl
        elif pnl < 0:
            engines[eng]["loss"] += abs(pnl)

    for eng in engines.values():
        eng["win_rate"] = round((eng["wins"] / eng["trades"] * 100.0), 2) if eng["trades"] > 0 else 0.0
        eng["profit"] = round(float(eng["profit"]), 2)
        eng["loss"] = round(float(eng["loss"]), 2)

    return {"status": True, "models": [engines["ml"], engines["llm"], engines["hybrid"]]}


@app.post("/api/trading/stop/{strategy}")
async def stop_trading_system(strategy: str, user_id: Optional[str] = Query(None), username: Optional[str] = Query(None)):
    """Stop trading system"""
    
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")

    owner_key = _normalize_owner_key(user_id, username)
    if not owner_key:
        raise HTTPException(status_code=400, detail="Missing user identity for stop request")
    stopped = _stop_runtime(owner_key, strategy)
    if not stopped:
        return {"status": False, "message": f"{strategy} is not active for this user"}
    any_active_for_strategy = any(_runtime_alive(k, strategy) for k in list(_user_engines.keys()))
    trading_systems[strategy]["status"] = bool(any_active_for_strategy)
    trading_systems[strategy]["pid"] = None

    return {
        "status": True,
        "message": "Trading system stopped (ML / LLM / Hybrid)",
    }


@app.post("/api/trading/emergency-exit/{strategy}")
async def emergency_exit_trading_system(strategy: str, user_id: Optional[str] = Query(None), username: Optional[str] = Query(None)):
    """Force close active trade and block system."""
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")
    owner_key = _normalize_owner_key(user_id, username)
    if not owner_key:
        raise HTTPException(status_code=400, detail="Missing user identity for emergency exit")
    runtime = _runtime(owner_key, strategy)
    bot = (runtime or {}).get("bot")
    if not (_runtime_alive(owner_key, strategy) and bot):
        return {"status": False, "message": f"{strategy} is not active"}
    try:
        result = (
            bot.trigger_emergency_exit("Manual emergency exit")
            if hasattr(bot, "trigger_emergency_exit")
            else {"status": "blocked", "reason": "Emergency exit not supported"}
        )
        return {"status": True, "strategy": strategy, "result": result}
    except Exception as e:
        return {"status": False, "message": f"Emergency exit failed: {e}"}


@app.post("/api/trading/manual-reset/{strategy}")
async def manual_reset_trading_system(strategy: str, user_id: Optional[str] = Query(None), username: Optional[str] = Query(None)):
    """Reset BLOCKED state to IDLE."""
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")
    owner_key = _normalize_owner_key(user_id, username)
    if not owner_key:
        raise HTTPException(status_code=400, detail="Missing user identity for manual reset")
    runtime = _runtime(owner_key, strategy)
    bot = (runtime or {}).get("bot")
    if not (_runtime_alive(owner_key, strategy) and bot):
        return {"status": False, "message": f"{strategy} is not active"}
    try:
        result = (
            bot.manual_reset_state_machine()
            if hasattr(bot, "manual_reset_state_machine")
            else {"status": "not_supported"}
        )
        return {"status": True, "strategy": strategy, "result": result}
    except Exception as e:
        return {"status": False, "message": f"Manual reset failed: {e}"}

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("="*60)
    print("🚀 MCX Trading Integration Service")
    print("📡 Smart Allocator: http://localhost:5000")
    print("🤖 ML Trading: Integrated")
    print("🧠 LLM Trading: Integrated")
    print("="*60)
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
