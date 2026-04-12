#!/usr/bin/env python3
"""
Historical Data Replay Engine
==============================
Replays historical MCX Silver futures data to simulate real-time trading.
Uses actual scraped data instead of random mock data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ReplayQuote:
    """Quote data from historical replay."""
    symbol: str
    exchange: str
    ltp: float
    volume: int
    bid: float
    ask: float
    open_price: float
    high: float
    low: float
    close_price: float
    oi: int
    timestamp: str
    
    def __repr__(self):
        return f"{self.symbol}@₹{self.ltp:,.0f} (Vol: {self.volume:,}, OI: {self.oi:,})"


class HistoricalDataReplay:
    """
    Replay historical MCX data at specified speed.
    Great for backtesting and realistic paper trading.
    """
    
    def __init__(self, csv_file: str = 'mcx_silver_futures_2025.csv', 
                 speed_factor: float = 1.0):
        """
        Initialize historical data replay.
        
        Args:
            csv_file: Path to historical data CSV (default: 2024 extended to Mar 2025)
            speed_factor: How fast to replay (1.0 = real-time, 10.0 = 10x faster)
        """
        self.csv_file = csv_file
        self.speed_factor = speed_factor
        self.data = None
        self.current_index = 0
        self.start_time = None
        
        self._load_data()
    
    def _load_data(self):
        """Load historical data from CSV."""
        try:
            self.data = pd.read_csv(self.csv_file)
            
            # Ensure required columns exist
            required = ['close', 'high', 'low', 'open', 'volume_lots', 'open_interest']
            missing = [col for col in required if col not in self.data.columns]
            
            if missing:
                raise ValueError(f"Missing columns: {missing}")
            
            # Convert to numeric
            for col in required:
                self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
            
            # Remove NaN rows
            self.data = self.data.dropna(subset=required)
            
            log.info(f"✅ Loaded {len(self.data)} historical data points")
            log.info(f"   Date range: {self.data['trade_date'].iloc[0]} to {self.data['trade_date'].iloc[-1]}")
            log.info(f"   Price range: ₹{self.data['close'].min():.0f} - ₹{self.data['close'].max():.0f}")
            
            self.start_time = datetime.now()
            self.current_index = 0
            
        except Exception as e:
            log.error(f"❌ Failed to load data: {e}")
            raise
    
    def get_next_quote(self) -> Optional[ReplayQuote]:
        """
        Get next quote from historical data with realistic intraday variation.
        Simulates price movement within the OHLC range.
        """
        if self.data is None or self.current_index >= len(self.data):
            log.warning("⚠️  End of historical data reached")
            # Loop back to start
            self.current_index = 0
            self.start_time = datetime.now()
            return self.get_next_quote()
        
        row = self.data.iloc[self.current_index]
        
        # Add intraday variation (price moves within the day's range)
        # This makes it look more realistic than just using close prices
        high = row['high']
        low = row['low']
        close = row['close']
        
        # Simulate price movement within the range
        price_variation = np.random.uniform(0.3, 0.7)  # 30-70% of daily range
        intraday_price = low + (high - low) * price_variation
        
        # Add some noise to the price
        noise = np.random.normal(0, (high - low) * 0.001)  # 0.1% noise
        ltp = intraday_price + noise
        
        # Volume spread throughout the day
        daily_volume = int(row.get('volume_lots', 100000))
        intraday_volume = int(daily_volume * np.random.uniform(0.05, 0.25))
        
        quote = ReplayQuote(
            symbol='SILVER',
            exchange='MCX',
            ltp=max(low, min(high, ltp)),  # Keep within daily range
            volume=intraday_volume,
            bid=ltp - 50,  # Spread
            ask=ltp + 50,
            open_price=row['open'],
            high=high,
            low=low,
            close_price=close,
            oi=int(row.get('open_interest', 50000)),
            timestamp=datetime.now().isoformat()
        )
        
        self.current_index += 1
        
        return quote
    
    def peek_next(self) -> Optional[dict]:
        """Peek at next data point without consuming it."""
        if self.data is None or self.current_index >= len(self.data):
            return None
        
        row = self.data.iloc[self.current_index]
        return {
            'date': row.get('trade_date', 'N/A'),
            'price': row['close'],
            'high': row['high'],
            'low': row['low'],
            'volume': row.get('volume_lots', 0),
            'oi': row.get('open_interest', 0)
        }
    
    def get_stats(self) -> dict:
        """Get statistics about the replay data."""
        if self.data is None:
            return {}
        
        return {
            'total_points': len(self.data),
            'remaining_points': len(self.data) - self.current_index,
            'progress_percent': (self.current_index / len(self.data) * 100),
            'avg_price': self.data['close'].mean(),
            'min_price': self.data['close'].min(),
            'max_price': self.data['close'].max(),
            'avg_volume': self.data.get('volume_lots', [0]).mean(),
            'avg_oi': self.data.get('open_interest', [0]).mean(),
        }
    
    def reset(self):
        """Reset to beginning of data."""
        self.current_index = 0
        self.start_time = datetime.now()
        log.info("📊 Data replay reset to beginning")


# ────────────────────────────────────────────────────────────────────────────
# Test the replay engine

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    print("\n" + "="*80)
    print("MCX SILVER FUTURES - HISTORICAL DATA REPLAY ENGINE")
    print("="*80 + "\n")
    
    try:
        replay = HistoricalDataReplay('mcx_silver_futures.csv')
        
        print("\n📊 Replaying first 10 quotes:")
        print("-" * 80)
        
        for i in range(10):
            quote = replay.get_next_quote()
            if quote:
                print(f"{i+1:2d}. {quote}")
        
        print("\n" + "="*80)
        stats = replay.get_stats()
        print(f"📈 Replay Statistics:")
        print(f"   Progress: {stats['progress_percent']:.1f}% ({stats['remaining_points']:,} remaining)")
        print(f"   Price: ₹{stats['avg_price']:.0f} (Range: ₹{stats['min_price']:.0f} - ₹{stats['max_price']:.0f})")
        print(f"   Avg Volume: {stats['avg_volume']:.0f} contracts")
        print(f"   Avg OI: {stats['avg_oi']:.0f}")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
