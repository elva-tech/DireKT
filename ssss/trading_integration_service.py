"""
MCX Trading Integration Service
Connects frontend with Smart Allocator and Trading Systems
"""

import os
import copy
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
import uuid
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
    smart_allocate,
    SmartAllocateRequest,
)
from trading_bot import SilverFuturesTradingBot
import database

# Initialize database on startup
database.init_db()


def _dashboard_fixed_tradingsymbol(query_override: Optional[str]) -> str:
    """Exact MCX symbol for dashboard live quote (env LIVE_QUOTE_TRADINGSYMBOL or SILVER05MAY26FUT)."""
    if query_override is not None and str(query_override).strip():
        return str(query_override).strip().upper()
    return (os.getenv("LIVE_QUOTE_TRADINGSYMBOL") or "SILVER05MAY26FUT").strip().upper()


_market_live_cache_lock = threading.Lock()
_market_live_cache: dict = {}


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

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

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
        # Call the imported allocator logic directly (no localhost HTTP needed)
        body = SmartAllocateRequest(
            available_amount=balance,
            symbol_type=req_symbol_type,
            product_type="CARRYFORWARD"
        )
        return smart_allocate(body)
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

_trading_bot = None
_trading_thread = None
_active_strategy: Optional[str] = None


def _stop_active_bot():
    global _trading_bot
    if _trading_bot is not None:
        try:
            _trading_bot.stop()
        except Exception:
            pass
        _trading_bot = None


def _bot_thread_alive() -> bool:
    return _trading_thread is not None and _trading_thread.is_alive()


def start_trading_bot(
    balance: float,
    strategy: str,
    symbol_family: str = "SILVER",
    tradingsymbol: Optional[str] = None,
    symbol_token: Optional[str] = None,
    max_lots: Optional[int] = None,
):
    """
    Start ML or LLM trading on the same live Angel feed + paper Dhan execution.
    Lot count and instrument come from smart allocation (balance-driven tier: SILVER / SILVERM / SILVERMIC).
    """
    global _trading_bot, _trading_thread, _active_strategy
    strategy = (strategy or "ml").lower()
    if strategy not in ("ml", "llm", "hybrid"):
        return {"status": False, "message": "Invalid strategy", "system": strategy}

    if _bot_thread_alive():
        if _active_strategy == strategy:
            trading_systems[strategy]["status"] = True
            return {
                "status": True,
                "message": f"{strategy.upper()} trading already running",
                "system": strategy,
                "balance": balance,
            }
        _stop_active_bot()

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
        _trading_bot = SilverFuturesTradingBot(
            max_position_size=direct_lots,
            trading_symbol=ts,
            angel_instrument_token=tok,
            decision_engine=strategy,
        )
    except Exception as e:
        return {
            "status": False,
            "message": f"Failed to create trading bot: {e}",
            "system": strategy,
        }

    _trading_thread = threading.Thread(target=_trading_bot.start, daemon=True)
    _trading_thread.start()

    import time as _time

    # WebSocket setup inside AngelOneConnector can take a few seconds.
    # Don't fail the API call just because `running=True` wasn't set yet.
    max_wait_sec = float(os.getenv("TRADING_BOT_START_WAIT_SEC", "12") or 12)
    poll = 0.5
    waited = 0.0
    while waited < max_wait_sec:
        if getattr(_trading_bot, "running", False):
            break
        if not _bot_thread_alive():
            break
        _time.sleep(poll)
        waited += poll

    if not getattr(_trading_bot, "running", False):
        _stop_active_bot()
        return {
            "status": False,
            "message": "Trading bot failed to start (check Angel/Dhan credentials or feed token).",
            "system": strategy,
        }

    _active_strategy = strategy
    trading_systems["ml"]["status"] = strategy == "ml"
    trading_systems["llm"]["status"] = strategy == "llm"
    trading_systems["hybrid"]["status"] = strategy == "hybrid"
    trading_systems[strategy]["pid"] = _trading_thread.ident
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

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """Register a new user account."""
    if not request.username or not request.password:
        return {"success": False, "message": "Username and password required"}
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (request.username,))
        if cursor.fetchone():
            return {"success": False, "message": "Username already exists"}
        
        # Create user
        password_hash = database.hash_password(request.password)
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (request.username, password_hash)
        )
        user_id = cursor.lastrowid
        
        # Create profile
        cursor.execute(
            "INSERT INTO user_profiles (user_id) VALUES (?)",
            (user_id,)
        )
        
        conn.commit()
        return {"success": True, "message": "Account created successfully. Please login."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Registration failed: {str(e)}"}
    finally:
        conn.close()

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Authenticate user against database."""
    if not request.username or not request.password:
        return {"success": False, "message": "Username and password required"}
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (request.username,))
        user_row = cursor.fetchone()
        
        if not user_row or not database.verify_password(request.password, user_row["password_hash"]):
            return {"success": False, "message": "Invalid username or password"}
        
        # Fetch profile
        cursor.execute("SELECT balance FROM user_profiles WHERE user_id = ?", (user_row["id"],))
        profile_row = cursor.fetchone()
        balance = profile_row["balance"] if profile_row else 100000.0
        
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        user_data = {
            "user_id": user_row["id"],
            "username": user_row["username"],
            "name": user_row["username"].capitalize(),
            "role": user_row["role"],
            "balance": balance
        }
        
        return {
            "success": True,
            "session_id": session_id,
            "user": user_data,
            "message": "Login successful"
        }
    finally:
        conn.close()

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "smart_allocator": "embedded",
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
        return _store_market_live_cache(cache_key, {"status": True, "data": snap})

    return {
        "status": False,
        "message": "Set prefer_may_jul=true (default), pass token=, or use_allocation_token=1 with balance=.",
    }


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
    
    result = start_trading_bot(
        request.balance,
        request.strategy,
        symbol_family=request.symbol,
        tradingsymbol=request.tradingsymbol,
        symbol_token=request.symbol_token,
        max_lots=request.max_lots,
    )
    return result

@app.get("/api/trading/status/{strategy}")
async def get_trading_status(strategy: str):
    """Get status of trading system"""
    
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")

    system = trading_systems[strategy]
    alive = _bot_thread_alive() and _active_strategy == strategy
    active = bool(alive)

    return TradingStatusResponse(
        status=active,
        message=f"{system['name']} is {'active' if active else 'inactive'}",
        system_type=strategy,
        active=active,
    )


@app.get("/api/trading/metrics/{strategy}")
async def get_trading_metrics(strategy: str):
    """Live runtime metrics for ML/LLM engine activity."""
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")

    active = bool(_bot_thread_alive() and _active_strategy == strategy and _trading_bot)
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
        metrics = _trading_bot.get_runtime_metrics() if hasattr(_trading_bot, "get_runtime_metrics") else {}
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
    return {
        "status": True,
        "systems": trading_systems
    }


@app.get("/api/trading/history")
async def get_trade_history(
    limit: int = Query(500, ge=1, le=5000, description="Max persisted events (most recent kept)"),
):
    """Persisted OPEN/CLOSED events from the trading bot (JSONL) plus current session trade_log when bot is running."""
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
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
    if len(events) > limit:
        events = events[-limit:]

    session_trades: list = []
    active_strategy = None
    bot_active = bool(_bot_thread_alive() and _trading_bot is not None)
    if bot_active:
        try:
            active_strategy = _active_strategy
            session_trades = [
                json.loads(json.dumps(t, default=str))
                for t in getattr(_trading_bot, "trade_log", []) or []
            ]
        except Exception:
            session_trades = []

    return {
        "status": True,
        "events": events,
        "event_count": len(events),
        "session_trades": session_trades,
        "bot_active": bot_active,
        "active_strategy": active_strategy,
        "history_file": path or None,
    }


@app.get("/api/trading/performance-summary")
async def get_performance_summary(limit: int = Query(5000, ge=10, le=50000)):
    """
    Compare model performance from persisted CLOSED trade events.
    Output is ready for UI charts (win%, total profit, total loss).
    """
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
async def stop_trading_system(strategy: str):
    """Stop trading system"""
    
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")

    global _active_strategy
    _stop_active_bot()
    _active_strategy = None
    trading_systems["ml"]["status"] = False
    trading_systems["llm"]["status"] = False
    trading_systems["hybrid"]["status"] = False
    trading_systems[strategy]["pid"] = None

    return {
        "status": True,
        "message": "Trading system stopped (ML / LLM / Hybrid)",
    }


@app.post("/api/trading/emergency-exit/{strategy}")
async def emergency_exit_trading_system(strategy: str):
    """Force close active trade and block system."""
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if not (_bot_thread_alive() and _active_strategy == strategy and _trading_bot):
        return {"status": False, "message": f"{strategy} is not active"}
    try:
        result = (
            _trading_bot.trigger_emergency_exit("Manual emergency exit")
            if hasattr(_trading_bot, "trigger_emergency_exit")
            else {"status": "blocked", "reason": "Emergency exit not supported"}
        )
        return {"status": True, "strategy": strategy, "result": result}
    except Exception as e:
        return {"status": False, "message": f"Emergency exit failed: {e}"}


@app.post("/api/trading/manual-reset/{strategy}")
async def manual_reset_trading_system(strategy: str):
    """Reset BLOCKED state to IDLE."""
    if strategy not in trading_systems:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if not (_bot_thread_alive() and _active_strategy == strategy and _trading_bot):
        return {"status": False, "message": f"{strategy} is not active"}
    try:
        result = (
            _trading_bot.manual_reset_state_machine()
            if hasattr(_trading_bot, "manual_reset_state_machine")
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
