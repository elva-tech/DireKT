#!/usr/bin/env python3
"""
Dhan Real-Time Data Fetcher
===========================
Alternative to Angel One for real-time MCX Silver data
"""

import os
import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

@dataclass
class QuoteData:
    """Real-time quote data structure."""
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
    timestamp: str
    oi: int

class DhanRealTimeFetcher:
    """Fetch real-time data from Dhan API."""
    
    def __init__(self):
        self.base_url = "https://api.dhan.co"
        self.access_token = os.getenv('DHAN_ACCESS_TOKEN')
        self.client_id = os.getenv('DHAN_CLIENT_ID')
        
        if not self.access_token:
            log.error("❌ DHAN_ACCESS_TOKEN not found in environment")
            raise ValueError("Dhan credentials required")
        
        self.headers = {
            'Accept': 'application/json',
            'client_id': self.client_id,
            'access_token': self.access_token
        }
        
        log.info("✅ Dhan API client initialized")
    
    def get_market_data(self, symbol: str = "SILVERMAR26", exchange: str = "MCX") -> Optional[QuoteData]:
        """Fetch latest market data for MCX Silver."""
        try:
            # Get market depth and price
            url = f"{self.base_url}/market-data/quote/{exchange}/{symbol}"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                log.info(f"✅ Dhan API response: {data}")
                
                # Parse response (adjust based on actual Dhan API format)
                if data.get('status') == 'success':
                    quote_data = data.get('data', {})
                    
                    return QuoteData(
                        symbol=symbol,
                        exchange=exchange,
                        ltp=quote_data.get('ltp', 0),
                        volume=quote_data.get('volume', 0),
                        bid=quote_data.get('bid', 0),
                        ask=quote_data.get('ask', 0),
                        open_price=quote_data.get('open', 0),
                        high=quote_data.get('high', 0),
                        low=quote_data.get('low', 0),
                        close_price=quote_data.get('close', 0),
                        timestamp=datetime.now().isoformat(),
                        oi=quote_data.get('oi', 0)
                    )
                else:
                    log.warning(f"❌ Dhan API error: {data.get('message', 'Unknown error')}")
                    return None
            else:
                log.error(f"❌ Dhan API HTTP error: {response.status_code}")
                return None
                
        except Exception as e:
            log.error(f"❌ Dhan API connection error: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test Dhan API connectivity."""
        try:
            url = f"{self.base_url}/profile"
            response = requests.get(url, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                log.info("✅ Dhan API connection successful")
                return True
            else:
                log.error(f"❌ Dhan API auth failed: {response.status_code}")
                return False
                
        except Exception as e:
            log.error(f"❌ Dhan API test failed: {e}")
            return False

def main():
    """Test Dhan real-time data fetch."""
    log.info("🔄 Testing Dhan API for real-time data...")
    
    try:
        fetcher = DhanRealTimeFetcher()
        
        # Test connection
        if fetcher.test_connection():
            # Fetch market data
            quote = fetcher.get_market_data()
            
            if quote:
                log.info("✅ Real-time data fetched successfully:")
                log.info(f"   Symbol: {quote.symbol}")
                log.info(f"   Price: ₹{quote.ltp:,.2f}")
                log.info(f"   Volume: {quote.volume:,}")
                log.info(f"   OI: {quote.oi:,}")
                return True
            else:
                log.error("❌ Failed to fetch market data")
                return False
        else:
            log.error("❌ Dhan API connection failed")
            return False
            
    except Exception as e:
        log.error(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
