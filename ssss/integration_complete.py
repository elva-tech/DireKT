#!/usr/bin/env python3
"""
Complete Trading System Integration
===================================
WebSocket Real-Time Data → ML Signal Generation → Dhan Paper Trading

Pipeline:
  1. Load historical data (till March 2)
  2. Train ML model on historical data
  3. Connect to WebSocket for real-time ticks
  4. Generate signals using trained model
  5. Execute paper trades on Dhan
  6. Track P&L and performance

Run: python3 integration_complete.py
"""

import asyncio
import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from angel_one_websocket_realtime import AngelOneRealTimeClient, TickData

# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION & LOGGING
# ═══════════════════════════════════════════════════════════════════

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s | %(message)s',
    handlers=[
        logging.FileHandler('integration_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
PAPER_MODE = True  # Set False for live trading
INSTRUMENT = "SILVER05MAY26FUT"
EXCHANGE = "MCX"
MODEL_PATH = "best_model_random_forest_2025.pkl"
SCALER_PATH = "feature_scaler.pkl"
HISTORICAL_DATA_CSV = "mcx_silver_ml_ready.csv"


# ═══════════════════════════════════════════════════════════════════
#  HISTORICAL DATA LOADER & MODEL TRAINER
# ═══════════════════════════════════════════════════════════════════

class HistoricalDataManager:
    """Load and prepare historical data till March 2, 2026."""

    def __init__(self, csv_path: str = HISTORICAL_DATA_CSV):
        self.csv_path = csv_path
        self.df = None
        self.feature_columns = None

    def load_data(self, cutoff_date: str = "2026-03-02") -> pd.DataFrame:
        """Load historical data up to cutoff date."""
        logger.info(f"📚 Loading historical data from {self.csv_path}...")

        if not os.path.exists(self.csv_path):
            logger.error(f"❌ Data file not found: {self.csv_path}")
            return None

        try:
            self.df = pd.read_csv(self.csv_path)
            logger.info(f"   Loaded {len(self.df)} rows")

            # Convert trade_date to datetime
            if 'trade_date' in self.df.columns:
                self.df['trade_date'] = pd.to_datetime(self.df['trade_date'])
                
                # Filter till cutoff date
                cutoff = pd.to_datetime(cutoff_date)
                self.df = self.df[self.df['trade_date'] <= cutoff]
                logger.info(f"   Filtered to {len(self.df)} rows up to {cutoff_date}")

            # Handle missing values
            self.df = self.df.fillna(self.df.median(numeric_only=True))
            
            logger.info(f"✅ Data loaded: {self.df['trade_date'].min()} to {self.df['trade_date'].max()}")
            return self.df

        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            return None

    def get_features(self) -> List[str]:
        """Get feature columns (exclude non-predictive columns)."""
        exclude = ['trade_date', 'symbol', 'expiry_date', 'close', 'high', 'low', 'open',
                   'return_next_n_pct', 'target']
        features = [col for col in self.df.columns if col not in exclude]
        self.feature_columns = features
        return features


class MLModelManager:
    """Train and manage ML models."""

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.X_train = None
        self.y_train = None

    def train(self, df: pd.DataFrame, features: List[str]) -> bool:
        """Train model on historical data."""
        logger.info("🤖 Training ML Model...")

        try:
            # Prepare data
            X = df[features].copy()
            y = df.get('target', (df['close'] > df['close'].shift(1)).astype(int))

            # Split: use 80% for training, 20% for validation
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # Train Random Forest model
            logger.info("   Training Random Forest classifier...")
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=20,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
                verbose=0
            )
            self.model.fit(X_train_scaled, y_train)

            # Evaluate
            train_score = self.model.score(X_train_scaled, y_train)
            test_score = self.model.score(X_test_scaled, y_test)

            logger.info(f"✅ Model trained successfully")
            logger.info(f"   Training accuracy: {train_score:.4f}")
            logger.info(f"   Testing accuracy: {test_score:.4f}")

            self.feature_columns = features
            self.X_train = X_train_scaled
            self.y_train = y_train

            # Save model
            self._save_model()
            return True

        except Exception as e:
            logger.error(f"❌ Model training error: {e}")
            return False

    def predict(self, features_dict: Dict) -> Tuple[float, float]:
        """
        Predict signal (0=SELL, 1=BUY) with confidence.
        Returns: (signal, confidence)
        """
        try:
            # Create feature vector
            X = np.zeros(len(self.feature_columns))
            for i, col in enumerate(self.feature_columns):
                X[i] = features_dict.get(col, 0.0)

            # Scale and predict
            X_scaled = self.scaler.transform(X.reshape(1, -1))
            proba = self.model.predict_proba(X_scaled)[0]
            
            signal = 1 if proba[1] > proba[0] else 0
            confidence = max(proba) * 100

            return signal, confidence

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0, 0.0

    def _save_model(self):
        """Save trained model to disk."""
        try:
            pickle.dump(self.model, open(MODEL_PATH, 'wb'))
            pickle.dump(self.scaler, open(SCALER_PATH, 'wb'))
            logger.info(f"   Model saved: {MODEL_PATH}")
        except Exception as e:
            logger.warning(f"Failed to save model: {e}")

    def load_model(self) -> bool:
        """Load pre-trained model from disk."""
        try:
            if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
                self.model = pickle.load(open(MODEL_PATH, 'rb'))
                self.scaler = pickle.load(open(SCALER_PATH, 'rb'))
                logger.info(f"✅ Model loaded from {MODEL_PATH}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════
#  FEATURE ENGINEERING FOR REAL-TIME DATA
# ═══════════════════════════════════════════════════════════════════

class FeatureGenerator:
    """Generate features for ML prediction from real-time OHLC bars."""

    def __init__(self, lookback: int = 20):
        self.lookback = lookback
        self.prices = []
        self.volumes = []
        self.opens = []
        self.highs = []
        self.lows = []

    def update(self, bar: Dict) -> Optional[Dict]:
        """Update with new bar and return features if ready."""
        self.prices.append(bar.get('close', 0.0))
        self.volumes.append(bar.get('volume', 0))
        self.opens.append(bar.get('open', 0.0))
        self.highs.append(bar.get('high', 0.0))
        self.lows.append(bar.get('low', 0.0))

        # Keep only lookback window
        if len(self.prices) > self.lookback:
            self.prices.pop(0)
            self.volumes.pop(0)
            self.opens.pop(0)
            self.highs.pop(0)
            self.lows.pop(0)

        if len(self.prices) < self.lookback:
            return None  # Not enough data yet

        return self._compute_features()

    def _compute_features(self) -> Dict:
        """Compute all features."""
        prices = np.array(self.prices)
        volumes = np.array(self.volumes)

        features = {
            # Momentum
            'sma_5': np.mean(prices[-5:]),
            'sma_10': np.mean(prices[-10:]),
            'sma_20': np.mean(prices),
            'momentum_5': prices[-1] - prices[-5],
            'momentum_10': prices[-1] - prices[-10],
            'rsi_14': self._compute_rsi(prices, 14),
            'macd': self._compute_macd(prices),
            
            # Volatility
            'volatility': np.std(prices),
            'atr_14': self._compute_atr(14),
            
            # Volume
            'volume_ma': np.mean(volumes),
            'volume_current': volumes[-1],
            'volume_ratio': volumes[-1] / max(np.mean(volumes), 1),
            
            # Price levels
            'high_20': np.max(prices),
            'low_20': np.min(prices),
            'range': np.max(prices) - np.min(prices),
            
            # Trend
            'trend_strength': (prices[-1] - prices[0]) / max(np.std(prices), 0.1),
        }

        return features

    def _compute_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Compute RSI indicator."""
        if len(prices) < period:
            return 50.0
        
        changes = np.diff(prices)
        gains = np.where(changes > 0, changes, 0)
        losses = np.where(changes < 0, -changes, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _compute_macd(self, prices: np.ndarray) -> float:
        """Compute MACD indicator."""
        ema12 = self._compute_ema(prices, 12)
        ema26 = self._compute_ema(prices, 26)
        return ema12 - ema26 if ema12 and ema26 else 0.0

    def _compute_ema(self, prices: np.ndarray, period: int) -> Optional[float]:
        """Compute EMA."""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = price * multiplier + ema * (1 - multiplier)
        
        return ema

    def _compute_atr(self, period: int = 14) -> float:
        """Compute Average True Range."""
        if len(self.highs) < period:
            return 0.0
        
        tr_values = []
        for i in range(len(self.highs)):
            if i == 0:
                tr = self.highs[i] - self.lows[i]
            else:
                tr = max(
                    self.highs[i] - self.lows[i],
                    abs(self.highs[i] - self.prices[i-1]),
                    abs(self.lows[i] - self.prices[i-1])
                )
            tr_values.append(tr)
        
        return np.mean(tr_values[-period:])


# ═══════════════════════════════════════════════════════════════════
#  DHAN PAPER TRADING EXECUTOR
# ═══════════════════════════════════════════════════════════════════

class DhanPaperTrader:
    """Simulate paper trading on Dhan platform."""

    def __init__(self, paper_mode: bool = True):
        self.paper_mode = paper_mode
        self.positions = {}
        self.trades = []
        self.pnl_log = []
        self.capital = 100000.0  # Paper trading capital
        self.current_balance = self.capital
        self.next_order_id = 1000

    async def place_order(self, signal: Dict, current_price: float) -> Optional[Dict]:
        """Place order based on signal."""
        try:
            order_id = self.next_order_id
            self.next_order_id += 1

            action = "BUY" if signal['signal'] == 1 else "SELL"
            quantity = 1
            
            order = {
                "order_id": order_id,
                "symbol": INSTRUMENT,
                "action": action,
                "quantity": quantity,
                "price": current_price,
                "timestamp": datetime.now().isoformat(),
                "confidence": signal.get('confidence', 0.0),
                "status": "EXECUTED" if self.paper_mode else "PENDING",
            }

            if self.paper_mode:
                logger.info(
                    f"📋 [PAPER MODE] Order #{order_id}: {action} {quantity} "
                    f"{INSTRUMENT} @ ₹{current_price:.2f} "
                    f"(Confidence: {signal.get('confidence', 0.0):.1f}%)"
                )
                
                # Update position
                if action == "BUY":
                    self.positions[INSTRUMENT] = {
                        "quantity": quantity,
                        "entry_price": current_price,
                        "entry_time": datetime.now(),
                    }
                elif action == "SELL" and INSTRUMENT in self.positions:
                    pos = self.positions[INSTRUMENT]
                    pnl = (current_price - pos['entry_price']) * quantity
                    pnl_pct = (pnl / (pos['entry_price'] * quantity)) * 100
                    
                    self.pnl_log.append({
                        "entry_price": pos['entry_price'],
                        "exit_price": current_price,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "timestamp": datetime.now(),
                    })
                    
                    logger.info(
                        f"📈 Position closed: PnL = ₹{pnl:.2f} ({pnl_pct:.2f}%)"
                    )
                    del self.positions[INSTRUMENT]
            else:
                logger.info(f"🚀 [LIVE MODE] Submitting order: {order}")

            self.trades.append(order)
            return order

        except Exception as e:
            logger.error(f"Order execution error: {e}")
            return None

    def get_summary(self) -> Dict:
        """Get trading summary."""
        total_pnl = sum(t['pnl'] for t in self.pnl_log)
        total_pnl_pct = (total_pnl / self.capital * 100) if self.capital > 0 else 0
        
        winning_trades = len([t for t in self.pnl_log if t['pnl'] > 0])
        losing_trades = len([t for t in self.pnl_log if t['pnl'] < 0])
        
        return {
            "total_trades": len(self.trades),
            "closed_positions": len(self.pnl_log),
            "open_positions": len(self.positions),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "win_rate": (winning_trades / max(len(self.pnl_log), 1)) * 100 if self.pnl_log else 0,
        }


# ═══════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════

class IntegratedTradingSystem:
    """Complete system: WebSocket → ML → Paper Trading."""

    def __init__(self):
        self.ws_client = AngelOneRealTimeClient()
        self.data_manager = HistoricalDataManager()
        self.model_manager = MLModelManager()
        self.feature_generator = FeatureGenerator()
        self.paper_trader = DhanPaperTrader(paper_mode=PAPER_MODE)
        
        self.features = None
        self.signal_count = 0
        self.min_confidence = 0.65

        # Register callbacks
        self.ws_client.on_tick(self._on_tick)
        self.ws_client.on_bar(self._on_bar)
        self.ws_client.on_connection(self._on_connection)

    async def _on_tick(self, tick: TickData):
        """Handle incoming tick (optional: stream to UI)."""
        pass

    async def _on_bar(self, bar: Dict):
        """Handle completed OHLC bar - generate signal."""
        # Generate features
        features = self.feature_generator.update(bar)
        if not features:
            return  # Need more data

        # Predict signal
        signal_value, confidence = self.model_manager.predict(features)
        
        if confidence >= self.min_confidence * 100:
            self.signal_count += 1
            
            signal = {
                "signal": signal_value,
                "confidence": confidence,
                "features": features,
            }
            
            signal_str = "🟢 BUY" if signal_value == 1 else "🔴 SELL"
            logger.info(
                f"{signal_str} Signal #{self.signal_count} @ ₹{bar['close']:.2f} "
                f"(Confidence: {confidence:.1f}%)"
            )

            # Execute paper trade
            await self.paper_trader.place_order(signal, bar['close'])

    async def _on_connection(self, state: bool):
        """Handle connection state changes."""
        status = "🟢 CONNECTED" if state else "🔴 DISCONNECTED"
        logger.info(f"WebSocket Status: {status}")

    async def initialize(self) -> bool:
        """Initialize system: load data, train model."""
        logger.info("=" * 70)
        logger.info("🔧 SYSTEM INITIALIZATION")
        logger.info("=" * 70)

        # Step 1: Load historical data
        df = self.data_manager.load_data(cutoff_date="2026-03-02")
        if df is None:
            return False

        # Step 2: Get feature columns
        features = self.data_manager.get_features()
        self.features = features
        self.model_manager.feature_columns = features
        logger.info(f"✅ Using {len(features)} features")

        # Step 3: Load or train model
        if not self.model_manager.load_model():
            logger.info("No pre-trained model found. Training new model...")
            if not self.model_manager.train(df, features):
                return False
        
        logger.info("=" * 70)
        logger.info("✅ SYSTEM READY")
        logger.info("=" * 70)
        return True

    async def start(self) -> bool:
        """Start the complete trading system."""
        
        # Initialize
        if not await self.initialize():
            return False

        # Connect WebSocket
        logger.info("\n🔌 Connecting to Angel One WebSocket...")
        if not await self.ws_client.login():
            logger.error("❌ WebSocket login failed")
            return False

        tokens = [{"exchangeTokens": {EXCHANGE: [INSTRUMENT]}}]
        if not await self.ws_client.connect(tokens):
            logger.error("❌ WebSocket connection failed")
            return False

        logger.info("✅ WebSocket connected - listening for signals...")
        logger.info("\n" + "=" * 70)
        logger.info("🚀 TRADING SYSTEM ACTIVE")
        logger.info(f"   Mode: {'📋 PAPER TRADING' if PAPER_MODE else '💰 LIVE TRADING'}")
        logger.info(f"   Instrument: {INSTRUMENT}")
        logger.info(f"   Min Confidence: {self.min_confidence * 100:.0f}%")
        logger.info("=" * 70 + "\n")

        # Listen for signals
        try:
            await self.ws_client.listen()
        except KeyboardInterrupt:
            logger.info("\n⏹️  Shutdown requested")
        finally:
            await self.stop()

    async def stop(self):
        """Gracefully shutdown system."""
        logger.info("\n🛑 Shutting down...")
        await self.ws_client.disconnect()

        # Print summary
        summary = self.paper_trader.get_summary()
        logger.info("\n" + "=" * 70)
        logger.info("📊 SESSION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"WebSocket Ticks: {self.ws_client.tick_count}")
        logger.info(f"OHLC Bars Built: {self.feature_generator.lookback}")
        logger.info(f"Signals Generated: {self.signal_count}")
        logger.info(f"Orders Placed: {summary['total_trades']}")
        logger.info(f"Positions Closed: {summary['closed_positions']}")
        logger.info(f"Win Rate: {summary['win_rate']:.1f}%")
        logger.info(f"Total PnL: ₹{summary['total_pnl']:.2f} ({summary['total_pnl_pct']:+.2f}%)")
        logger.info("=" * 70)


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

async def main():
    """Run complete integrated trading system."""
    system = IntegratedTradingSystem()
    await system.start()


if __name__ == "__main__":
    asyncio.run(main())
