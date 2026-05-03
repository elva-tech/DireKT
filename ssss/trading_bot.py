"""
MCX Silver Futures - Real-Time Automated Trading Bot
====================================================
Fetches live data from Angel One → Predicts signals with ML model → Executes on Dhan.
"""

import os
import sys
import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from pathlib import Path
import pandas as pd
import numpy as np
from collections import deque
from threading import Thread, Event
def _persist_trade_history_event(position_snapshot: dict, lifecycle: str, decision_engine: str) -> None:
    """Append one trade lifecycle row for UI history (JSONL locally, Postgres if DATABASE_URL)."""
    try:
        from trade_history_store import persist_trade_event

        persist_trade_event(position_snapshot, lifecycle, decision_engine)
    except Exception as e:
        log.warning(f"Trade history persist failed: {e}")
import schedule

_handlers = [logging.StreamHandler()]
try:
    _handlers.append(logging.FileHandler("trading_bot.log"))
except OSError:
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_handlers,
    force=True,
)
log = logging.getLogger(__name__)

# Import our modules
from angel_one_connector import AngelOneConnector, RealTimeDataStream
from dhan_trader import DhanTradingClient
from trading_state_machine import EventType, TradeState, TradingStateMachine
from google_sheets_metrics import append_trade_metric
from feature_engineering import (
    add_moving_averages,
    add_rsi,
    add_macd,
    add_bollinger_bands,
    add_atr,
    add_price_features,
    add_volume_features,
    add_oi_features,
    add_entry_signals,
)

# ── CONFIG ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    # Force .env to override any stale process/user env vars.
    load_dotenv(override=True)
except:
    log.warning("python-dotenv not found. Ensure .env variables are set.")

def _env_clean(name: str, default: str) -> str:
    raw = os.getenv(name, default)
    if raw is None:
        return default
    return str(raw).split("#", 1)[0].strip() or default


def _env_float(name: str, default: str) -> float:
    return float(_env_clean(name, default))


def _env_int(name: str, default: str) -> int:
    return int(float(_env_clean(name, default)))


TRADING_SYMBOL = _env_clean('TRADING_SYMBOL', 'SILVER')
TRADING_EXCHANGE = _env_clean('TRADING_EXCHANGE', 'MCX')
MIN_CONFIDENCE = _env_float('MIN_CONFIDENCE', '0.65')
MAX_POSITION_SIZE = _env_int('MAX_POSITION_SIZE', '5')
STOP_LOSS_PCT = _env_float('STOP_LOSS_PCT', '1.5')
PROFIT_TARGET_PCT = _env_float('PROFIT_TARGET_PCT', '2.0')
PAPER_TRADE = _env_clean('PAPER_TRADE_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'y')
FETCH_INTERVAL_SECONDS = _env_int('FETCH_INTERVAL_SECONDS', '5')
MIN_FEATURE_QUOTES = _env_int('MIN_FEATURE_QUOTES', '60')
ATR_STOP_MULTIPLIER = _env_float('ATR_STOP_MULTIPLIER', '1.5')
ATR_TARGET_RR = _env_float('ATR_TARGET_RR', '2.0')
MAX_ATR_PCT_OF_PRICE = _env_float('MAX_ATR_PCT_OF_PRICE', '5.0')
SIGNAL_CONFIRMATION_QUOTES = _env_int('SIGNAL_CONFIRMATION_QUOTES', '3')

# Model path
MODEL_PATH = "best_model_random_forest_2025.pkl"

# Feature set expected by the ML model training pipeline.
# We recreate the same engineered features used to build `mcx_silver_ml_ready.csv`,
# then drop the same excluded columns (see `ml_training.py`).
ML_EXCLUDE_COLS = [
    'trade_date', 'symbol', 'expiry_date',
    'close', 'high', 'low', 'open',
    'return_next_n_pct',
]

ML_FEATURES_ORDER = [
    # Price features
    'close', 'high', 'low', 'open',
    'pct_return', 'candle_body', 'daily_range', 'daily_range_pct',
    'price_in_range',
    'momentum_5', 'momentum_10',
    # Moving averages
    'SMA_10', 'SMA_20', 'SMA_50',
    'EMA_12', 'EMA_26',
    'price_vs_sma20', 'price_vs_sma50',
    # Volatility
    'ATR', 'BB_width', 'BB_pct',
    # Volume
    'volume_lots', 'volume_spike_ratio', 'is_volume_spike',
    'volume_momentum', 'volume_change_MA',
    # Open Interest
    'open_interest', 'OI_change', 'OI_change_pct',
    'OI_momentum', 'price_oi_bullish',
    # Technical indicators
    'RSI', 'MACD', 'MACD_signal',
    # Entry signals
    'rsi_oversold', 'vol_spike', 'oi_increasing',
    'price_near_bb_lower', 'strong_entry_signal',
    # target + return_next_n_pct exist in training dataset, but are excluded from X
    'target', 'return_next_n_pct',
]


class SilverFuturesTradingBot:
    """Main trading bot for MCX silver futures."""
    
    def __init__(
        self,
        *,
        trading_symbol: Optional[str] = None,
        trading_exchange: Optional[str] = None,
        angel_instrument_token: Optional[str] = None,
        decision_engine: str = "ml",
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        min_confidence: Optional[float] = None,
        max_position_size: Optional[int] = None,
        stop_loss_pct: Optional[float] = None,
        profit_target_pct: Optional[float] = None,
    ):
        """Initialize the trading bot."""
        log.info("="*70)
        log.info("🚀 MCX SILVER FUTURES - AUTOMATED TRADING BOT")
        log.info("="*70)
        
        # Instance-level configuration (so the integration service can override per session)
        self.trading_symbol = trading_symbol or TRADING_SYMBOL
        self.trading_exchange = trading_exchange or TRADING_EXCHANGE
        self.angel_instrument_token = (angel_instrument_token or "").strip() or None
        self.decision_engine = (decision_engine or "ml").lower()
        self.user_id = (user_id or "").strip() or None
        self.username = (username or "").strip() or None
        if self.decision_engine not in ("ml", "llm", "hybrid"):
            self.decision_engine = "ml"
        self.min_confidence = float(min_confidence if min_confidence is not None else MIN_CONFIDENCE)
        self.max_position_size = int(max_position_size if max_position_size is not None else MAX_POSITION_SIZE)
        self.stop_loss_pct = float(stop_loss_pct if stop_loss_pct is not None else STOP_LOSS_PCT)
        self.profit_target_pct = float(profit_target_pct if profit_target_pct is not None else PROFIT_TARGET_PCT)

        # Load Angel One SmartAPI credentials
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
            raise RuntimeError(f"Missing credentials: {', '.join(missing)}")
        
        # Initialize connectors
        self.angel_connector = AngelOneConnector(
            angel_client_id, angel_client_secret, angel_api_key,
            angel_totp, angel_password, angel_user_id
        )
        self.dhan_client = DhanTradingClient(
            dhan_access_token, dhan_client_id, paper_trade=PAPER_TRADE
        )
        
        self.model = None
        self.model_feature_names = None
        self.model_scaler = None
        self._llm_engine = None
        if self.decision_engine == "ml":
            self.model = self._load_model()
        elif self.decision_engine == "hybrid":
            log.info("Hybrid engine — ML proposes, LLM verifies before execution")
            self.model = self._load_model()
            from llm_engine import LLMTradingEngine

            self._llm_engine = LLMTradingEngine(
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"),
                min_confidence_pct=self.min_confidence * 100.0,
            )
        else:
            log.info("LLM decision engine — ML model not loaded")
            from llm_engine import LLMTradingEngine
            self._llm_engine = LLMTradingEngine(
                api_key=os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"),
                min_confidence_pct=self.min_confidence * 100.0,
            )
        
        # Data management
        self.data_stream = None
        # Keep enough history for rolling indicators, but allow earlier signal generation.
        self.quote_buffer = deque(maxlen=220)
        
        # Trading state
        self.active_orders = {}
        self.open_position = None
        self.signal_history = []
        self.trade_log = []
        # Runtime activity metrics (for UI visibility)
        self.quote_count = 0
        self.signal_count = 0
        self.last_quote_at = None
        self.last_signal_at = None
        self.last_quote_ltp = None
        self.last_signal_action = None
        # Last raw engine decision (even if it is rejected and no signal is generated)
        self.last_engine_action = None  # BUY/SELL/HOLD or synthetic HOLD
        self.last_engine_confidence = None  # for LLM: 0-100; for ML: 0-1
        self.last_engine_reason = None  # LLM reason text when available
        self.last_engine_reject_reason = None  # why we returned None (no trade)
        self.latest_indicator_snapshot = {}
        self.pending_signal_action = None
        self.pending_signal_count = 0
        self.state_machine = TradingStateMachine(
            entry_pending_timeout_secs=int(os.getenv("TRADING_ENTRY_PENDING_TIMEOUT_SECS", "5") or 5),
            cooldown_secs=int(os.getenv("TRADING_COOLDOWN_SECS", "120") or 120),
        )
        self.consecutive_quote_failures = 0
        self.consecutive_engine_failures = 0
        self.max_quote_failures_before_block = int(os.getenv("MAX_QUOTE_FAILURES_BEFORE_BLOCK", "12") or 12)
        self.max_engine_failures_before_block = int(os.getenv("MAX_ENGINE_FAILURES_BEFORE_BLOCK", "8") or 8)
        
        # Control
        self.running = False
        self.stop_event = Event()
        
        # Configuration
        log.info(f"⚙️  CONFIGURATION:")
        log.info(f"   Angel quote token/symbol: {self.angel_instrument_token or self.trading_symbol}")
        log.info(f"   Order / label symbol: {self.trading_symbol}")
        log.info(f"   Exchange: {self.trading_exchange}")
        log.info(f"   Decision engine: {self.decision_engine.upper()}")
        log.info(f"   Min Confidence: {self.min_confidence*100:.1f}%")
        log.info(f"   Max Position: {self.max_position_size} contracts")
        log.info(f"   SL: -{self.stop_loss_pct}% | TGT: +{self.profit_target_pct}%")
        log.info(f"   Mode: {'📄 PAPER TRADING' if PAPER_TRADE else '💰 LIVE TRADING'}")
        log.info(f"   Fetch Interval: {FETCH_INTERVAL_SECONDS}s")
    
    def _load_model(self):
        """Load trained ML model."""
        if not Path(MODEL_PATH).exists():
            log.error(f"❌ Model not found: {MODEL_PATH}")
            log.error("Run feature_engineering.py and ml_training.py first")
            raise FileNotFoundError(f"ML model not found: {MODEL_PATH}")
        
        with open(MODEL_PATH, 'rb') as f:
            payload = pickle.load(f)

        # Support both raw estimator pickle and wrapped training artifacts:
        # {"model": estimator, "scaler": ..., "feature_names": ...}
        model = payload
        if isinstance(payload, dict):
            candidate = payload.get("model")
            if candidate is not None:
                model = candidate
            feat_names = payload.get("feature_names")
            if isinstance(feat_names, (list, tuple)) and feat_names:
                self.model_feature_names = list(feat_names)
            scaler = payload.get("scaler")
            if scaler is not None and hasattr(scaler, "transform"):
                self.model_scaler = scaler

        if not hasattr(model, "predict_proba"):
            raise TypeError(
                f"Loaded ML artifact does not expose predict_proba (type={type(model).__name__}). "
                "Expected a fitted classifier estimator."
            )
        
        log.info(f"✅ ML model loaded: {MODEL_PATH}")
        return model
    
    def start(self):
        """Start the trading bot."""
        log.info("\n" + "="*70)
        log.info("🟢 STARTING TRADING BOT")
        log.info("="*70)
        
        # Authenticate with Angel One
        if not self.angel_connector.authenticate():
            log.error("❌ Failed to authenticate with Angel One")
            return False
        
        # Initialize external data stream (Angel One) or return None if unavailable
        self.data_stream = RealTimeDataStream(self.angel_connector)
        
        self.running = True
        self.stop_event.clear()
        
        # Start background threads
        fetch_thread = Thread(target=self._fetch_loop, daemon=True)
        fetch_thread.start()
        
        log.info("✅ Trading bot started successfully")
        log.info("Press Ctrl+C to stop")
        
        try:
            while self.running and not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("\n⏹️  Stopping trading bot...")
            self.stop()
    
    def _fetch_loop(self):
        """Continuous data fetching loop."""
        log.info(f"📊 Starting fetch loop (interval: {FETCH_INTERVAL_SECONDS}s)")
        
        quote_count = 0
        signal_count = 0
        
        while self.running and not self.stop_event.is_set():
            try:
                self.state_machine.process_time_events()
                # Fetch latest quote
                quote_id = self.angel_instrument_token or self.trading_symbol
                quote = self.data_stream.fetch_latest(quote_id, self.trading_exchange)
                quote_count += 1
                self.quote_count = quote_count
                
                if quote:
                    self.consecutive_quote_failures = 0
                    log.debug(f"Quote #{quote_count}: {quote}")
                    self.last_quote_at = datetime.now().isoformat()
                    self.last_quote_ltp = float(getattr(quote, 'ltp', 0) or 0)
                    
                    price = float(getattr(quote, 'ltp', 0) or 0)
                    exit_signal = None
                    if self.open_position and price > 0:
                        if self._check_stop_loss(price):
                            exit_signal = {
                                'timestamp': datetime.now().isoformat(),
                                'price': price,
                                'volume': int(getattr(quote, 'volume', 0) or 0),
                                'oi': int(getattr(quote, 'oi', 0) or 0),
                                'confidence': 1.0,
                                'action': 'SELL',
                                'exit_reason': 'STOP_LOSS',
                            }
                        elif self._check_target(price):
                            exit_signal = {
                                'timestamp': datetime.now().isoformat(),
                                'price': price,
                                'volume': int(getattr(quote, 'volume', 0) or 0),
                                'oi': int(getattr(quote, 'oi', 0) or 0),
                                'confidence': 1.0,
                                'action': 'SELL',
                                'exit_reason': 'TAKE_PROFIT',
                            }

                    if exit_signal:
                        self.last_engine_action = 'SELL'
                        self.last_engine_confidence = 1.0
                        self.last_engine_reason = (
                            'Auto exit: stop loss'
                            if exit_signal.get('exit_reason') == 'STOP_LOSS'
                            else 'Auto exit: profit target'
                        )
                        self.last_engine_reject_reason = None
                        signal_count += 1
                        self.signal_count = signal_count
                        log.info(
                            f"Signal #{signal_count} generated (auto {exit_signal.get('exit_reason')})"
                        )
                        self._handle_signal(quote, exit_signal)
                    else:
                        signal = self._generate_signal(quote)
                        if self.last_engine_reject_reason and self.last_engine_reject_reason.startswith("Exception"):
                            self.consecutive_engine_failures += 1
                        else:
                            self.consecutive_engine_failures = 0
                        if self.consecutive_engine_failures >= self.max_engine_failures_before_block:
                            self.state_machine.handle_event(
                                EventType.RISK_BREACH,
                                {"reason": f"Repeated engine failures ({self.consecutive_engine_failures})"},
                            )
                            self.last_engine_reject_reason = (
                                f"System blocked after repeated engine failures ({self.consecutive_engine_failures})"
                            )
                            if self.open_position:
                                self.trigger_emergency_exit("Repeated engine failures")
                            continue
                        if signal:
                            signal_count += 1
                            self.signal_count = signal_count
                            log.info(f"Signal #{signal_count} generated")
                            self._handle_signal(quote, signal)
                        else:
                            self._reset_signal_confirmation()
                            log.debug(f"No signal for quote #{quote_count}")
                else:
                    self.consecutive_quote_failures += 1
                    log.warning(f"Quote #{quote_count} returned None")
                    if self.consecutive_quote_failures >= self.max_quote_failures_before_block:
                        self.state_machine.handle_event(
                            EventType.RISK_BREACH,
                            {"reason": f"Websocket/quote disconnect ({self.consecutive_quote_failures} failures)"},
                        )
                        self.last_engine_reject_reason = (
                            f"System blocked after quote failures ({self.consecutive_quote_failures})"
                        )
                        if self.open_position:
                            self.trigger_emergency_exit("Quote disconnect")
                
                time.sleep(FETCH_INTERVAL_SECONDS)
                
            except Exception as e:
                log.error(f"Error in fetch loop: {e}")
                import traceback
                log.debug(traceback.format_exc())
                self.consecutive_quote_failures += 1
                time.sleep(5)  # Back off on error
    
    def _append_quote_to_buffer(self, quote) -> None:
        sym_label = (self.trading_symbol or "SILVER").replace(" ", "")[:32]
        self.quote_buffer.append({
            'trade_date': pd.to_datetime(quote.timestamp),
            'symbol': sym_label,
            'expiry_date': 'NA',
            'open': float(getattr(quote, 'open_price', 0) or 0),
            'high': float(getattr(quote, 'high', 0) or 0),
            'low': float(getattr(quote, 'low', 0) or 0),
            'close': float(getattr(quote, 'ltp', 0) or 0),
            'volume_lots': float(getattr(quote, 'volume', 0) or 0),
            'open_interest': float(getattr(quote, 'oi', 0) or 0),
        })

    def _engineered_last_row(self, quote):
        """Return last row of engineered features or None if not ready."""
        self._append_quote_to_buffer(quote)
        if len(self.quote_buffer) < MIN_FEATURE_QUOTES:
            return None

        df = pd.DataFrame(list(self.quote_buffer))
        df = add_moving_averages(df)
        df = add_rsi(df)
        df = add_macd(df)
        df = add_bollinger_bands(df)
        df = add_atr(df)
        df = add_price_features(df)
        df = add_volume_features(df)
        df = add_oi_features(df)
        df = add_entry_signals(df)
        df = df.replace([np.inf, -np.inf], np.nan)
        return df.iloc[-1], df

    def _engineered_row_from_buffer_only(self):
        """Same as _engineered_last_row but without appending (use after ML already consumed this quote)."""
        if len(self.quote_buffer) < MIN_FEATURE_QUOTES:
            return None
        df = pd.DataFrame(list(self.quote_buffer))
        df = add_moving_averages(df)
        df = add_rsi(df)
        df = add_macd(df)
        df = add_bollinger_bands(df)
        df = add_atr(df)
        df = add_price_features(df)
        df = add_volume_features(df)
        df = add_oi_features(df)
        df = add_entry_signals(df)
        df = df.replace([np.inf, -np.inf], np.nan)
        return df.iloc[-1], df

    def _ohlc_and_indicators(self, quote, last) -> Tuple[Dict, Dict]:
        ohlc_data = {
            'open': float(last.get('open', getattr(quote, 'open_price', 0) or 0) or 0),
            'high': float(last.get('high', getattr(quote, 'high', 0) or 0) or 0),
            'low': float(last.get('low', getattr(quote, 'low', 0) or 0) or 0),
            'close': float(last.get('close', quote.ltp) or 0),
            'volume': int(float(last.get('volume_lots', getattr(quote, 'volume', 0) or 0) or 0)),
        }
        close = ohlc_data['close'] or float(quote.ltp)
        sma20 = float(last.get('SMA_20', close) or close)
        indicators = {
            'RSI': float(last.get('RSI', 50) or 50),
            'MACD': float(last.get('MACD', 0) or 0),
            'ATR': float(last.get('ATR', 0) or 0),
            'SMA_20': sma20,
            'EMA_12': float(last.get('EMA_12', close) or close),
            'volume_ratio': float(last.get('volume_spike_ratio', 1.0) or 1.0),
            'trend_strength': float(last.get('price_vs_sma20', 0) or 0) / 100.0,
        }
        return ohlc_data, indicators

    def _compute_exit_levels(self, entry_price: float, signal: Dict) -> Tuple[float, float, str]:
        """Pick dynamic stop-loss/target from signal, ATR/trend, then fixed pct fallback."""
        sig_sl = float(signal.get('stop_loss') or 0)
        sig_target = float(signal.get('target') or 0)
        if 0 < sig_sl < entry_price and sig_target > entry_price:
            return sig_sl, sig_target, "signal"

        indicators = self.latest_indicator_snapshot or {}
        atr = float(indicators.get('ATR') or 0)
        trend = float(indicators.get('trend_strength') or 0)
        if atr > 0:
            atr_pct = (atr / entry_price * 100.0) if entry_price > 0 else 0.0
            if 0 < atr_pct <= MAX_ATR_PCT_OF_PRICE:
                rr = ATR_TARGET_RR
                if trend > 0.25:
                    rr += 0.5
                elif trend < -0.25:
                    rr = max(1.2, rr - 0.5)
                risk_distance = atr * ATR_STOP_MULTIPLIER
                sl_price = max(0.01, entry_price - risk_distance)
                target_price = entry_price + (risk_distance * rr)
                if sl_price > 0 and sl_price < entry_price and target_price > entry_price:
                    return sl_price, target_price, f"atr(rr={rr:.2f},atr_pct={atr_pct:.2f})"

        sl_price = entry_price * (1 - self.stop_loss_pct/100)
        target_price = entry_price * (1 + self.profit_target_pct/100)
        return sl_price, target_price, "fixed_pct"

    def _reset_signal_confirmation(self) -> None:
        self.pending_signal_action = None
        self.pending_signal_count = 0

    def _confirmed_signal_ready(self, signal: Dict) -> bool:
        action = str(signal.get('action') or '').upper()
        if action not in ('BUY', 'SELL'):
            self._reset_signal_confirmation()
            return False
        if self.pending_signal_action == action:
            self.pending_signal_count += 1
        else:
            self.pending_signal_action = action
            self.pending_signal_count = 1
        needed = max(1, SIGNAL_CONFIRMATION_QUOTES)
        if self.pending_signal_count < needed:
            self.last_engine_reject_reason = f"Awaiting {action} confirmation ({self.pending_signal_count}/{needed})"
            return False
        self._reset_signal_confirmation()
        return True

    def _generate_signal(self, quote) -> Optional[Dict]:
        if self.decision_engine == "llm":
            return self._generate_signal_llm(quote)
        if self.decision_engine == "hybrid":
            return self._generate_signal_hybrid(quote)
        return self._generate_signal_ml(quote)

    def _generate_signal_hybrid(self, quote) -> Optional[Dict]:
        """
        ML proposes BUY/SELL; LLM verifies. Only if LLM agrees with same action and
        meets confidence threshold does a signal fire. SL/TP auto-exit unchanged.
        """
        try:
            ml_sig = self._generate_signal_ml(quote)
            if not ml_sig:
                return None
            out = self._engineered_row_from_buffer_only()
            if out is None:
                self.last_engine_reject_reason = "Hybrid: engineered row unavailable after ML"
                return None
            last, _ = out
            ohlc_data, indicators = self._ohlc_and_indicators(quote, last)
            self.latest_indicator_snapshot = dict(indicators)
            position = None
            if self.open_position:
                position = {
                    'side': 'LONG',
                    'entry_price': self.open_position.get('entry_price'),
                    'quantity': self.open_position.get('quantity'),
                }
            ml_action = str(ml_sig.get('action') or '').upper()
            ml_conf_pct = float(ml_sig.get('confidence') or 0) * 100.0
            verify = self._llm_engine.verify_ml_proposal(
                ml_action=ml_action,
                ml_confidence_pct=ml_conf_pct,
                ohlc_data=ohlc_data,
                indicators=indicators,
                position=position,
            )
            if not verify:
                self.last_engine_action = "HOLD"
                self.last_engine_confidence = None
                self.last_engine_reason = None
                self.last_engine_reject_reason = "Hybrid LLM verify failed (API/parse)"
                return None
            if not verify.get("agree"):
                self.last_engine_action = "HOLD"
                self.last_engine_confidence = float(verify.get("confidence", 0)) / 100.0
                self.last_engine_reason = verify.get("reason") or "LLM disagreed with ML"
                self.last_engine_reject_reason = (
                    f"LLM veto: {verify.get('reason') or 'DISAGREE'} "
                    f"(LLM wanted {verify.get('action')})"
                )
                return None
            vconf = float(verify.get("confidence", 0)) / 100.0
            if vconf < self.min_confidence:
                self.last_engine_action = "HOLD"
                self.last_engine_confidence = vconf
                self.last_engine_reason = verify.get("reason")
                self.last_engine_reject_reason = (
                    f"LLM verify confidence below threshold ({vconf:.3f}<{self.min_confidence:.3f})"
                )
                return None
            # Both ML and LLM agree: surface hybrid context in metrics
            self.last_engine_action = ml_action
            self.last_engine_confidence = min(float(ml_sig.get('confidence', 0)), vconf)
            self.last_engine_reason = verify.get("reason") or "LLM verified ML"
            self.last_engine_reject_reason = None
            out_sig = dict(ml_sig)
            out_sig["confidence"] = float(self.last_engine_confidence)
            out_sig["hybrid_verified"] = True
            return out_sig
        except Exception as e:
            self.last_engine_action = "HOLD"
            self.last_engine_confidence = None
            self.last_engine_reason = None
            self.last_engine_reject_reason = f"Exception hybrid signal: {e}"
            log.debug(f"Error generating hybrid signal: {e}")
            return None

    def _generate_signal_ml(self, quote) -> Optional[Dict]:
        """
        Generate BUY/SELL signal using the trained ML model (live Angel quotes).
        """
        try:
            out = self._engineered_last_row(quote)
            if out is None:
                # Not ready: keep UI explainable instead of returning silent None.
                self.last_engine_action = "HOLD"
                have = len(self.quote_buffer)
                self.last_engine_confidence = None
                self.last_engine_reason = None
                self.last_engine_reject_reason = f"Engine features not ready (have {have}/{MIN_FEATURE_QUOTES})"
                return None
            last, df = out
            _, indicators = self._ohlc_and_indicators(quote, last)
            self.latest_indicator_snapshot = dict(indicators)

            feature_cols = [
                f
                for f in ML_FEATURES_ORDER
                if f != 'target' and f in df.columns and f not in ML_EXCLUDE_COLS
            ]
            if not feature_cols:
                self.last_engine_action = "HOLD"
                self.last_engine_confidence = None
                self.last_engine_reason = None
                self.last_engine_reject_reason = "No usable ML feature columns found"
                return None

            # Some live-engineered indicators can briefly produce NaN/inf (e.g. zero OI/volume windows).
            # Sanitize using rolling history and a final zero-fill fallback so ML can still infer.
            feature_frame = df[feature_cols].copy()
            feature_frame = feature_frame.replace([np.inf, -np.inf], np.nan).ffill().bfill()
            last_features = pd.to_numeric(feature_frame.iloc[-1], errors='coerce')

            # Prefer training-time feature order from model artifact when available.
            if self.model_feature_names:
                aligned = {
                    name: float(last_features.get(name, 0.0) or 0.0)
                    for name in self.model_feature_names
                }
                feature_values = np.array([aligned[name] for name in self.model_feature_names], dtype=float)
            else:
                if last_features.isna().any():
                    last_features = last_features.fillna(0.0)
                    self.last_engine_reject_reason = "NaN in features auto-filled (0.0 fallback)"
                feature_values = last_features.astype(float).values

            # Final numeric sanitation
            feature_values = np.nan_to_num(feature_values, nan=0.0, posinf=0.0, neginf=0.0)

            # Align with estimator expected dimensionality.
            expected = int(getattr(self.model, "n_features_in_", 0) or 0)
            if expected > 0 and feature_values.shape[0] != expected:
                got = int(feature_values.shape[0])
                if got > expected:
                    feature_values = feature_values[:expected]
                    self.last_engine_reject_reason = f"Feature vector truncated ({got}->{expected})"
                else:
                    feature_values = np.pad(feature_values, (0, expected - got), mode='constant', constant_values=0.0)
                    self.last_engine_reject_reason = f"Feature vector padded ({got}->{expected})"

            x_input = feature_values.reshape(1, -1)
            if self.model_scaler is not None:
                try:
                    x_input = self.model_scaler.transform(x_input)
                except Exception:
                    # Keep model running if scaler shape/check fails.
                    self.last_engine_reject_reason = "Scaler transform failed; using raw feature vector"

            proba = self.model.predict_proba(x_input)[0]
            classes = getattr(self.model, "classes_", None)

            if classes is not None and 1 in classes:
                idx = list(classes).index(1)
                p_buy = float(proba[idx])
            else:
                p_buy = float(proba[-1])

            if p_buy >= self.min_confidence:
                action = 'BUY'
                confidence = p_buy
            elif p_buy <= (1.0 - self.min_confidence):
                action = 'SELL'
                confidence = 1.0 - p_buy
            else:
                # Neutral zone: not strong enough to generate a signal.
                self.last_engine_action = 'HOLD'
                self.last_engine_confidence = float(p_buy)
                self.last_engine_reason = None
                self.last_engine_reject_reason = f"Neutral ML zone (p_buy={p_buy:.3f}, min_confidence={self.min_confidence:.3f})"
                return None

            # Store last decision attempt
            self.last_engine_action = action
            self.last_engine_confidence = float(confidence)
            self.last_engine_reason = None
            self.last_engine_reject_reason = None

            return {
                'timestamp': datetime.now().isoformat(),
                'price': float(quote.ltp),
                'volume': int(getattr(quote, 'volume', 0) or 0),
                'oi': int(getattr(quote, 'oi', 0) or 0),
                'confidence': float(confidence),
                'action': action,
            }

        except Exception as e:
            self.last_engine_action = "HOLD"
            self.last_engine_confidence = None
            self.last_engine_reason = None
            self.last_engine_reject_reason = f"Exception generating ML signal: {e}"
            log.debug(f"Error generating ML signal: {e}")
            return None

    def _generate_signal_llm(self, quote) -> Optional[Dict]:
        """
        Same live OHLC/feature pipeline; LLM decides entry / exit (paper execution unchanged).
        """
        try:
            out = self._engineered_last_row(quote)
            if out is None:
                self.last_engine_action = "HOLD"
                self.last_engine_confidence = None
                self.last_engine_reason = None
                self.last_engine_reject_reason = f"Engine features not ready (have {len(self.quote_buffer)}/{MIN_FEATURE_QUOTES})"
                return None
            last, _df = out

            ohlc_data = {
                'open': float(last.get('open', getattr(quote, 'open_price', 0) or 0) or 0),
                'high': float(last.get('high', getattr(quote, 'high', 0) or 0) or 0),
                'low': float(last.get('low', getattr(quote, 'low', 0) or 0) or 0),
                'close': float(last.get('close', quote.ltp) or 0),
                'volume': int(float(last.get('volume_lots', getattr(quote, 'volume', 0) or 0) or 0)),
            }
            close = ohlc_data['close'] or float(quote.ltp)
            sma20 = float(last.get('SMA_20', close) or close)
            indicators = {
                'RSI': float(last.get('RSI', 50) or 50),
                'MACD': float(last.get('MACD', 0) or 0),
                'ATR': float(last.get('ATR', 0) or 0),
                'SMA_20': sma20,
                'EMA_12': float(last.get('EMA_12', close) or close),
                'volume_ratio': float(last.get('volume_spike_ratio', 1.0) or 1.0),
                'trend_strength': float(last.get('price_vs_sma20', 0) or 0) / 100.0,
            }
            self.latest_indicator_snapshot = dict(indicators)

            position = None
            if self.open_position:
                position = {
                    'side': 'LONG',
                    'entry_price': self.open_position.get('entry_price'),
                    'quantity': self.open_position.get('quantity'),
                }

            decision = self._llm_engine.generate_decision(ohlc_data, indicators, position)
            # Record raw LLM output, even if it doesn't become a trading signal.
            self.last_engine_action = decision.action
            self.last_engine_confidence = float(decision.confidence)
            self.last_engine_reason = decision.reason
            self.last_engine_reject_reason = None
            if decision.action == 'HOLD':
                self.last_engine_reject_reason = (
                    decision.reason or "LLM chose HOLD (no BUY/SELL signal)"
                )
                return None

            conf = decision.confidence / 100.0
            if conf < self.min_confidence:
                self.last_engine_reject_reason = f"LLM confidence below threshold ({conf:.3f}<{self.min_confidence:.3f})"
                return None

            if decision.action == 'SELL' and not self.open_position:
                self.last_engine_reject_reason = "SELL ignored (no open position)"
                return None

            return {
                'timestamp': datetime.now().isoformat(),
                'price': float(quote.ltp),
                'volume': int(getattr(quote, 'volume', 0) or 0),
                'oi': int(getattr(quote, 'oi', 0) or 0),
                'confidence': float(conf),
                'action': decision.action,
                'stop_loss': float(decision.stop_loss or 0),
                'target': float(decision.target or 0),
            }

        except Exception as e:
            self.last_engine_action = "HOLD"
            self.last_engine_confidence = None
            self.last_engine_reason = None
            self.last_engine_reject_reason = f"Exception generating LLM signal: {e}"
            log.debug(f"Error generating LLM signal: {e}")
            return None
    
    def _handle_signal(self, quote, signal: Dict):
        """Process trading signal."""
        self.state_machine.process_time_events()
        log.info(f"\n🔔 SIGNAL GENERATED")
        log.info(f"   Price: ₹{quote.ltp:,.2f}")
        log.info(f"   Volume: {quote.volume:,}")
        log.info(f"   OI: {quote.oi:,}")
        log.info(f"   Action: {signal['action']}")
        log.info(f"   Confidence: {signal['confidence']*100:.1f}%")
        
        # Store signal
        self.signal_history.append(signal)
        self.last_signal_at = datetime.now().isoformat()
        self.last_signal_action = signal.get('action')
        
        # Check confidence threshold
        if signal['confidence'] < self.min_confidence:
            log.info(f"⏭️  Confidence below threshold ({self.min_confidence*100:.1f}%)")
            self._reset_signal_confirmation()
            return

        is_entry = signal['action'] == 'BUY' and not self.open_position
        is_exit = signal['action'] == 'SELL' and self.open_position
        is_auto_exit = bool(signal.get('exit_reason'))
        if (is_entry or is_exit) and not is_auto_exit and not self._confirmed_signal_ready(signal):
            log.info(f"⏭️  Waiting for confirmation before executing {signal['action']}")
            return
        
        # Execute trade
        if signal['action'] == 'BUY' and not self.open_position:
            self._execute_buy(quote, signal)
        
        elif signal['action'] == 'SELL' and self.open_position:
            self._execute_sell(quote, signal)
    
    def _execute_buy(self, quote, signal: Dict):
        """Execute BUY order."""
        try:
            qty = self.max_position_size
            entry_price = quote.ltp
            sl_price, target_price, exit_model = self._compute_exit_levels(entry_price, signal)
            sm_result = self.state_machine.handle_event(
                EventType.LLM_ENTRY_SIGNAL,
                {
                    'contract': self.trading_symbol,
                    'lot_size': qty,
                    'stop_loss': sl_price,
                    'target': target_price,
                    'direction': 'LONG',
                },
            )
            if sm_result.get('status') != 'accepted':
                self.last_engine_reject_reason = f"State machine blocked entry: {sm_result.get('reason', sm_result.get('status'))}"
                return
            
            log.info(f"\n🔵 EXECUTING BUY ORDER")
            log.info(f"   Quantity: {qty} contracts")
            log.info(f"   Entry: ₹{entry_price:,.2f}")
            log.info(f"   Exit model: {exit_model}")
            log.info(f"   SL: ₹{sl_price:,.2f}")
            log.info(f"   Target: ₹{target_price:,.2f}")
            
            # Place order
            order = self.dhan_client.place_order(
                symbol=self.trading_symbol,
                quantity=qty,
                side='BUY',
                price=entry_price,
                exchange=self.trading_exchange,
                order_type='MARKET',
                sl_price=sl_price,
                target_price=target_price
            )
            
            if order:
                self.state_machine.handle_event(
                    EventType.ORDER_FILLED,
                    {'fill_price': float(entry_price)},
                )
                self.open_position = {
                    'order_id': order.order_id,
                    'trade_id': self.state_machine.current_trade.id if self.state_machine.current_trade else None,
                    'symbol': self.trading_symbol,
                    'quantity': qty,
                    'user_id': self.user_id,
                    'username': self.username,
                    'entry_price': entry_price,
                    'sl_price': sl_price,
                    'target_price': target_price,
                    'exit_model': exit_model,
                    'timestamp': datetime.now(),
                    'status': 'OPEN'
                }
                
                self.active_orders[order.order_id] = order
                self.trade_log.append(self.open_position)
                _persist_trade_history_event(self.open_position, "OPEN", self.decision_engine)
                
                log.info(f"✅ BUY order executed: {order.order_id}")
            else:
                self.state_machine.handle_event(
                    EventType.ORDER_REJECTED,
                    {'reason': 'Broker order placement failed'},
                )
        
        except Exception as e:
            self.state_machine.handle_event(
                EventType.ORDER_REJECTED,
                {'reason': str(e)},
            )
            log.error(f"❌ Error executing BUY: {e}")
    
    def _execute_sell(self, quote, signal: Dict):
        """Execute SELL order to close position."""
        if not self.open_position:
            return
        
        try:
            qty = self.open_position['quantity']
            exit_price = quote.ltp
            entry_price = self.open_position['entry_price']
            pnl = (exit_price - entry_price) * qty
            pnl_pct = (pnl / (entry_price * qty)) * 100
            exit_reason = str(signal.get('exit_reason') or 'LLM_EXIT')

            if exit_reason == 'STOP_LOSS':
                sm_result = self.state_machine.handle_event(
                    EventType.STOPLOSS_HIT,
                    {'sl_price': float(exit_price)},
                )
            else:
                sm_result = self.state_machine.handle_event(
                    EventType.LLM_EXIT_SIGNAL,
                    {'exit_price': float(exit_price), 'reason': exit_reason},
                )
            if sm_result.get('status') not in ('exit_pending', 'closed'):
                self.last_engine_reject_reason = f"State machine blocked exit: {sm_result.get('reason', sm_result.get('status'))}"
                return
            
            log.info(f"\n🔴 CLOSING POSITION")
            log.info(f"   Exit Price: ₹{exit_price:,.2f}")
            log.info(f"   P&L: ₹{pnl:,.2f} ({pnl_pct:+.2f}%)")
            
            # Place sell order
            order = self.dhan_client.place_order(
                symbol=self.trading_symbol,
                quantity=qty,
                side='SELL',
                price=exit_price,
                exchange=self.trading_exchange,
                order_type='MARKET'
            )
            
            if order:
                if exit_reason != 'STOP_LOSS':
                    self.state_machine.handle_event(
                        EventType.ORDER_FILLED,
                        {'fill_price': float(exit_price)},
                    )
                self.open_position['status'] = 'CLOSED'
                self.open_position['exit_price'] = exit_price
                self.open_position['pnl'] = pnl
                self.open_position['pnl_pct'] = pnl_pct
                self.open_position['close_timestamp'] = datetime.now()
                self.open_position['exit_reason'] = exit_reason
                _persist_trade_history_event(self.open_position, "CLOSED", self.decision_engine)
                self._append_google_sheets_metrics(self.open_position)
                
                log.info(f"✅ Position closed: {order.order_id}")
                self.open_position = None
            else:
                self.state_machine.handle_event(
                    EventType.ORDER_REJECTED,
                    {'reason': 'Broker exit order placement failed'},
                )
        
        except Exception as e:
            self.state_machine.handle_event(
                EventType.ORDER_REJECTED,
                {'reason': str(e)},
            )
            log.error(f"❌ Error executing SELL: {e}")
    
    def _check_stop_loss(self, current_price: float) -> bool:
        """Check if stop-loss is triggered."""
        if not self.open_position:
            return False
        
        if current_price <= self.open_position['sl_price']:
            log.warning(f"⚠️  STOP LOSS TRIGGERED at ₹{current_price}")
            return True
        
        return False
    
    def _check_target(self, current_price: float) -> bool:
        """Check if profit target is reached."""
        if not self.open_position:
            return False
        
        if current_price >= self.open_position['target_price']:
            log.info(f"✅ PROFIT TARGET REACHED at ₹{current_price}")
            return True
        
        return False
    
    def stop(self):
        """Stop the trading bot gracefully."""
        log.info("\n⏹️  Shutting down...")
        self.running = False
        self.stop_event.set()
        
        # Export data
        self.export_session_data()
        
        log.info("✅ Trading bot stopped")
    
    def export_session_data(self):
        """Export trading session data to files."""
        try:
            # Export signals
            with open('session_signals.json', 'w') as f:
                json.dump(self.signal_history, f, indent=2)
            
            # Export trades
            with open('session_trades.json', 'w') as f:
                json.dump(self.trade_log, f, indent=2, default=str)
            
            # Export from connectors
            self.data_stream.export_history('session_price_history.json')
            self.dhan_client.export_trades('session_order_history.json')
            
            log.info("\n📊 Session data exported:")
            log.info(f"   - session_signals.json ({len(self.signal_history)} signals)")
            log.info(f"   - session_trades.json ({len(self.trade_log)} trades)")
            log.info(f"   - session_price_history.json")
            log.info(f"   - session_order_history.json")
            
        except Exception as e:
            log.error(f"Error exporting data: {e}")

    def trigger_emergency_exit(self, reason: str = "operator_emergency") -> dict:
        """Force-close the open position at market and block the state machine."""
        if self.open_position:
            try:
                qty = int(self.open_position.get('quantity') or 0)
                exit_price = float(self.last_quote_ltp or self.open_position.get('entry_price') or 0)
                order = self.dhan_client.place_order(
                    symbol=self.trading_symbol,
                    quantity=qty,
                    side='SELL',
                    price=exit_price,
                    exchange=self.trading_exchange,
                    order_type='MARKET'
                )
                if order:
                    entry_price = float(self.open_position.get('entry_price') or 0)
                    pnl = (exit_price - entry_price) * qty
                    pnl_pct = (pnl / (entry_price * qty)) * 100 if entry_price > 0 and qty > 0 else 0.0
                    self.open_position['status'] = 'CLOSED'
                    self.open_position['exit_price'] = exit_price
                    self.open_position['pnl'] = pnl
                    self.open_position['pnl_pct'] = pnl_pct
                    self.open_position['close_timestamp'] = datetime.now()
                    self.open_position['exit_reason'] = reason
                    _persist_trade_history_event(self.open_position, "CLOSED", self.decision_engine)
                    self._append_google_sheets_metrics(self.open_position)
                    self.open_position = None
            except Exception as e:
                log.error(f"Emergency exit order failed: {e}")
        return self.state_machine.handle_event(
            EventType.EMERGENCY_EXIT,
            {"reason": reason, "exit_price": float(self.last_quote_ltp or 0)},
        )

    def manual_reset_state_machine(self) -> dict:
        """Manual reset for BLOCKED state."""
        return self.state_machine.handle_event(EventType.MANUAL_RESET, {})

    def _append_google_sheets_metrics(self, closed_position: Dict) -> None:
        """Send one CLOSED trade row to Google Sheets metrics tab."""
        try:
            closed = [t for t in self.trade_log if str(t.get('status') or '').upper() == 'CLOSED']
            wins = sum(1 for t in closed if float(t.get('pnl') or 0) > 0)
            winrate_pct = (wins / len(closed) * 100.0) if closed else 0.0
            pnl = float(closed_position.get('pnl') or 0.0)
            payload = {
                "engine": self.decision_engine,
                "winrate": round(winrate_pct, 4),
                "profit": round(pnl, 6) if pnl > 0 else 0.0,
                "loss": round(abs(pnl), 6) if pnl < 0 else 0.0,
                "entry_price": float(closed_position.get('entry_price') or 0.0),
                "exit_price": float(closed_position.get('exit_price') or 0.0),
                "reasons": str(closed_position.get('exit_reason') or 'LLM_EXIT'),
                "trade_id": str(closed_position.get('trade_id') or closed_position.get('order_id') or ''),
                "execution_time": str(closed_position.get('close_timestamp') or datetime.now().isoformat()),
            }
            ok = append_trade_metric(payload, logger=log)
            if ok:
                log.info("📤 Trade metrics pushed to Google Sheets")
        except Exception as e:
            log.warning(f"Sheets metrics payload error: {e}")
    
    def get_summary(self) -> Dict:
        """Get trading session summary."""
        total_trades = len(self.trade_log)
        closed_trades = sum(1 for t in self.trade_log if t['status'] == 'CLOSED')
        winning_trades = sum(1 for t in self.trade_log if t.get('pnl', 0) > 0)
        total_pnl = sum(t.get('pnl', 0) for t in self.trade_log)
        
        return {
            'total_trades': total_trades,
            'closed_trades': closed_trades,
            'winning_trades': winning_trades,
            'total_pnl': total_pnl,
            'win_rate': winning_trades / closed_trades if closed_trades > 0 else 0,
            'signals_generated': len(self.signal_history)
        }

    def get_runtime_metrics(self) -> Dict:
        """Live runtime metrics for UI monitoring."""
        closed_trades = [t for t in self.trade_log if t.get('status') == 'CLOSED']
        realized_pnl = float(sum(float(t.get('pnl', 0) or 0) for t in closed_trades))
        entries_count = int(len(self.trade_log))
        exits_count = int(len(closed_trades))

        unrealized_pnl = 0.0
        open_entry_price = None
        open_sl_price = None
        open_target_price = None
        open_qty = 0
        price_change_since_entry = 0.0
        if self.open_position:
            open_entry_price = float(self.open_position.get('entry_price') or 0)
            open_sl_price = float(self.open_position.get('sl_price') or 0)
            open_target_price = float(self.open_position.get('target_price') or 0)
            open_qty = int(self.open_position.get('quantity') or 0)
            mkt = float(self.last_quote_ltp or 0)
            if open_entry_price > 0 and open_qty > 0 and mkt > 0:
                unrealized_pnl = (mkt - open_entry_price) * open_qty
                price_change_since_entry = mkt - open_entry_price

        total_pnl = realized_pnl + unrealized_pnl
        sm = self.state_machine.snapshot()
        return {
            'engine': self.decision_engine,
            'trade_state': sm.get('state'),
            'block_reason': sm.get('block_reason'),
            'state_machine_trade': sm.get('current_trade'),
            'state_machine_history_count': sm.get('history_count'),
            'cooldown_remaining_secs': sm.get('cooldown_remaining_secs'),
            'consecutive_quote_failures': int(self.consecutive_quote_failures),
            'consecutive_engine_failures': int(self.consecutive_engine_failures),
            'running': bool(self.running),
            'quote_count': int(self.quote_count),
            'signal_count': int(self.signal_count),
            'last_quote_at': self.last_quote_at,
            'last_signal_at': self.last_signal_at,
            'last_quote_ltp': self.last_quote_ltp,
            'last_signal_action': self.last_signal_action,
            'last_engine_action': self.last_engine_action,
            'last_engine_confidence': self.last_engine_confidence,
            'last_engine_reason': self.last_engine_reason,
            'last_engine_reject_reason': self.last_engine_reject_reason,
            'open_position': bool(self.open_position),
            'open_entry_price': open_entry_price,
            'open_sl_price': open_sl_price,
            'open_target_price': open_target_price,
            'open_quantity': open_qty,
            'price_change_since_entry': round(price_change_since_entry, 2),
            'entries_count': entries_count,
            'exits_count': exits_count,
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_pnl': round(total_pnl, 2),
        }


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    
    # Create and start bot
    bot = SilverFuturesTradingBot()
    bot.start()
    
    # Print summary on exit
    summary = bot.get_summary()
    log.info("\n" + "="*70)
    log.info("📊 SESSION SUMMARY")
    log.info("="*70)
    log.info(f"Total Trades: {summary['total_trades']}")
    log.info(f"Closed Trades: {summary['closed_trades']}")
    log.info(f"Winning Trades: {summary['winning_trades']}")
    log.info(f"Win Rate: {summary['win_rate']*100:.1f}%")
    log.info(f"Total P&L: ₹{summary['total_pnl']:,.2f}")
    log.info(f"Signals Generated: {summary['signals_generated']}")
