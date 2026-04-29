#!/usr/bin/env python3
"""
MCX Silver Futures - Enhanced Trading Bot with Strategy Selection
=================================================================
Extended trading bot with auto lot selection, LLM integration, and strategy selection.

Features:
  • Interactive strategy selection (ML/LLM/Rule-based/Hybrid)
  • Automatic lot calculation based on available capital
  • Enhanced risk management with daily loss limits
  • Seamless integration with existing pipeline
  • Real-time strategy switching

Usage:
    python3 enhanced_trading_bot.py
"""

import os
import sys
import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple, Any
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from threading import Thread, Event
import schedule

# Import existing modules
from angel_one_connector import AngelOneConnector, RealTimeDataStream
from dhan_trader import DhanTradingClient
from mcx_realtime_final import MCXRealTimeData

# Import new modules
from lot_selector import LotSelector, LotInfo
from llm_engine import LLMTradingEngine, TradingDecision
from strategy_selector import StrategySelector, StrategyType, StrategyConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('enhanced_trading_bot.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── CONFIG ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    log.warning("python-dotenv not found. Ensure .env variables are set.")

TRADING_SYMBOL = os.getenv('TRADING_SYMBOL', 'SILVER')
TRADING_EXCHANGE = os.getenv('TRADING_EXCHANGE', 'MCX')
MIN_CONFIDENCE = float(os.getenv('MIN_CONFIDENCE', '0.65'))
MAX_POSITION_SIZE = int(os.getenv('MAX_POSITION_SIZE', '5'))
STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PCT', '1.5'))
PROFIT_TARGET_PCT = float(os.getenv('PROFIT_TARGET_PCT', '2.0'))
PAPER_TRADE = os.getenv('PAPER_TRADE_ENABLED', 'true').lower() == 'true'
FETCH_INTERVAL_SECONDS = int(os.getenv('FETCH_INTERVAL_SECONDS', '5'))

# Risk management
DAILY_LOSS_LIMIT_PCT = float(os.getenv('DAILY_LOSS_LIMIT_PCT', '3.0'))
MAX_RISK_PER_TRADE_PCT = float(os.getenv('MAX_RISK_PER_TRADE_PCT', '1.5'))

# Model paths
MODEL_PATH = "best_model_random_forest_2025.pkl"
SCALER_PATH = "feature_scaler.pkl"


class EnhancedTradingBot:
    """Enhanced trading bot with strategy selection and auto lot sizing."""
    
    def __init__(self):
        """Initialize enhanced trading bot."""
        log.info("="*70)
        log.info("🚀 MCX SILVER FUTURES - ENHANCED TRADING BOT")
        log.info("="*70)
        
        # Initialize new components
        self.strategy_selector = StrategySelector()
        self.lot_selector = None
        self.llm_engine = None
        
        # Trading state
        self.selected_strategy = None
        self.lot_info = None
        self.daily_pnl = 0.0
        self.daily_start_time = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        self.trading_enabled = True
        
        # Load credentials and initialize connectors
        self._initialize_connectors()
        
        # Load ML model (for ML strategy)
        self._load_ml_model()
        
        # Interactive setup
        self._interactive_setup()
        
    def _initialize_connectors(self):
        """Initialize API connectors."""
        # Load Angel One credentials
        angel_client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
        angel_client_secret = os.getenv('ANGEL_ONE_CLIENT_SECRET')
        angel_api_key = os.getenv('ANGEL_ONE_API_KEY')
        angel_totp = os.getenv('ANGEL_ONE_TOTP_SECRET')
        angel_password = os.getenv('ANGEL_ONE_PASSWORD')
        angel_user_id = os.getenv('ANGEL_ONE_USER_ID')
        
        # Load Dhan credentials
        dhan_api_key = os.getenv('DHAN_API_KEY')
        dhan_access_token = os.getenv('DHAN_ACCESS_TOKEN')
        dhan_client_id = os.getenv('DHAN_CLIENT_ID')
        
        # Validate credentials
        missing = []
        for var, name in [
            (angel_client_id, 'ANGEL_ONE_CLIENT_ID'),
            (angel_client_secret, 'ANGEL_ONE_CLIENT_SECRET'),
            (angel_api_key, 'ANGEL_ONE_API_KEY'),
            (angel_totp, 'ANGEL_ONE_TOTP_SECRET'),
            (angel_password, 'ANGEL_ONE_PASSWORD'),
            (angel_user_id, 'ANGEL_ONE_USER_ID'),
            (dhan_client_id, 'DHAN_CLIENT_ID'),
            (dhan_access_token, 'DHAN_ACCESS_TOKEN')
        ]:
            if not var:
                missing.append(name)
        
        if missing:
            log.error(f"❌ Missing credentials: {', '.join(missing)}")
            log.error("Add them to .env file. Use .env.example as template.")
            sys.exit(1)
        
        # Initialize connectors
        self.angel_connector = AngelOneConnector(
            angel_client_id, angel_client_secret, angel_api_key,
            angel_totp, angel_password, angel_user_id
        )
        self.dhan_client = DhanTradingClient(
            dhan_access_token, dhan_client_id, paper_trade=PAPER_TRADE
        )
        
        # Initialize lot selector with Dhan client
        self.lot_selector = LotSelector(self.dhan_client)
        
    def _load_ml_model(self):
        """Load ML model for strategy use."""
        try:
            if os.path.exists(MODEL_PATH):
                with open(MODEL_PATH, 'rb') as f:
                    self.ml_model = pickle.load(f)
                log.info(f"✅ ML model loaded: {MODEL_PATH}")
                
                # Load scaler if exists
                if os.path.exists(SCALER_PATH):
                    with open(SCALER_PATH, 'rb') as f:
                        self.scaler = pickle.load(f)
                    log.info(f"✅ Feature scaler loaded: {SCALER_PATH}")
                else:
                    self.scaler = None
                    log.warning("⚠️ Feature scaler not found")
            else:
                self.ml_model = None
                self.scaler = None
                log.warning(f"⚠️ ML model not found: {MODEL_PATH}")
        except Exception as e:
            log.error(f"❌ Error loading ML model: {e}")
            self.ml_model = None
            self.scaler = None
    
    def _interactive_setup(self):
        """Interactive setup for strategy selection and lot calculation."""
        print("\n" + "="*70)
        print("🔧 ENHANCED TRADING BOT SETUP")
        print("="*70)
        
        # Step 1: Strategy selection
        print("\n📊 Step 1: Strategy Selection")
        self.selected_strategy = self.strategy_selector.select_strategy_interactive()
        
        if not self.selected_strategy:
            log.info("No strategy selected. Exiting...")
            sys.exit(0)
        
        # Step 2: Initialize strategy-specific components
        self._initialize_strategy_components()
        
        # Step 3: Lot selection
        print("\n💰 Step 2: Auto Lot Selection")
        self._perform_lot_selection()
        
        # Step 4: Risk validation
        print("\n🛡️ Step 3: Risk Management Setup")
        self._validate_risk_parameters()
        
        print("\n✅ Setup complete! Ready to start trading...")
        
    def _initialize_strategy_components(self):
        """Initialize components based on selected strategy."""
        if self.selected_strategy.strategy_type == StrategyType.LLM_MODEL:
            # Initialize LLM engine
            llm_api_key = os.getenv('LLM_API_KEY')
            self.llm_engine = LLMTradingEngine(api_key=llm_api_key)
            log.info("✅ LLM engine initialized")
        
        elif self.selected_strategy.strategy_type == StrategyType.HYBRID:
            # Initialize both ML and LLM
            llm_api_key = os.getenv('LLM_API_KEY')
            self.llm_engine = LLMTradingEngine(api_key=llm_api_key)
            log.info("✅ Hybrid strategy components initialized")
        
        log.info(f"✅ {self.selected_strategy.name} strategy initialized")
    
    def _perform_lot_selection(self):
        """Perform automatic lot selection."""
        # Get current market price (mock for setup, real in runtime)
        current_price = 28150.0  # Mock price for setup
        
        print(f"Current market price: ₹{current_price:.2f}")
        
        # Calculate optimal lots
        self.lot_info = self.lot_selector.calculate_optimal_lots(current_price)
        
        # Validate risk limits
        if self.lot_selector.validate_risk_limits(self.lot_info):
            print(f"✅ Lot allocation successful:")
            print(f"   Max lots: {self.lot_info.max_lots}")
            print(f"   Trade quantity: {self.lot_info.trade_quantity} kg")
            print(f"   Capital utilization: {self.lot_info.utilization_pct:.1f}%")
        else:
            log.error("❌ Lot allocation failed risk validation")
            sys.exit(1)
    
    def _validate_risk_parameters(self):
        """Validate and display risk parameters."""
        print(f"Risk Management Parameters:")
        print(f"   Daily loss limit: {DAILY_LOSS_LIMIT_PCT}%")
        print(f"   Max risk per trade: {MAX_RISK_PER_TRADE_PCT}%")
        print(f"   Stop loss: {STOP_LOSS_PCT}%")
        print(f"   Profit target: {PROFIT_TARGET_PCT}%")
        print(f"   Max position size: {MAX_POSITION_SIZE} lots")
        
        # Validate risk parameters
        if DAILY_LOSS_LIMIT_PCT > 5.0:
            print("⚠️  Warning: Daily loss limit is high (>5%)")
        
        if MAX_RISK_PER_TRADE_PCT > 2.0:
            print("⚠️  Warning: Risk per trade is high (>2%)")
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is reached."""
        if self.daily_pnl <= -abs(DAILY_LOSS_LIMIT_PCT * self.lot_info.available_capital / 100):
            log.error(f"🛑 Daily loss limit reached: ₹{self.daily_pnl:,.2f}")
            self.trading_enabled = False
            return False
        return True
    
    def _generate_ml_signal(self, features: np.ndarray) -> Tuple[str, float]:
        """Generate signal using ML model."""
        if not self.ml_model:
            return "HOLD", 0.0
        
        try:
            # Scale features if scaler is available
            if self.scaler:
                features = self.scaler.transform([features])
            else:
                features = [features]
            
            # Predict
            prediction = self.ml_model.predict_proba(features)[0]
            confidence = max(prediction) * 100
            
            if prediction[1] > 0.5:
                return "BUY", confidence
            else:
                return "SELL", confidence
                
        except Exception as e:
            log.error(f"Error generating ML signal: {e}")
            return "HOLD", 0.0
    
    def _generate_llm_signal(self, ohlc_data: Dict, indicators: Dict) -> TradingDecision:
        """Generate signal using LLM engine."""
        if not self.llm_engine:
            return TradingDecision(
                action="HOLD", confidence=0.0, entry_price=0.0,
                stop_loss=0.0, target=0.0, reason="LLM not available",
                timestamp=datetime.now().isoformat(), risk_reward_ratio=0.0
            )
        
        return self.llm_engine.generate_decision(ohlc_data, indicators)
    
    def _generate_hybrid_signal(self, ohlc_data: Dict, indicators: Dict, features: np.ndarray) -> TradingDecision:
        """Generate signal using hybrid approach."""
        # Get ML signal
        ml_action, ml_confidence = self._generate_ml_signal(features)
        
        # Get LLM signal
        llm_decision = self._generate_llm_signal(ohlc_data, indicators)
        
        # Simple rule-based signal (RSI-based)
        rsi = indicators.get('RSI', 50)
        if rsi < 30:
            rule_action = "BUY"
            rule_confidence = 70.0
        elif rsi > 70:
            rule_action = "SELL"
            rule_confidence = 70.0
        else:
            rule_action = "HOLD"
            rule_confidence = 50.0
        
        # Weighted combination
        ml_weight = self.selected_strategy.parameters.get('ml_weight', 0.4)
        llm_weight = self.selected_strategy.parameters.get('llm_weight', 0.4)
        rule_weight = self.selected_strategy.parameters.get('rule_weight', 0.2)
        
        # Convert actions to numeric scores (-1 for SELL, 0 for HOLD, 1 for BUY)
        action_scores = {
            "SELL": -1,
            "HOLD": 0,
            "BUY": 1
        }
        
        ml_score = action_scores[ml_action] * (ml_confidence / 100)
        llm_score = action_scores[llm_decision.action] * (llm_decision.confidence / 100)
        rule_score = action_scores[rule_action] * (rule_confidence / 100)
        
        combined_score = (ml_score * ml_weight + llm_score * llm_weight + rule_score * rule_weight)
        combined_confidence = abs(combined_score) * 100
        
        if combined_score > 0.3:
            final_action = "BUY"
        elif combined_score < -0.3:
            final_action = "SELL"
        else:
            final_action = "HOLD"
        
        return TradingDecision(
            action=final_action,
            confidence=combined_confidence,
            entry_price=ohlc_data.get('close', 0),
            stop_loss=llm_decision.stop_loss,
            target=llm_decision.target,
            reason=f"Hybrid: ML({ml_action}:{ml_confidence:.1f}%) + LLM({llm_decision.action}:{llm_decision.confidence:.1f}%) + Rule({rule_action}:{rule_confidence:.1f}%)",
            timestamp=datetime.now().isoformat(),
            risk_reward_ratio=llm_decision.risk_reward_ratio
        )
    
    def _execute_trade(self, decision: TradingDecision) -> bool:
        """Execute trade based on decision."""
        if decision.action == "HOLD":
            return True
        
        if not self.trading_enabled:
            log.warning("Trading disabled - daily loss limit reached")
            return False
        
        # Check confidence threshold
        min_conf = self.selected_strategy.min_confidence
        if decision.confidence < min_conf:
            log.info(f"Signal confidence too low: {decision.confidence:.1f}% < {min_conf}%")
            return True
        
        # Calculate position size based on lot info
        if self.lot_info.max_lots <= 0:
            log.error("No lots available for trading")
            return False
        
        # Place order
        try:
            order_result = self.dhan_client.place_order(
                symbol=TRADING_SYMBOL,
                quantity=self.lot_info.trade_quantity,
                side=decision.action,
                order_type="LIMIT",
                price=decision.entry_price,
                exchange=TRADING_EXCHANGE,
                sl_price=decision.stop_loss,
                target_price=decision.target
            )
            
            if order_result:
                log.info(f"✅ Order placed: {decision.action} {self.lot_info.trade_quantity} {TRADING_SYMBOL} @ ₹{decision.entry_price:.2f}")
                return True
            else:
                log.error(f"❌ Order failed: {decision.action}")
                return False
                
        except Exception as e:
            log.error(f"Error executing trade: {e}")
            return False
    
    def run(self):
        """Main trading loop."""
        log.info("🚀 Starting enhanced trading bot...")
        log.info(f"Strategy: {self.selected_strategy.name}")
        log.info(f"Lots: {self.lot_info.max_lots}")
        log.info(f"Mode: {'📄 PAPER TRADING' if PAPER_TRADE else '💰 LIVE TRADING'}")
        
        # Initialize real-time data feed
        data_stream = RealTimeDataStream(self.angel_connector)
        
        try:
            while True:
                # Check daily loss limit
                if not self._check_daily_loss_limit():
                    log.info("Daily loss limit reached. Stopping trading...")
                    break
                
                # Get latest data (mock for now)
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
                
                features = np.random.random(65)  # Mock features
                
                # Generate signal based on strategy
                if self.selected_strategy.strategy_type == StrategyType.ML_MODEL:
                    ml_action, ml_confidence = self._generate_ml_signal(features)
                    decision = TradingDecision(
                        action=ml_action,
                        confidence=ml_confidence,
                        entry_price=ohlc_data['close'],
                        stop_loss=ohlc_data['close'] * (1 - STOP_LOSS_PCT/100),
                        target=ohlc_data['close'] * (1 + PROFIT_TARGET_PCT/100),
                        reason="ML model prediction",
                        timestamp=datetime.now().isoformat(),
                        risk_reward_ratio=PROFIT_TARGET_PCT/STOP_LOSS_PCT
                    )
                
                elif self.selected_strategy.strategy_type == StrategyType.LLM_MODEL:
                    decision = self._generate_llm_signal(ohlc_data, indicators)
                
                elif self.selected_strategy.strategy_type == StrategyType.HYBRID:
                    decision = self._generate_hybrid_signal(ohlc_data, indicators, features)
                
                else:  # Rule-based
                    rsi = indicators['RSI']
                    if rsi < 30:
                        action = "BUY"
                        confidence = 70.0
                    elif rsi > 70:
                        action = "SELL"
                        confidence = 70.0
                    else:
                        action = "HOLD"
                        confidence = 50.0
                    
                    decision = TradingDecision(
                        action=action,
                        confidence=confidence,
                        entry_price=ohlc_data['close'],
                        stop_loss=ohlc_data['close'] * (1 - STOP_LOSS_PCT/100),
                        target=ohlc_data['close'] * (1 + PROFIT_TARGET_PCT/100),
                        reason=f"Rule-based (RSI: {rsi:.1f})",
                        timestamp=datetime.now().isoformat(),
                        risk_reward_ratio=PROFIT_TARGET_PCT/STOP_LOSS_PCT
                    )
                
                # Execute trade
                if decision:
                    log.info(f"Signal: {decision.action} @ ₹{decision.entry_price:.2f} "
                           f"(Confidence: {decision.confidence:.1f}%, Reason: {decision.reason})")
                    
                    self._execute_trade(decision)
                
                # Wait for next interval
                time.sleep(FETCH_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            log.info("🛑 Trading stopped by user")
        except Exception as e:
            log.error(f"❌ Trading error: {e}")
        finally:
            log.info("📊 Trading session ended")


def main():
    """Main entry point."""
    try:
        bot = EnhancedTradingBot()
        bot.run()
    except KeyboardInterrupt:
        log.info("🛑 Bot stopped by user")
    except Exception as e:
        log.error(f"❌ Bot initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
