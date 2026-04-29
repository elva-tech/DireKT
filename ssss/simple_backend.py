#!/usr/bin/env python3
"""
MCX Silver Futures - Web Backend API (Standalone)
===================================================
Simplified FastAPI backend for testing without all trading dependencies.

Features:
  • Basic RESTful API endpoints
  • WebSocket support for real-time data
  • Mock authentication and data
  • CORS support for frontend integration

Usage:
    python3 simple_backend.py
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173"
]

# Pydantic models for API
class LoginRequest(BaseModel):
    username: str
    password: str

class TradeRequest(BaseModel):
    symbol: str
    action: str
    quantity: int
    order_type: str = "LIMIT"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None

class LotCalculationRequest(BaseModel):
    current_price: float
    available_balance: Optional[float] = None

# Session management
class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
    
    def create_session(self, user_data: Dict) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "authenticated": True
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        return self.sessions.get(session_id)
    
    def update_activity(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]["last_activity"] = datetime.now()
    
    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_personal_message(self, message: dict, session_id: str):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")
                self.disconnect(session_id)

# Global instances
session_manager = SessionManager()
connection_manager = ConnectionManager()

# FastAPI app
app = FastAPI(
    title="MCX Silver Futures Trading API",
    description="Web API for MCX Silver Futures paper trading system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
# security = HTTPBearer()

async def get_current_user():
    """Mock authentication for demo purposes."""
    return {
        "user_id": "user_001",
        "username": "admin",
        "role": "admin",
        "authenticated": True
    }

# API Routes
@app.get("/")
async def root():
    return {
        "message": "MCX Silver Futures Trading API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Authenticate user and create session."""
    # Mock authentication
    if request.username == "admin" and request.password == "admin123":
        user_data = {
            "user_id": "user_001",
            "username": request.username,
            "role": "admin"
        }
        
        session_id = session_manager.create_session(user_data)
        
        return {
            "success": True,
            "session_id": session_id,
            "user": user_data,
            "message": "Login successful"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@app.get("/api/strategies/available")
async def get_available_strategies():
    """Get available trading strategies."""
    strategies = {
        "ml_model": {
            "strategy_type": "ml_model",
            "name": "Machine Learning Model",
            "description": "Random Forest classifier trained on historical data",
            "min_confidence": 65.0,
            "requires_llm": False,
            "requires_ml_model": True,
            "parameters": {
                "model_path": "best_model_random_forest_2025.pkl",
                "features_count": 65
            }
        },
        "llm_model": {
            "strategy_type": "llm_model",
            "name": "LLM-Powered Trading",
            "description": "Large Language Model analyzing market conditions",
            "min_confidence": 65.0,
            "requires_llm": True,
            "requires_ml_model": False,
            "parameters": {
                "confidence_threshold": 65.0,
                "risk_reward_ratio": 2.0,
                "atr_multiplier": 1.5
            }
        },
        "rule_based": {
            "strategy_type": "rule_based",
            "name": "Rule-Based Trading",
            "description": "Technical analysis rules and indicators",
            "min_confidence": 70.0,
            "requires_llm": False,
            "requires_ml_model": False,
            "parameters": {
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "volume_threshold": 1.5
            }
        },
        "hybrid": {
            "strategy_type": "hybrid",
            "name": "Hybrid Strategy",
            "description": "Combines ML, LLM, and rule-based signals",
            "min_confidence": 75.0,
            "requires_llm": True,
            "requires_ml_model": True,
            "parameters": {
                "ml_weight": 0.4,
                "llm_weight": 0.4,
                "rule_weight": 0.2,
                "consensus_threshold": 0.7
            }
        }
    }
    
    return {
        "success": True,
        "strategies": strategies
    }

@app.post("/api/lot/calculate")
async def calculate_lots(request: LotCalculationRequest):
    """Calculate optimal lot size."""
    try:
        # Mock lot calculation
        current_price = request.current_price
        available_balance = request.available_balance or 200000
        
        # Simple calculation
        contract_value = current_price * 30  # 30 kg per lot
        margin_per_lot = contract_value * 0.12  # 12% margin
        max_lots_by_capital = int(available_balance / margin_per_lot)
        max_lots = min(max_lots_by_capital, 5)  # Risk cap at 5 lots
        
        lot_info = {
            "symbol": "SILVERM2026",
            "lot_size": 30,
            "max_lots": max_lots,
            "trade_quantity": max_lots * 30,
            "margin_per_lot": margin_per_lot,
            "contract_value": contract_value,
            "available_capital": available_balance,
            "utilization_pct": round((max_lots * margin_per_lot) / available_balance * 100, 2)
        }
        
        return {
            "success": True,
            "lot_info": lot_info,
            "risk_validated": max_lots > 0,
            "message": "Lot calculation completed"
        }
        
    except Exception as e:
        logger.error(f"Error calculating lots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/trading/signals/generate")
async def generate_signal():
    """Generate trading signal based on selected strategy."""
    try:
        # Mock signal generation
        import random
        
        actions = ["BUY", "SELL", "HOLD"]
        action = random.choice(actions)
        
        if action == "HOLD":
            confidence = 0
        else:
            confidence = random.randint(65, 95)
        
        base_price = 28150.0
        price_variation = random.uniform(-50, 50)
        
        signal = {
            "action": action,
            "confidence": confidence,
            "entry_price": base_price + price_variation,
            "stop_loss": base_price + price_variation - 100,
            "target": base_price + price_variation + 200,
            "reason": f"Mock {action} signal generated for testing",
            "timestamp": datetime.now().isoformat(),
            "risk_reward_ratio": 2.0
        }
        
        return {
            "success": True,
            "signal": signal,
            "market_data": {
                "ohlc": {
                    "open": base_price,
                    "high": base_price + 75,
                    "low": base_price - 75,
                    "close": base_price + price_variation,
                    "volume": 1500
                },
                "indicators": {
                    "RSI": 55.5,
                    "MACD": 12.3,
                    "ATR": 85.5,
                    "SMA_20": 28080.0,
                    "EMA_12": 28120.0,
                    "volume_ratio": 1.2,
                    "trend_strength": 0.3
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating signal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/trading/orders/place")
async def place_order(request: TradeRequest):
    """Place trading order."""
    try:
        # Mock order placement
        order_id = f"ORD_{uuid.uuid4().hex[:8].upper()}"
        
        order = {
            "order_id": order_id,
            "symbol": request.symbol,
            "action": request.action,
            "quantity": request.quantity,
            "order_type": request.order_type,
            "price": request.price or 28150.0,
            "stop_loss": request.stop_loss,
            "target": request.target,
            "status": "PENDING",
            "created_at": datetime.now().isoformat(),
            "user_id": "user_001"
        }
        
        return {
            "success": True,
            "order": order,
            "message": "Order placed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/trading/orders/history")
async def get_order_history():
    """Get order history."""
    # Mock order history
    orders = [
        {
            "order_id": "ORD_001",
            "symbol": "SILVERM2026",
            "action": "BUY",
            "quantity": 30,
            "price": 28150.0,
            "status": "COMPLETED",
            "pnl": 250.0,
            "created_at": "2026-03-25T10:30:00"
        },
        {
            "order_id": "ORD_002", 
            "symbol": "SILVERM2026",
            "action": "SELL",
            "quantity": 30,
            "price": 28200.0,
            "status": "COMPLETED",
            "pnl": 150.0,
            "created_at": "2026-03-25T11:15:00"
        }
    ]
    
    return {
        "success": True,
        "orders": orders,
        "total_orders": len(orders)
    }

@app.get("/api/portfolio/summary")
async def get_portfolio_summary():
    """Get portfolio summary."""
    # Mock portfolio data
    portfolio = {
        "total_value": 100000.0,
        "available_balance": 85000.0,
        "invested_amount": 15000.0,
        "today_pnl": 400.0,
        "today_pnl_pct": 0.47,
        "total_pnl": 2500.0,
        "total_pnl_pct": 2.56,
        "positions": [
            {
                "symbol": "SILVERM2026",
                "quantity": 30,
                "avg_price": 28150.0,
                "current_price": 28165.0,
                "pnl": 450.0,
                "pnl_pct": 0.53
            }
        ],
        "daily_trades": 5,
        "win_rate": 60.0
    }
    
    return {
        "success": True,
        "portfolio": portfolio
    }

@app.get("/api/risk/metrics")
async def get_risk_metrics():
    """Get risk management metrics."""
    # Mock risk metrics
    risk_metrics = {
        "daily_pnl": 400.0,
        "daily_trades": 5,
        "daily_wins": 3,
        "daily_losses": 2,
        "max_drawdown": 2.5,
        "current_drawdown": 0.8,
        "risk_score": 25.5,
        "win_rate": 60.0,
        "avg_win": 250.0,
        "avg_loss": 175.0,
        "profit_factor": 1.43,
        "daily_loss_limit": 3000.0,
        "max_risk_per_trade": 1500.0,
        "risk_utilization": 13.3
    }
    
    return {
        "success": True,
        "risk_metrics": risk_metrics
    }

@app.get("/api/market/data")
async def get_market_data():
    """Get current market data."""
    # Mock market data with realistic variations
    import random
    base_price = 28165.0
    variation = random.uniform(-100, 100)
    
    market_data = {
        "symbol": "SILVERM2026",
        "last_price": base_price + variation,
        "change": variation,
        "change_pct": (variation / base_price) * 100,
        "volume": 15420 + random.randint(-1000, 1000),
        "oi": 148500 + random.randint(-5000, 5000),
        "bid": base_price + variation - 5,
        "ask": base_price + variation + 5,
        "high": base_price + 75,
        "low": base_price - 75,
        "open": base_price,
        "timestamp": datetime.now().isoformat()
    }
    
    return {
        "success": True,
        "market_data": market_data
    }

# WebSocket endpoint
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time data streaming."""
    await connection_manager.connect(websocket, session_id)
    
    try:
        while True:
            # Send real-time market data updates
            import random
            base_price = 28165.0
            variation = random.uniform(-50, 50)
            
            market_data = {
                "type": "market_update",
                "data": {
                    "symbol": "SILVERM2026",
                    "price": base_price + variation,
                    "change": variation,
                    "volume": 15420 + random.randint(-500, 500),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            await connection_manager.send_personal_message(market_data, session_id)
            
            # Wait before next update
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        connection_manager.disconnect(session_id)
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(session_id)

# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "active_connections": len(connection_manager.active_connections),
        "active_sessions": len(session_manager.sessions)
    }

if __name__ == "__main__":
    uvicorn.run(
        "simple_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
