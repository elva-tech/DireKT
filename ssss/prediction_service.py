"""
MCX Silver Futures - Real-time Entry Signal Prediction
======================================================
Use the trained model to generate trading signals for new data.
"""

import pandas as pd
import numpy as np
import pickle
from sklearn.preprocessing import StandardScaler
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

MODEL_PATH = "best_model_random_forest.pkl"

class SilverTradingSignals:
    """Generate trading signals using trained ML model."""
    
    def __init__(self, model_path: str):
        """Load trained model."""
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        self.scaler = StandardScaler()  # Note: you'll need to save fitted scaler in production
        log.info(f"✅ Model loaded from {model_path}")
    
    def get_entry_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict entry signals for new data with technical indicators.
        
        Input: DataFrame with engineered features
        Output: DataFrame with BUY/NO_TRADE signals and probabilities
        """
        
        # Select same features used in training
        FEATURE_COLS = [
            'pct_return', 'candle_body', 'daily_range', 'daily_range_pct',
            'price_in_range', 'momentum_5', 'momentum_10',
            'SMA_10', 'SMA_20', 'SMA_50', 'EMA_12', 'EMA_26',
            'price_vs_sma20', 'price_vs_sma50',
            'ATR', 'BB_width', 'BB_pct',
            'volume_lots', 'volume_spike_ratio', 'is_volume_spike',
            'volume_momentum', 'volume_change_MA',
            'open_interest', 'OI_change', 'OI_change_pct',
            'OI_momentum', 'price_oi_bullish',
            'RSI', 'MACD', 'MACD_signal',
            'rsi_oversold', 'vol_spike', 'oi_increasing',
            'price_near_bb_lower', 'strong_entry_signal'
        ]
        
        # Filter to available features
        available_features = [f for f in FEATURE_COLS if f in df.columns]
        X = df[available_features].copy()
        
        # Handle missing values
        X = X.fillna(X.median())
        
        # Make predictions
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)[:, 1]
        
        # Create results dataframe
        results = df[['trade_date', 'symbol', 'expiry_date', 'close', 'volume_lots', 
                      'open_interest']].copy()
        results['signal'] = predictions
        results['signal_label'] = results['signal'].map({1: 'BUY', 0: 'NO_TRADE'})
        results['confidence'] = probabilities
        results['confidence_pct'] = (probabilities * 100).round(2)
        
        return results
    
    def filter_high_confidence_signals(self, signals_df: pd.DataFrame, 
                                      min_confidence: float = 0.6) -> pd.DataFrame:
        """Filter signals by minimum confidence level."""
        high_conf = signals_df[
            (signals_df['signal'] == 1) & 
            (signals_df['confidence'] >= min_confidence)
        ]
        return high_conf.sort_values('confidence', ascending=False)
    
    def find_rule_based_entries(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Find entries using rule-based signals:
        RSI oversold + Volume spike + OI increasing
        """
        strong_signals = df[df['strong_entry_signal'] == 1].copy()
        
        if len(strong_signals) > 0:
            strong_signals['entry_reason'] = 'RSI<30 + Vol.spike + OI↑'
            return strong_signals[['trade_date', 'symbol', 'close', 'volume_lots', 
                                  'open_interest', 'RSI', 'entry_reason']]
        else:
            return pd.DataFrame()


# ── Example Usage ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    
    log.info("Example: Loading ML-ready data and generating signals...")
    
    # Load the full ML dataset
    df = pd.read_csv("mcx_silver_ml_ready.csv")
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    
    # Initialize signal generator
    signal_gen = SilverTradingSignals(MODEL_PATH)
    
    # Get predictions for all data
    log.info("\nGenerating entry signals...")
    signals = signal_gen.get_entry_signals(df)
    
    # Summary
    log.info(f"\nTotal signals: {len(signals)}")
    log.info(f"BUY signals: {(signals['signal'] == 1).sum()}")
    log.info(f"Average confidence on BUY: {signals[signals['signal']==1]['confidence'].mean():.3f}")
    
    # High confidence signals (>60%)
    log.info("\n🔥 HIGH-CONFIDENCE BUY SIGNALS (Confidence > 60%):")
    high_conf = signal_gen.filter_high_confidence_signals(signals, min_confidence=0.6)
    
    if len(high_conf) > 0:
        print("\n" + high_conf[['trade_date', 'symbol', 'close', 'confidence_pct']].head(20).to_string(index=False))
        log.info(f"\nFound {len(high_conf)} high-confidence signals")
    else:
        log.info("No high-confidence signals found")
    
    # Rule-based entries
    log.info("\n📊 RULE-BASED ENTRIES (RSI<30 + Volume spike + OI increasing):")
    rule_signals = signal_gen.find_rule_based_entries(df)
    
    if len(rule_signals) > 0:
        print("\n" + rule_signals.head(20).to_string(index=False))
        log.info(f"\nFound {len(rule_signals)} rule-based signals")
    else:
        log.info("No rule-based signals found")
    
    # Save results
    signals.to_csv("trading_signals_predictions.csv", index=False)
    log.info(f"\n✅ All signals saved to 'trading_signals_predictions.csv'")
