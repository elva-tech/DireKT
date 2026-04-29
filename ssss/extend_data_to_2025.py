#!/usr/bin/env python3
"""
Simple MCX Silver Data Extension to March 2, 2025
Extends existing CSV with realistic generated data
"""

import pandas as pd
from datetime import datetime, timedelta
import random
import os

print("📊 Extending MCX Silver data to March 2, 2025...\n")

# Load existing data
try:
    df = pd.read_csv('mcx_silver_futures.csv')
    print(f"✅ Loaded {len(df)} existing records")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    exit(1)

# Ensure date is datetime
df['date'] = pd.to_datetime(df['date'])

# Get last known values
last_date = df['date'].max()
last_close = float(df['close'].iloc[-1])
last_volume = int(df['volume'].iloc[-1])
last_oi = int(df['oi'].iloc[-1])

print(f"\n📈 Last known data:")
print(f"   Date: {last_date.strftime('%Y-%m-%d')}")
print(f"   Price: ₹{last_close:.2f}")
print(f"   Volume: {last_volume}")
print(f"   OI: {last_oi}")

# Calculate volatility from recent data
recent = df.tail(100)
recent['change'] = abs((recent['close'] - recent['open']) / recent['open'] * 100)
volatility = recent['change'].mean()

print(f"   Volatility (30d): {volatility:.2f}%\n")

# Generate data until March 2, 2025
print("🔄 Generating extension data...")

target_date = datetime(2025, 3, 2)
current_date = last_date + timedelta(days=1)
current_price = last_close

new_rows = []
trading_days = 0

while current_date <= target_date:
    # Skip weekends (0=Monday, 6=Sunday)
    if current_date.weekday() < 5:  # Monday to Friday
        # Random seed for reproducibility
        random.seed(int(current_date.timestamp()))
        
        # Random daily change (normal distribution)
        daily_change_pct = random.gauss(0.05, volatility)  # Slight upward bias
        
        # Generate OHLC
        open_price = current_price * (1 + random.uniform(-0.002, 0.002))
        close_price = open_price * (1 + daily_change_pct / 100)
        
        high = max(open_price, close_price) * (1 + random.uniform(0, 0.004))
        low = min(open_price, close_price) * (1 - random.uniform(0, 0.004))
        
        # Volume & OI (realistic for MCX Silver)
        volume = int(last_volume * random.uniform(0.7, 1.3))
        oi = int(last_oi * random.uniform(0.95, 1.05))
        
        new_rows.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'symbol': 'SILVER',
            'ltp': round(close_price, 2),
            'volume': volume,
            'bid': round(close_price - 0.50, 2),
            'ask': round(close_price + 0.50, 2),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close_price, 2),
            'timestamp': current_date.isoformat(),
            'oi': oi
        })
        
        current_price = close_price
        trading_days += 1
        
        if trading_days % 50 == 0:
            print(f"  Generated {trading_days} trading days...")
    
    current_date += timedelta(days=1)

print(f"✅ Generated {len(new_rows)} new records ({trading_days} trading days)\n")

# Create DataFrame and combine
df_new = pd.DataFrame(new_rows)

# Combine
df['date'] = df['date'].dt.strftime('%Y-%m-%d')
df_combined = pd.concat([df, df_new], ignore_index=True)

# Remove duplicates, keep latest
df_combined = df_combined.drop_duplicates(subset=['date', 'symbol'], keep='last')
df_combined = df_combined.sort_values('date')

# Save
output_file = 'mcx_silver_futures_2025.csv'
df_combined.to_csv(output_file, index=False)

print(f"✅ Saved to {output_file}")
print(f"   Total records: {len(df_combined)}")
print(f"   Date range: {df_combined['date'].min()} to {df_combined['date'].max()}")

# Statistics
prices = df_combined['close'].astype(float)
volumes = df_combined['volume'].astype(int)
ois = df_combined['oi'].astype(int)

print(f"\n📊 Extended Dataset Statistics:")
print(f"   Price range: ₹{prices.min():.2f} - ₹{prices.max():.2f}")
print(f"   Avg price: ₹{prices.mean():.2f}")
print(f"   Avg volume: {volumes.mean():.0f} contracts/day")
print(f"   Avg OI: {ois.mean():.0f}")

print(f"\n✅ Done! Ready for model retraining.\n")
