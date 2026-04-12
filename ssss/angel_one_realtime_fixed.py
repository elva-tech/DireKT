#!/usr/bin/env python3
"""
Real-Time MCX Silver Data (WebSocket + REST Fallback)
==================================================
Fixed WebSocket connection with REST API fallback for reliable real-time data
"""

import os
import json
import logging
import requests
import websocket
import threading
import time
import ssl
import certifi
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

@dataclass
class MCXQuoteData:
    """MCX Silver futures quote in INR."""
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

class AngelOneRealTimeData:
    """Fixed Angel One WebSocket + REST API for real-time MCX data."""
    
    def __init__(self):
        # Load credentials
        self.api_key = os.getenv('ANGEL_ONE_API_KEY')
        self.client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
        self.client_secret = os.getenv('ANGEL_ONE_CLIENT_SECRET')
        self.auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')
        
        self.ws_connected = False
        self.last_quote = None
        self.quote_callback = None
        
        # SSL context for WebSocket
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        log.info("✅ Angel One real-time data client initialized")
    
    def get_rest_quote(self, symbol: str = "SILVER", exchange: str = "MCX") -> Optional[MCXQuoteData]:
        """Get quote via REST API (fallback method)."""
        try:
            # Angel One REST API endpoint for quotes
            url = f"https://smartapi.angelbroking.com/rest/secure/quotes"
            
            headers = {
                'Authorization': f'Bearer {self.auth_token}',
                'Content-Type': 'application/json',
                'X-UserType': 'USER',
                'X-SourceID': 'WEB',
                'X-ClientLocalIP': '127.0.0.1',
                'X-MACAddress': '00:00:00:00:00:00',
                'X-UserType': 'USER'
            }
            
            payload = {
                "mode": "FULL",
                "exchangeTokens": {
                    exchange: [symbol]
                }
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') and data.get('data'):
                    quote_data = data['data'].get('fetched', [{}])[0]
                    
                    return MCXQuoteData(
                        symbol=symbol,
                        exchange=exchange,
                        ltp=float(quote_data.get('ltp', 0)),
                        volume=int(quote_data.get('volume', 0)),
                        bid=float(quote_data.get('bid', 0)),
                        ask=float(quote_data.get('ask', 0)),
                        open_price=float(quote_data.get('open', 0)),
                        high=float(quote_data.get('high', 0)),
                        low=float(quote_data.get('low', 0)),
                        close_price=float(quote_data.get('close', 0)),
                        timestamp=datetime.now().isoformat(),
                        oi=int(quote_data.get('oi', 0))
                    )
            
            log.warning(f"REST API failed: {response.status_code}")
            return None
            
        except Exception as e:
            log.error(f"REST API error: {e}")
            return None
    
    def on_websocket_message(self, ws, message):
        """Handle WebSocket message."""
        try:
            data = json.loads(message)
            
            if data.get('type') == 'quote':
                quote_data = data.get('data', {})
                
                quote = MCXQuoteData(
                    symbol=quote_data.get('name', 'SILVER'),
                    exchange=quote_data.get('exch', 'MCX'),
                    ltp=float(quote_data.get('ltp', 0)),
                    volume=int(quote_data.get('volume', 0)),
                    bid=float(quote_data.get('bid', 0)),
                    ask=float(quote_data.get('ask', 0)),
                    open_price=float(quote_data.get('open', 0)),
                    high=float(quote_data.get('high', 0)),
                    low=float(quote_data.get('low', 0)),
                    close_price=float(quote_data.get('close', 0)),
                    timestamp=datetime.now().isoformat(),
                    oi=int(quote_data.get('oi', 0))
                )
                
                self.last_quote = quote
                log.info(f"📡 WebSocket quote: ₹{quote.ltp:,.2f}")
                
                if self.quote_callback:
                    self.quote_callback(quote)
                    
            elif data.get('type') == 'ack':
                log.info("✅ WebSocket subscription acknowledged")
                
        except Exception as e:
            log.error(f"WebSocket message error: {e}")
    
    def on_websocket_error(self, ws, error):
        """Handle WebSocket error."""
        log.error(f"❌ WebSocket error: {error}")
        self.ws_connected = False
    
    def on_websocket_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        log.warning(f"⚠️  WebSocket closed: {close_status_code}")
        self.ws_connected = False
    
    def on_websocket_open(self, ws):
        """Handle WebSocket open."""
        log.info("✅ WebSocket connected")
        self.ws_connected = True
        
        # Send subscription request
        subscription = {
            "type": "subscribe",
            "mode": "LTP",
            "tokenSet": [{
                "exchangeTokens": {
                    "MCX": ["SILVER"]
                }
            }],
            "clientId": self.client_id
        }
        
        ws.send(json.dumps(subscription))
        log.info("📡 Subscription sent for MCX SILVER")
    
    def connect_websocket(self) -> bool:
        """Connect to Angel One WebSocket."""
        try:
            # Try multiple endpoints
            endpoints = [
                "wss://smartapi.angelbroking.com/feed",
                "wss://smartapi.angelbroking.com/NorenWS"
            ]
            
            for endpoint in endpoints:
                try:
                    log.info(f"🔄 Connecting to: {endpoint}")
                    
                    headers = [
                        f"Authorization: Bearer {self.auth_token}",
                        f"X-API-KEY: {self.api_key}",
                        f"X-CLIENT-ID: {self.client_id}"
                    ]
                    
                    ws = websocket.WebSocketApp(
                        endpoint,
                        header=headers,
                        on_message=self.on_websocket_message,
                        on_error=self.on_websocket_error,
                        on_close=self.on_websocket_close,
                        on_open=self.on_websocket_open
                    )
                    
                    # Start WebSocket in background
                    ws_thread = threading.Thread(
                        target=ws.run_forever,
                        kwargs={"sslopt": {"context": self.ssl_context}},
                        daemon=True
                    )
                    ws_thread.start()
                    
                    # Wait for connection
                    for i in range(10):
                        if self.ws_connected:
                            log.info(f"✅ WebSocket connected to {endpoint}")
                            return True
                        time.sleep(1)
                    
                    log.warning(f"❌ Timeout connecting to {endpoint}")
                    
                except Exception as e:
                    log.error(f"❌ Failed to connect to {endpoint}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            log.error(f"WebSocket connection failed: {e}")
            return False
    
    def get_real_time_data(self, callback=None) -> Optional[MCXQuoteData]:
        """
        Get real-time data using WebSocket with REST fallback.
        
        Args:
            callback: Function to call when new quote arrives
            
        Returns:
            Latest quote or None if unavailable
        """
        self.quote_callback = callback
        
        # Try WebSocket first
        if not self.ws_connected:
            log.info("🔄 Attempting WebSocket connection...")
            if self.connect_websocket():
                # Wait for first WebSocket quote
                for i in range(5):
                    if self.last_quote:
                        return self.last_quote
                    time.sleep(1)
        
        # Fallback to REST API
        log.info("🔄 Using REST API fallback...")
        quote = self.get_rest_quote()
        
        if quote:
            self.last_quote = quote
            log.info(f"📡 REST quote: ₹{quote.ltp:,.2f}")
            
            if self.quote_callback:
                self.quote_callback(quote)
        
        return quote

def main():
    """Test real-time data with WebSocket + REST fallback."""
    log.info("🔄 Testing Angel One Real-Time Data (WebSocket + REST)")
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Initialize client
    client = AngelOneRealTimeData()
    
    def quote_callback(quote):
        print(f"🔔 New Quote: {quote}")
    
    # Test data fetching
    for i in range(3):
        log.info(f"\n--- Test {i+1} ---")
        
        quote = client.get_real_time_data(quote_callback)
        
        if quote:
            log.info(f"✅ Quote received:")
            log.info(f"   Symbol: {quote.symbol}")
            log.info(f"   Price: ₹{quote.ltp:,.2f}")
            log.info(f"   Volume: {quote.volume:,}")
            log.info(f"   OI: {quote.oi:,}")
        else:
            log.error("❌ No quote received")
        
        time.sleep(3)
    
    log.info("✅ Real-time data test completed")

if __name__ == "__main__":
    main()
