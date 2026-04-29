"""
MCX Silver Smart Allocator — Simplified Version (No SmartApi dependency)
Run:  python app.py
Base: http://localhost:5000
Docs: http://localhost:5000/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
import threading
import time
import math
import uvicorn
from datetime import datetime, timedelta
import random

app = FastAPI(
    title="MCX Silver Smart Allocator",
    description="Finds best silver futures contracts and allocates lots based on volatility",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LOT_SIZES = {"SILVER": 30, "SILVERM": 5, "SILVERMIC": 1}

VOLATILITY_THRESHOLDS = {"HIGH": 2.0, "NORMAL": 1.0}

RISK_PCT = {
    "HIGH":   (0.30, 0.40),   # High volatility   → risk only 30-40% of capital
    "NORMAL": (0.40, 0.50),   # Medium volatility  → risk 40-50% of capital
    "LOW":    (0.60, 0.70),   # Low volatility     → risk 60-70% of capital
}

# --- Pydantic Models ---
class SubscribeRequest(BaseModel):
    token: str
    symbol: str = "SILVER"

class ContractItem(BaseModel):
    symbol_type: str
    token: str
    trading_symbol: str

class AllocateRequest(BaseModel):
    available_amount: float
    risk_amount: float
    ltp: float
    product_type: str = "CARRYFORWARD"
    contracts: List[ContractItem]

class SmartAllocateRequest(BaseModel):
    available_amount: float
    product_type: str = "CARRYFORWARD"
    # For paper-first integration we allow selecting only one contract family
    # (SILVER / SILVERM / SILVERMIC) so downstream trading systems can size consistently.
    symbol_type: str = "SILVER"

# Mock data for demonstration
MOCK_CONTRACTS = {
    "SILVER": {
        "symboltoken": "260105",
        "tradingsymbol": "SILVER24APRFUT",
        "expiry": "2024-04-05",
        "days_to_expiry": 15,
        "volume": 1250,
        "ltp": 65000,
        "open": 64800,
        "high": 65200,
        "low": 64700,
        "close": 65050,
        "openInterest": 4500
    },
    "SILVERM": {
        "symboltoken": "260106",
        "tradingsymbol": "SILVERM24APRFUT",
        "expiry": "2024-04-05",
        "days_to_expiry": 15,
        "volume": 850,
        "ltp": 65100,
        "open": 64900,
        "high": 65300,
        "low": 64800,
        "close": 65150,
        "openInterest": 3200
    },
    "SILVERMIC": {
        "symboltoken": "260107",
        "tradingsymbol": "SILVERMIC24APRFUT",
        "expiry": "2024-04-05",
        "days_to_expiry": 15,
        "volume": 600,
        "ltp": 65200,
        "open": 65000,
        "high": 65400,
        "low": 64900,
        "close": 65250,
        "openInterest": 2100
    }
}

_current_token  = None
_current_symbol = None
_price_history  = []
_MAX_TICKS      = 200

def fetch_ltp(token_str):
    """Mock LTP fetching for demonstration"""
    try:
        # Simulate realistic price movement
        base_price = 65000
        variation = random.uniform(-200, 200)
        ltp = base_price + variation
        
        if ltp > 0:
            return ltp, None
        return None, "Mock data unavailable"
    except Exception as e:
        return None, str(e)

def calculate_volatility(token_str):
    """Mock volatility calculation"""
    try:
        # Simulate realistic market data
        base_price = 65000
        high = base_price + random.uniform(100, 300)
        low = base_price - random.uniform(100, 300)
        close = base_price + random.uniform(-50, 50)
        open_ = base_price + random.uniform(-50, 50)
        
        # Calculate ATR-based volatility
        atr_pct = ((high - low) / close * 100) if high > 0 and low > 0 and close > 0 else 0.0
        
        # Add some randomness to tick volatility
        tick_vol = random.uniform(0.5, 2.0)
        
        # Combine: prefer OHLC ATR, else tick vol
        primary = atr_pct if atr_pct > 0 else tick_vol * 3
        level = ("HIGH" if primary >= VOLATILITY_THRESHOLDS["HIGH"]
                 else "NORMAL" if primary >= VOLATILITY_THRESHOLDS["NORMAL"] else "LOW")

        print(f"Mock Volatility: ATR%={atr_pct:.3f} tick_vol%={tick_vol:.3f} level={level}")
        return {
            "level":           level,
            "atr_pct":         round(atr_pct, 3),
            "atr_source":      "mock_data",
            "tick_vol":        round(tick_vol, 3),
            "high":            high,
            "low":             low,
            "close":           close,
            "open":            open_,
            "ticks_used":      len(_price_history),
        }
    except Exception as e:
        print(f"calculate_volatility error: {e}")
        return {"level": "NORMAL", "atr_pct": 0, "atr_source": "none", "tick_vol": 0,
                "high": 0, "low": 0, "close": 0, "open": 0, "ticks_used": 0}

def suggest_risk_amount(available_amount, vol_data):
    level   = vol_data.get("level", "NORMAL")
    rng     = RISK_PCT[level]
    pct_mid = (rng[0] + rng[1]) / 2
    return {
        "risk_amount":  round(available_amount * pct_mid, 2),
        "risk_pct_min": rng[0] * 100,
        "risk_pct_max": rng[1] * 100,
        "risk_pct_mid": pct_mid * 100,
        "level":        level,
        "reasoning": {
            "HIGH":   f"Volatility HIGH (ATR={vol_data['atr_pct']:.2f}%) — Using 30-40% risk range (midpoint 35%)",
            "NORMAL": f"Volatility MEDIUM (ATR={vol_data['atr_pct']:.2f}%) — Using 40-50% risk range (midpoint 45%)",
            "LOW":    f"Volatility LOW (ATR={vol_data['atr_pct']:.2f}%) — Using 60-70% risk range (midpoint 65%)",
        }[level],
    }

def pick_best_contract(symbol):
    """Mock contract selection"""
    try:
        if symbol not in MOCK_CONTRACTS:
            return None, f"Symbol {symbol} not found"
        
        # Simulate some variation in volume
        contract = MOCK_CONTRACTS[symbol].copy()
        contract["volume"] = contract["volume"] + random.randint(-100, 100)
        
        print(f"Mock {symbol}: {contract['tradingsymbol']} vol={contract['volume']}")
        return contract, None
    except Exception as e:
        print(f"pick_best_contract error: {e}")
        return None, str(e)

def fetch_margin(token, trading_symbol, symbol_type, lots, price, product_type):
    """Mock margin calculation"""
    try:
        # Simulate margin calculation (approximately 12% of contract value)
        lot_size = LOT_SIZES.get(symbol_type, 30)
        contract_value = lots * lot_size * price
        margin_required = contract_value * 0.12
        
        return {
            "totalMarginRequired": margin_required,
            "spanMargin": margin_required * 0.8,
            "exposureMargin": margin_required * 0.2,
            "availableBalance": 1000000  # Mock available balance
        }
    except Exception as e:
        print(f"fetch_margin error: {e}")
        return None

def greedy_allocate(budget, ltp, contracts, product_type):
    LABELS = {"SILVER": "Silver Standard", "SILVERM": "Silver Mini", "SILVERMIC": "Silver Micro"}
    cms = []
    for c in contracts:
        stype  = c["symbol_type"]
        margin = fetch_margin(c["token"], c["trading_symbol"], stype, 1, ltp, product_type)
        mpl    = (margin["totalMarginRequired"]
                  if margin and margin["totalMarginRequired"] > 0
                  else LOT_SIZES[stype] * ltp * 0.15)
        if not (margin and margin["totalMarginRequired"] > 0):
            print(f"Estimated margin for {stype}: Rs.{mpl:.2f}")
        cms.append({"symbol_type": stype, "token": c["token"],
                    "trading_symbol": c["trading_symbol"], "lot_size": LOT_SIZES[stype],
                    "margin_per_lot": mpl, "label": LABELS[stype]})
    cms.sort(key=lambda x: x["lot_size"], reverse=True)
    remaining, allocation, total_lots, total_margin, total_kg = budget, [], 0, 0, 0
    for cm in cms:
        if remaining < cm["margin_per_lot"]:
            continue
        lots = int(remaining // cm["margin_per_lot"])
        if lots <= 0:
            continue
        cost = lots * cm["margin_per_lot"]
        kg   = lots * cm["lot_size"]
        allocation.append({
            "symbol_type": cm["symbol_type"], "label": cm["label"],
            "trading_symbol": cm["trading_symbol"], "token": cm["token"],
            "lots": lots, "lot_size": cm["lot_size"],
            "margin_per_lot": round(cm["margin_per_lot"], 2),
            "total_margin": round(cost, 2), "total_kg": kg,
            "exposure_value": round(kg * ltp, 2),
        })
        remaining -= cost; total_lots += lots; total_margin += cost; total_kg += kg
    return {
        "allocation": allocation, "total_lots": total_lots,
        "total_margin": round(total_margin, 2), "total_kg": total_kg,
        "total_exposure": round(total_kg * ltp, 2),
        "remaining_cash": round(remaining, 2),
        "utilization": round((total_margin / budget * 100) if budget > 0 else 0, 1),
    }

def poll_loop():
    global _price_history
    while True:
        if _current_token:
            ltp, err = fetch_ltp(_current_token)
            if ltp and ltp > 0:
                _price_history.append(ltp)
                if len(_price_history) > _MAX_TICKS:
                    _price_history.pop(0)
                print(f"[poll] {_current_symbol} LTP={ltp}")
            else:
                print(f"[poll] error: {err}")
        time.sleep(3)

# ═══════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════

@app.get("/health")
def health():
    return {"status": True, "message": "MCX Silver API is running (Mock Mode)"}

@app.get("/api/best-contract")
def best_contract(symbol: str = Query(default="SILVER", description="SILVER | SILVERM | SILVERMIC")):
    symbol = symbol.upper()
    if symbol not in LOT_SIZES:
        raise HTTPException(status_code=400, detail="symbol must be SILVER, SILVERM, or SILVERMIC")
    best, err = pick_best_contract(symbol)
    if best:
        return {"status": True, "symbol": symbol, "data": best}
    raise HTTPException(status_code=500, detail=err or "Could not find contract")

@app.get("/api/ltp")
def get_ltp(token: str = Query(..., description="Instrument token from /api/best-contract")):
    ltp, err = fetch_ltp(token)
    if ltp:
        return {"status": True, "ltp": ltp}
    raise HTTPException(status_code=500, detail=str(err))

@app.get("/api/volatility")
def get_volatility(
    token: str     = Query(..., description="Instrument token"),
    available: float = Query(default=0, description="Available capital in Rs"),
):
    vol_data  = calculate_volatility(token)
    risk_data = suggest_risk_amount(available, vol_data) if available > 0 else {}
    return {"status": True, "volatility": vol_data, "risk": risk_data}

@app.post("/api/subscribe")
def subscribe(body: SubscribeRequest):
    global _current_token, _current_symbol, _price_history
    if body.token != _current_token:
        _price_history = []
    _current_token  = body.token
    _current_symbol = body.symbol
    
    # Start polling thread if not already running
    if not hasattr(subscribe, '_poll_thread') or not subscribe._poll_thread.is_alive():
        subscribe._poll_thread = threading.Thread(target=poll_loop, daemon=True)
        subscribe._poll_thread.start()
    
    ltp, err = fetch_ltp(body.token)
    if ltp:
        _price_history.append(ltp)
    return {"status": True, "ltp": ltp, "symbol": body.symbol, "message": err}

@app.post("/api/allocate")
def allocate(body: AllocateRequest):
    if body.available_amount <= 0:
        raise HTTPException(status_code=400, detail="available_amount is required")
    if body.risk_amount <= 0:
        raise HTTPException(status_code=400, detail="risk_amount is required")
    if body.ltp <= 0:
        raise HTTPException(status_code=400, detail="ltp must be greater than 0")
    if not body.contracts:
        raise HTTPException(status_code=400, detail="contracts list is required")
    contracts = [{"symbol_type": c.symbol_type, "token": c.token, "trading_symbol": c.trading_symbol}
                 for c in body.contracts]
    budget = min(body.available_amount, body.risk_amount)
    result = greedy_allocate(budget, body.ltp, contracts, body.product_type)
    result.update({"budget": round(budget, 2), "available": round(body.available_amount, 2),
                   "risk": round(body.risk_amount, 2), "ltp": body.ltp})
    return {"status": True, "data": result}

@app.post("/api/smart-allocate")
def smart_allocate(body: SmartAllocateRequest):
    if body.available_amount <= 0:
        raise HTTPException(status_code=400, detail="available_amount is required")

    errors: list[str] = []
    symbol_type = (body.symbol_type or "SILVER").upper()
    if symbol_type not in LOT_SIZES:
        raise HTTPException(
            status_code=400,
            detail={"message": "symbol_type must be SILVER, SILVERM, or SILVERMIC"},
        )

    best, err = pick_best_contract(symbol_type)
    if not best:
        raise HTTPException(status_code=500, detail={"message": "Could not find contract", "error": err})

    contracts_list = [
        {
            "symbol_type": symbol_type,
            "token": best["symboltoken"],
            "trading_symbol": best["tradingsymbol"],
        }
    ]

    token = best["symboltoken"]
    fetched_ltp, _ = fetch_ltp(str(token))
    if fetched_ltp and fetched_ltp > 0:
        ltp, ltp_token = fetched_ltp, token
    else:
        # Fallback to mock LTP stored in the contract object
        ltp, ltp_token = float(best.get("ltp", 0) or 0), token

    if ltp > 0:
        _price_history.append(ltp)
        if len(_price_history) > _MAX_TICKS:
            _price_history.pop(0)

    if ltp <= 0:
        raise HTTPException(status_code=500,
                            detail={"message": "Could not fetch live price — market may be closed"})

    vol_data  = calculate_volatility(str(ltp_token)) if ltp_token else \
                {"level": "NORMAL", "atr_pct": 0, "tick_vol": 0,
                 "high": 0, "low": 0, "close": 0, "open": 0, "ticks_used": 0}
    risk_data = suggest_risk_amount(body.available_amount, vol_data)
    budget    = min(body.available_amount, risk_data["risk_amount"])
    alloc     = greedy_allocate(budget, ltp, contracts_list, body.product_type)

    buy_orders = [{
        "action":         "BUY",
        "contract":       item["trading_symbol"],
        "lots":           item["lots"],
        "lot_size_kg":    item["lot_size"],
        "total_kg":       item["total_kg"],
        "ltp":            ltp,
        "margin_per_lot": item["margin_per_lot"],
        "total_margin":   item["total_margin"],
        "exposure_value": item["exposure_value"],
    } for item in alloc["allocation"]]

    return {
        "status": True,
        "summary": {
            "available_capital":   round(body.available_amount, 2),
            "volatility_level":    vol_data["level"],
            "risk_pct_used":       f"{risk_data['risk_pct_mid']}%",
            "risk_amount":         risk_data["risk_amount"],
            "budget_deployed":     round(budget, 2),
            "live_price_Rs":       ltp,
            "total_lots":          alloc["total_lots"],
            "total_silver_kg":     alloc["total_kg"],
            "total_margin_used":   alloc["total_margin"],
            "remaining_cash":      alloc["remaining_cash"],
            "capital_utilization": f"{alloc['utilization']}%",
            "reasoning":           risk_data["reasoning"],
        },
        "buy_orders": buy_orders,
        "errors":     errors,
    }

if __name__ == "__main__":
    # Swap to external allocator (no mock pricing) at runtime.
    from smart_allocator_external import app as external_app
    app = external_app

    print("=" * 57)
    print("  MCX Silver Smart Allocator  ->  http://localhost:5000")
    print("  Interactive Docs            ->  http://localhost:5000/docs")
    print("  MODE: EXTERNAL SMARTAPI (No mock pricing)")
    print("=" * 57)
    uvicorn.run(app, host="0.0.0.0", port=5000)
