#!/usr/bin/env python3
"""
Real-Time Data Integration for Trading Bot
======================================
Integrates multiple real-time data sources for MCX Silver in INR
"""

import logging
from typing import Optional
from mcx_silver_inr import MCXIndiaData, MCXQuoteData
from angel_one_connector import QuoteData

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class UnifiedRealTimeData:
    """Unified real-time data fetcher for trading bot."""
    
    def __init__(self):
        self.mcx_fetcher = MCXIndiaData()
        self.last_quote = None
    
    def fetch_latest(self, symbol: str = "SILVER", exchange: str = "MCX") -> Optional[QuoteData]:
        """
        Fetch latest quote in trading bot format.
        
        Returns QuoteData object compatible with existing trading bot.
        """
        try:
            # Get MCX Silver data in INR
            mcx_data = self.mcx_fetcher.get_real_time_data()
            
            if mcx_data:
                log.info(f"✅ Real-time MCX data: ₹{mcx_data.ltp:,.2f}")
                
                # Convert to trading bot's QuoteData format
                quote = QuoteData(
                    symbol=mcx_data.symbol,
                    exchange=mcx_data.exchange,
                    ltp=mcx_data.ltp,
                    volume=mcx_data.volume,
                    bid=mcx_data.bid,
                    ask=mcx_data.ask,
                    open_price=mcx_data.open_price,
                    high=mcx_data.high,
                    low=mcx_data.low,
                    close_price=mcx_data.close_price,
                    timestamp=mcx_data.timestamp,
                    oi=mcx_data.oi
                )
                
                self.last_quote = quote
                return quote
            else:
                log.warning("❌ No real-time data available")
                return None
                
        except Exception as e:
            log.error(f"❌ Error fetching real-time data: {e}")
            return None
    
    def get_last_quote(self) -> Optional[QuoteData]:
        """Get the last successfully fetched quote."""
        return self.last_quote
    
    def test_connection(self) -> bool:
        """Test real-time data connection."""
        try:
            quote = self.fetch_latest()
            if quote:
                log.info("✅ Real-time data connection successful")
                log.info(f"   Current price: ₹{quote.ltp:,.2f}")
                log.info(f"   Volume: {quote.volume:,}")
                log.info(f"   OI: {quote.oi:,}")
                return True
            else:
                log.error("❌ Failed to fetch real-time data")
                return False
        except Exception as e:
            log.error(f"❌ Connection test failed: {e}")
            return False

def main():
    """Test unified real-time data integration."""
    log.info("🔄 Testing unified real-time data integration...")
    
    fetcher = UnifiedRealTimeData()
    
    # Test connection
    if fetcher.test_connection():
        log.info("✅ Ready for trading bot integration")
        
        # Fetch a few quotes to test
        for i in range(3):
            quote = fetcher.fetch_latest()
            if quote:
                log.info(f"   Quote {i+1}: {quote}")
            import time
            time.sleep(2)
        
        return True
    else:
        log.error("❌ Integration failed")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
