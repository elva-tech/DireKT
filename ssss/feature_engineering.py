"""
MCX Silver Futures - Feature Engineering for ML Trading Models
==============================================================
Transforms raw OHLC data into ML-ready features for trade entry prediction.

Features engineered:
  1. Price momentum (SMA, EMA, returns)
  2. Volatility (ATR, Bollinger Bands, daily range)
  3. Volume analysis (volume_spike, volume_momentum)
  4. Open Interest signals (OI_change, OI_momentum)
  5. Technical indicators (RSI, MACD)
  6. Derived patterns for entry detection
  7. Target variable: 5-candle forward return label
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── CONFIG ──────────────────────────────────────────────────────────────────
CSV_PATH             = "mcx_silver_futures_2025.csv"
ENGINEERED_CSV_PATH  = "mcx_silver_features.csv"
ML_READY_CSV_PATH    = "mcx_silver_ml_ready.csv"
PROFIT_TARGET_PCT    = 0.5  # 0.5% = entry if next 5 candles give +0.5% return


# ── Technical Indicators ────────────────────────────────────────────────────
def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA and EMA indicators."""
    df['SMA_10']  = df['close'].rolling(10).mean()
    df['SMA_20']  = df['close'].rolling(20).mean()
    df['SMA_50']  = df['close'].rolling(50).mean()
    df['SMA_200'] = df['close'].rolling(200).mean()
    
    df['EMA_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate Relative Strength Index."""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MACD (Moving Average Convergence Divergence)."""
    df['MACD']      = df['EMA_12'] - df['EMA_26']
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist']   = df['MACD'] - df['MACD_signal']
    return df


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Calculate Bollinger Bands."""
    sma = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    
    df['BB_upper'] = sma + (std * std_dev)
    df['BB_lower'] = sma - (std * std_dev)
    df['BB_middle'] = sma
    df['BB_width'] = df['BB_upper'] - df['BB_lower']
    df['BB_pct'] = (df['close'] - df['BB_lower']) / (df['BB_upper'] - df['BB_lower'])  # %B indicator
    
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calculate Average True Range (volatility indicator)."""
    df['high_low']   = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift())
    df['low_close']  = abs(df['low'] - df['close'].shift())
    
    df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['ATR'] = df['true_range'].rolling(period).mean()
    
    return df


# ── Price Features ──────────────────────────────────────────────────────────
def add_price_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute price-based features."""
    # Daily returns
    df['pct_return'] = df['close'].pct_change() * 100
    
    # Candle components
    df['candle_body'] = abs(df['close'] - df['open'])
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    
    # Daily range
    df['daily_range'] = df['high'] - df['low']
    df['daily_range_pct'] = (df['daily_range'] / df['close']) * 100
    
    # Price position in range (0=low, 1=high)
    df['price_in_range'] = (df['close'] - df['low']) / (df['high'] - df['low'])
    
    # Momentum
    df['momentum_5'] = df['close'] - df['close'].shift(5)
    df['momentum_10'] = df['close'] - df['close'].shift(10)
    
    # Price vs moving average
    df['price_vs_sma20'] = ((df['close'] - df['SMA_20']) / df['SMA_20']) * 100
    df['price_vs_sma50'] = ((df['close'] - df['SMA_50']) / df['SMA_50']) * 100
    
    return df


# ── Volume Features ─────────────────────────────────────────────────────────
def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute volume-based features."""
    # Volume moving averages
    df['volume_MA_20'] = df['volume_lots'].rolling(20).mean()
    df['volume_MA_50'] = df['volume_lots'].rolling(50).mean()
    
    # Volume change
    df['volume_change'] = df['volume_lots'].pct_change() * 100
    df['volume_change_MA'] = df['volume_change'].rolling(10).mean()
    
    # Volume spike (deviation from MA)
    df['volume_spike_ratio'] = df['volume_lots'] / df['volume_MA_20']
    df['is_volume_spike'] = (df['volume_spike_ratio'] > 1.5).astype(int)
    
    # Volume momentum (if volume increasing with trend)
    volume_uptrend = (df['close'] > df['close'].shift(1)).astype(int)
    df['volume_momentum'] = df['volume_lots'] * volume_uptrend
    
    return df


# ── Open Interest Features ──────────────────────────────────────────────────
def add_oi_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Open Interest features."""
    # OI change and momentum
    df['OI_change'] = df['open_interest'].diff()
    df['OI_change_pct'] = df['open_interest'].pct_change() * 100
    
    # OI moving average
    df['OI_MA_20'] = df['open_interest'].rolling(20).mean()
    
    # OI momentum (increasing/decreasing)
    df['OI_momentum'] = df['OI_change'].rolling(5).mean()
    
    # Price vs OI trend (bullish signal: price↑ + OI↑)
    price_up = (df['close'] > df['close'].shift(1)).astype(int)
    oi_up = (df['open_interest'] > df['open_interest'].shift(1)).astype(int)
    df['price_oi_bullish'] = price_up & oi_up
    
    return df


# ── Entry Signal Features ───────────────────────────────────────────────────
def add_entry_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Create entry signal features for classification."""
    # RSI oversold/overbought
    df['rsi_oversold'] = (df['RSI'] < 30).astype(int)
    df['rsi_overbought'] = (df['RSI'] > 70).astype(int)
    
    # Volume spike
    df['vol_spike'] = (df['volume_spike_ratio'] > 1.5).astype(int)
    
    # OI increasing
    df['oi_increasing'] = (df['OI_change'] > 0).astype(int)
    
    # Price near Bollinger Band lower (support)
    df['price_near_bb_lower'] = (df['BB_pct'] < 0.2).astype(int)
    
    # MACD bullish crossover
    df['macd_bullish'] = ((df['MACD'] > df['MACD_signal']) & 
                          (df['MACD'].shift(1) <= df['MACD_signal'].shift(1))).astype(int)
    
    # Combined entry signal: RSI oversold + volume spike + OI increasing
    df['strong_entry_signal'] = (
        (df['rsi_oversold'] == 1) &
        (df['vol_spike'] == 1) &
        (df['oi_increasing'] == 1)
    ).astype(int)
    
    return df


# ── Target Variable (Forward Return Label) ──────────────────────────────────
def add_target_variable(df: pd.DataFrame, forward_periods: int = 5, 
                       profit_target_pct: float = 0.5) -> pd.DataFrame:
    """
    Create target variable: predict if next N candles give X% return.
    
    Label:
      1 = BUY (next 5 candles: high >= current_close * (1 + 0.5%))
      0 = NO_TRADE
    """
    # Calculate max price in next N periods
    df['high_next_n'] = df['high'].shift(-forward_periods).rolling(forward_periods).max()
    df['high_next_n'] = df['high_next_n'].shift(forward_periods)  # align back
    
    # Alternative: use close price movement
    df['close_next_n'] = df['close'].shift(-forward_periods)
    df['return_next_n_pct'] = ((df['close_next_n'] - df['close']) / df['close']) * 100
    
    # Label: 1 if profit target hit in next N candles
    df['target'] = (df['return_next_n_pct'] >= profit_target_pct).astype(int)
    
    return df


# ── Data Cleaning ───────────────────────────────────────────────────────────
def clean_features(df: pd.DataFrame) -> pd.DataFrame:
    """Remove NaN, drop duplicates, sort by date."""
    # Remove rows with NaN in critical features
    df = df.dropna(subset=['close', 'volume_lots', 'open_interest'])
    
    # Drop fully NaN rows
    df = df.dropna(how='all')
    
    # Drop duplicates
    df = df.drop_duplicates(subset=['trade_date', 'symbol', 'expiry_date'], keep='first')
    
    # Sort by date
    df = df.sort_values('trade_date').reset_index(drop=True)
    
    return df


# ── Main Pipeline ───────────────────────────────────────────────────────────
def engineer_features(input_csv: str, output_csv: str) -> pd.DataFrame:
    """Complete feature engineering pipeline."""
    
    log.info(f"Loading raw data from {input_csv}...")
    df = pd.read_csv(input_csv)
    
    # Ensure proper data types
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    df['volume_lots'] = pd.to_numeric(df['volume_lots'], errors='coerce')
    df['open_interest'] = pd.to_numeric(df['open_interest'], errors='coerce')
    
    log.info(f"Raw data shape: {df.shape}")
    
    # Add all features
    log.info("Adding technical indicators...")
    df = add_moving_averages(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)
    df = add_atr(df)
    
    log.info("Adding price features...")
    df = add_price_features(df)
    
    log.info("Adding volume features...")
    df = add_volume_features(df)
    
    log.info("Adding Open Interest features...")
    df = add_oi_features(df)
    
    log.info("Adding entry signals...")
    df = add_entry_signals(df)
    
    log.info(f"Adding target variable (forward {5} candles, target: +{PROFIT_TARGET_PCT}%)...")
    df = add_target_variable(df, forward_periods=5, profit_target_pct=PROFIT_TARGET_PCT)
    
    log.info("Cleaning features...")
    df = clean_features(df)
    
    log.info(f"Engineered data shape: {df.shape}")
    log.info(f"Total features: {df.shape[1]}")
    
    # Save full feature set
    df.to_csv(output_csv, index=False)
    log.info(f"✅ Full feature set saved to {output_csv}")
    
    return df


def create_ml_ready_dataset(df: pd.DataFrame, output_csv: str) -> pd.DataFrame:
    """Select best features for ML model training."""
    
    # Core ML features (the most powerful ones)
    ml_features = [
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
        
        # Target
        'target', 'return_next_n_pct'
    ]
    
    # Check which features exist
    available_features = [f for f in ml_features if f in df.columns]
    
    ml_df = df[['trade_date', 'symbol', 'expiry_date'] + available_features].copy()
    
    # Remove rows with NaN in critical features
    ml_df = ml_df.dropna(subset=['RSI', 'MACD', 'ATR', 'target'])
    
    log.info(f"ML-ready dataset shape: {ml_df.shape}")
    log.info(f"Features selected: {len(available_features)}")
    log.info(f"Target distribution:\n{ml_df['target'].value_counts()}")
    
    ml_df.to_csv(output_csv, index=False)
    log.info(f"✅ ML-ready dataset saved to {output_csv}")
    
    return ml_df


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Step 1: Engineer all features
    df_engineered = engineer_features(CSV_PATH, ENGINEERED_CSV_PATH)
    
    # Step 2: Create ML-ready dataset
    df_ml = create_ml_ready_dataset(df_engineered, ML_READY_CSV_PATH)
    
    # Summary statistics
    log.info("\n" + "="*70)
    log.info("📊 FEATURE ENGINEERING SUMMARY")
    log.info("="*70)
    log.info(f"Raw CSV: {CSV_PATH}")
    log.info(f"Full features CSV: {ENGINEERED_CSV_PATH}")
    log.info(f"ML-ready CSV: {ML_READY_CSV_PATH}")
    log.info(f"\nDataset size: {df_ml.shape[0]} rows × {df_ml.shape[1]} columns")
    log.info(f"Date range: {df_ml['trade_date'].min()} to {df_ml['trade_date'].max()}")
    log.info(f"\nBUY signals: {df_ml['target'].sum()} ({df_ml['target'].mean()*100:.1f}%)")
    log.info(f"NO_TRADE: {(1-df_ml['target']).sum()} ({(1-df_ml['target']).mean()*100:.1f}%)")
    log.info("\n✅ Feature engineering complete! Ready for ML model training.")
