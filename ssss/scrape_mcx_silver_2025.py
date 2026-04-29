#!/usr/bin/env python3
"""
MCX Silver Futures Data Scraper - Fetch historical data up to March 2, 2025
Uses MCX Bhavcopy API and web scraping for complete historical coverage
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
import csv
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# MCX Silver contract symbol variations
SILVER_SYMBOLS = ['SILVER', 'SILVERMIC', 'SILVER-MIC', 'SILVERM']

def fetch_bhavcopy_data():
    """
    Fetch historical data from MCX Bhavcopy (official settlement data)
    Range: 2020-01-01 to 2025-03-02
    """
    log.info("🔄 Fetching MCX Bhavcopy historical data...")
    
    data = []
    base_url = "https://www.mcxindia.com/bhavcopy/bhavcopy_csv"
    
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2025, 3, 2)
    
    current_date = start_date
    count = 0
    errors = 0
    
    while current_date <= end_date:
        # Skip weekends (MCX doesn't trade on Saturdays/Sundays)
        if current_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            current_date += timedelta(days=1)
            continue
        
        date_str = current_date.strftime('%d%b%Y').upper()
        url = f"{base_url}/{date_str}.csv"
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                # Parse CSV content
                lines = response.text.strip().split('\n')
                
                for line in lines[1:]:  # Skip header
                    if not line.strip():
                        continue
                    
                    parts = [p.strip() for p in line.split(',')]
                    
                    # Find SILVER contract data
                    if len(parts) >= 8 and any(sym in parts[0].upper() for sym in SILVER_SYMBOLS):
                        try:
                            contract = parts[0]
                            date = current_date.strftime('%Y-%m-%d')
                            open_price = float(parts[2])
                            high = float(parts[3])
                            low = float(parts[4])
                            close = float(parts[5])
                            volume = int(float(parts[6]))
                            oi = int(float(parts[7]))
                            
                            # Skip if basic validation fails
                            if open_price <= 0 or close <= 0:
                                continue
                            
                            data.append({
                                'date': date,
                                'symbol': 'SILVER',
                                'contract': contract,
                                'open': open_price,
                                'high': high,
                                'low': low,
                                'close': close,
                                'volume': volume,
                                'oi': oi
                            })
                            
                            count += 1
                        except (ValueError, IndexError):
                            continue
                
                if count % 50 == 0:
                    log.info(f"✅ Fetched {count} records (up to {date_str})")
            
            elif response.status_code == 404:
                log.debug(f"⏭️  No data for {date_str} (holiday/non-trading)")
            else:
                errors += 1
                if errors % 50 == 0:
                    log.warning(f"⚠️  {errors} errors encountered")
        
        except requests.exceptions.RequestException as e:
            log.debug(f"Error fetching {date_str}: {e}")
            errors += 1
        
        current_date += timedelta(days=1)
    
    log.info(f"✅ Total records fetched: {count}")
    return pd.DataFrame(data)

def fetch_alternative_sources():
    """
    Fallback: Try alternative data sources if Bhavcopy unavailable
    """
    log.info("🔄 Trying alternative data sources...")
    
    try:
        # Try Angel One historical data if available through their API
        url = "https://smartapi.angelbroking.com/rest/secure/historical"
        # Implementation would go here if we have API access
        log.info("⏳ Alternative source check...")
    except Exception as e:
        log.warning(f"Alternative sources unavailable: {e}")
    
    return None

def save_to_csv(df, filename='mcx_silver_futures_2025.csv'):
    """Save data to CSV with proper formatting"""
    if df.empty:
        log.warning("❌ No data to save")
        return False
    
    # Sort by date
    df = df.sort_values('date').reset_index(drop=True)
    
    # Remove duplicates (keep latest if same date)
    df = df.drop_duplicates(subset=['date', 'symbol'], keep='last')
    
    # Save to CSV
    df.to_csv(filename, index=False)
    
    log.info(f"✅ Saved {len(df)} records to {filename}")
    log.info(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    log.info(f"   Price range: ₹{df['close'].min():.2f} - ₹{df['close'].max():.2f}")
    log.info(f"   Avg volume: {df['volume'].mean():.0f} contracts/day")
    log.info(f"   Avg OI: {df['oi'].mean():.0f}")
    
    return True

def main():
    """Main scraping workflow"""
    print("\n" + "="*70)
    print("🔍 MCX SILVER FUTURES DATA SCRAPER")
    print("   Period: 2020-01-01 to 2025-03-02")
    print("="*70 + "\n")
    
    # Fetch Bhavcopy data
    df = fetch_bhavcopy_data()
    
    if df.empty:
        log.warning("❌ Bhavcopy fetch failed, trying alternatives...")
        df = fetch_alternative_sources()
    
    if df is None or df.empty:
        log.error("❌ Could not fetch data from any source")
        return False
    
    # Save to CSV
    if save_to_csv(df, 'mcx_silver_futures_2025.csv'):
        log.info("\n✅ MCX Silver data successfully scraped and saved!")
        return True
    else:
        log.error("❌ Failed to save data")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
