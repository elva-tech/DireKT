#!/usr/bin/env python3
"""
MCX Silver Futures - Web Backend API
===================================
FastAPI backend server for the trading web application.

Features:
  • RESTful API endpoints for trading operations
  • WebSocket support for real-time data streaming
  • Authentication and session management
  • Integration with existing trading modules
  • CORS support for frontend integration

Usage:
    python3 backend_server.py
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import redis
from contextlib import asynccontextmanager

# Import trading modules
from lot_selector import LotSelector, LotInfo
from llm_engine import LLMTradingEngine, TradingDecision
from strategy_selector import StrategySelector, StrategyType, StrategyConfig
from risk_manager import RiskManager, RiskMetrics
from enhanced_trading_bot import EnhancedTradingBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://direkt-frontend.onrender.com",
    "https://direkt-backend-koop.onrender.com"
]

# Pydantic models for API
class LoginRequest(BaseModel):
    username: str
    password: str

class StrategySelectionRequest(BaseModel):
    strategy_type: str
    parameters: Optional[Dict[str, Any]] = None

class TradeRequest(BaseModel):
    symbol: str
    action: str
    quantity: int
    order_type: str = "LIMIT"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None

class RiskConfigRequest(BaseModel):
    daily_loss_limit_pct: float = 3.0
    max_risk_per_trade_pct: float = 1.5
    max_position_size_lots: int = 5
    max_daily_trades: int = 20

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
            "authenticated": True,
            "trading_bot": None,
            "risk_manager": None
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
        self.user_connections: Dict[str, List[str]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        
        # Add to user connections if authenticated
        session = session_manager.get_session(session_id)
        if session and session.get("authenticated"):
            user_id = session.get("user_id")
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(session_id)
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        
        # Remove from user connections
        session = session_manager.get_session(session_id)
        if session and session.get("authenticated"):
            user_id = session.get("user_id")
            if user_id in self.user_connections:
                self.user_connections[user_id] = [
                    sid for sid in self.user_connections[user_id] if sid != session_id
                ]
    
    async def send_personal_message(self, message: dict, session_id: str):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")
                self.disconnect(session_id)
    
    async def broadcast_to_user(self, message: dict, user_id: str):
        if user_id in self.user_connections:
            for session_id in self.user_connections[user_id]:
                await self.send_personal_message(message, session_id)

# Global instances
session_manager = SessionManager()
connection_manager = ConnectionManager()

# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 MCX Trading Web Backend starting up...")
    yield
    # Shutdown
    logger.info("🛑 MCX Trading Web Backend shutting down...")

# FastAPI app
app = FastAPI(
    title="MCX Silver Futures Trading API",
    description="Web API for MCX Silver Futures automated trading system",
    version="1.0.0",
    lifespan=lifespan
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
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    session = session_manager.get_session(token)
    
    if not session or not session.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    session_manager.update_activity(token)
    return session

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
    # Paper-first auth: accept any non-empty username/password and create an in-memory session.
    # (No real trading credentials are verified here.)
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    user_data = {
        "user_id": f"user_{uuid.uuid4().hex[:8]}",
        "username": request.username,
        "role": "paper_user",
    }

    session_id = session_manager.create_session(user_data)

    return {
        "success": True,
        "session_id": session_id,
        "user": user_data,
        "message": "Login successful",
    }

@app.post("/api/auth/logout")
async def logout(
    current_user: Dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Logout user and remove session."""
    # Remove the session token from the in-memory store.
    token = credentials.credentials
    session_manager.remove_session(token)
    return {"success": True, "message": "Logout successful"}

@app.get("/api/user/profile")
async def get_profile(current_user: Dict = Depends(get_current_user)):
    """Get user profile."""
    return {
        "success": True,
        "user": {
            "user_id": current_user.get("user_id"),
            "username": current_user.get("username"),
            "role": current_user.get("role"),
            "session_created": current_user.get("created_at").isoformat()
        }
    }

@app.get("/api/strategies/available")
async def get_available_strategies(current_user: Dict = Depends(get_current_user)):
    """Get available trading strategies."""
    selector = StrategySelector()
    strategies = {}
    
    for strategy_type, config in selector.available_strategies.items():
        strategies[strategy_type.value] = selector.to_dict(config)
    
    return {
        "success": True,
        "strategies": strategies
    }

@app.post("/api/strategies/select")
async def select_strategy(
    request: StrategySelectionRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Select trading strategy."""
    try:
        selector = StrategySelector()
        
        # Convert string to StrategyType
        strategy_map = {
            "ml_model": StrategyType.ML_MODEL,
            "llm_model": StrategyType.LLM_MODEL,
            "rule_based": StrategyType.RULE_BASED,
            "hybrid": StrategyType.HYBRID
        }
        
        strategy_type = strategy_map.get(request.strategy_type)
        if not strategy_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid strategy type"
            )
        
        # Get strategy configuration
        strategy_config = selector.get_strategy_config(strategy_type)
        if not strategy_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Strategy not available"
            )
        
        # Update parameters if provided
        if request.parameters:
            strategy_config.parameters.update(request.parameters)
        
        return {
            "success": True,
            "strategy": selector.to_dict(strategy_config),
            "message": f"Strategy {strategy_config.name} selected successfully"
        }
        
    except Exception as e:
        logger.error(f"Error selecting strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/lot/calculate")
async def calculate_lots(
    request: LotCalculationRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Calculate optimal lot size."""
    try:
        # Initialize lot selector
        lot_selector = LotSelector(mock_balance=request.available_balance)
        
        # Calculate lots
        lot_info = lot_selector.calculate_optimal_lots(request.current_price)
        
        # Validate risk limits
        is_valid = lot_selector.validate_risk_limits(lot_info)
        
        return {
            "success": True,
            "lot_info": lot_selector.to_dict(lot_info),
            "risk_validated": is_valid,
            "message": "Lot calculation completed"
        }
        
    except Exception as e:
        logger.error(f"Error calculating lots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/trading/signals/generate")
async def generate_signal(
    current_user: Dict = Depends(get_current_user)
):
    """Generate trading signal based on selected strategy."""
    try:
        # Mock data for demonstration
        ohlc_data = {
            'open': 28100.0,
            'high': 28200.0,
            'low': 28050.0,
            'close': 28150.0,
            'volume': 1500
        }
        
        indicators = {
            'RSI': 55.5,
            'MACD': 12.3,
            'ATR': 85.5,
            'SMA_20': 28080.0,
            'EMA_12': 28120.0,
            'volume_ratio': 1.2,
            'trend_strength': 0.3
        }
        
        # Initialize LLM engine
        llm_engine = LLMTradingEngine()
        
        # Generate decision
        decision = llm_engine.generate_decision(ohlc_data, indicators)
        
        return {
            "success": True,
            "signal": asdict(decision),
            "market_data": {
                "ohlc": ohlc_data,
                "indicators": indicators
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
async def place_order(
    request: TradeRequest,
    current_user: Dict = Depends(get_current_user)
):
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
            "price": request.price,
            "stop_loss": request.stop_loss,
            "target": request.target,
            "status": "PENDING",
            "created_at": datetime.now().isoformat(),
            "user_id": current_user.get("user_id")
        }
        
        # Send real-time update
        await connection_manager.broadcast_to_user(
            {
                "type": "order_placed",
                "order": order
            },
            current_user.get("user_id")
        )
        
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
async def get_order_history(current_user: Dict = Depends(get_current_user)):
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
async def get_portfolio_summary(current_user: Dict = Depends(get_current_user)):
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
async def get_risk_metrics(current_user: Dict = Depends(get_current_user)):
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

@app.post("/api/risk/config")
async def update_risk_config(
    request: RiskConfigRequest,
    current_user: Dict = Depends(get_current_user)):
    """Update risk management configuration."""
    try:
        # Update risk configuration
        config = {
            "daily_loss_limit_pct": request.daily_loss_limit_pct,
            "max_risk_per_trade_pct": request.max_risk_per_trade_pct,
            "max_position_size_lots": request.max_position_size_lots,
            "max_daily_trades": request.max_daily_trades,
            "updated_at": datetime.now().isoformat(),
            "updated_by": current_user.get("user_id")
        }
        
        return {
            "success": True,
            "config": config,
            "message": "Risk configuration updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error updating risk config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/market/data")
async def get_market_data(current_user: Dict = Depends(get_current_user)):
    """Get current market data."""
    # Mock market data
    market_data = {
        "symbol": "SILVERM2026",
        "last_price": 28165.0,
        "change": 15.0,
        "change_pct": 0.053,
        "volume": 15420,
        "oi": 148500,
        "bid": 28160.0,
        "ask": 28170.0,
        "high": 28200.0,
        "low": 28080.0,
        "open": 28150.0,
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
            market_data = {
                "type": "market_update",
                "data": {
                    "symbol": "SILVERM2026",
                    "price": 28165.0 + (hash(session_id) % 100 - 50) / 100,
                    "change": 15.0,
                    "volume": 15420,
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
        "backend_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
