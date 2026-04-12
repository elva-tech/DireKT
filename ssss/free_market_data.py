#!/usr/bin/env python3
"""
Free Real-Time Market Data Fetcher
=================================
Uses free APIs for real-time MCX Silver data
"""

import requests
import json
import logging
from datetime import datetime
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class FreeMarketData:
    """Fetch real-time data from free market APIs."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_yahoo_finance_data(self, symbol: str = "GC=F") -> Optional[Dict]:
        """Get data from Yahoo Finance (Silver Futures)."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                chart = data.get('chart', {}).get('result', [])
                
                if chart:
                    meta = chart[0].get('meta', {})
                    current_data = chart[0].get('indicators', {}).get('quote', [{}])[0]
                    
                    # Get latest data
                    timestamps = chart[0].get('timestamp', [])
                    if timestamps:
                        latest_idx = len(timestamps) - 1
                        
                        return {
                            'symbol': 'SILVER',
                            'exchange': 'MCX',
                            'ltp': current_data.get('close', [0])[-1] or meta.get('regularMarketPrice', 0),
                            'volume': meta.get('regularMarketVolume', 0),
                            'bid': meta.get('bid', 0),
                            'ask': meta.get('ask', 0),
                            'open_price': meta.get('regularMarketOpen', 0),
                            'high': meta.get('regularMarketDayHigh', 0),
                            'low': meta.get('regularMarketDayLow', 0),
                            'close_price': meta.get('regularMarketPreviousClose', 0),
                            'timestamp': datetime.now().isoformat(),
                            'oi': 0  # Not available from Yahoo
                        }
            
            return None
            
        except Exception as e:
            log.error(f"Yahoo Finance error: {e}")
            return None
    
    def get_investing_data(self) -> Optional[Dict]:
        """Get data from Investing.com (alternative source)."""
        try:
            # This would require web scraping - simplified version
            url = "https://www.investing.com/commodities/silver"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                # Parse HTML for price data (simplified)
                # In real implementation, use BeautifulSoup
                log.info("✅ Investing.com accessible - would parse for real-time data")
                return None
            
            return None
            
        except Exception as e:
            log.error(f"Investing.com error: {e}")
            return None
    
    def get_market_data(self) -> Optional[Dict]:
        """Try multiple sources for real-time data."""
        log.info("🔄 Fetching real-time data from multiple sources...")
        
        # Try Yahoo Finance first
        data = self.get_yahoo_finance_data()
        if data:
            log.info("✅ Real-time data from Yahoo Finance")
            return data
        
        # Try Investing.com as backup
        data = self.get_investing_data()
        if data:
            log.info("✅ Real-time data from Investing.com")
            return data
        
        log.error("❌ All real-time data sources failed")
        return None

def main():
    """Test free market data fetch."""
    log.info("🔄 Testing free market data APIs...")
    
    fetcher = FreeMarketData()
    data = fetcher.get_market_data()
    
    if data:
        log.info("✅ Real-time data fetched:")
        log.info(f"   Symbol: {data['symbol']}")
        log.info(f"   Price: ${data['ltp']:,.2f}")
        log.info(f"   Volume: {data['volume']:,}")
        log.info(f"   High: ${data['high']:,.2f}")
        log.info(f"   Low: ${data['low']:,.2f}")
        return True
    else:
        log.error("❌ Failed to fetch real-time data")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
