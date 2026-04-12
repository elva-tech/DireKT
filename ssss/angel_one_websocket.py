#!/usr/bin/env python3
"""
Angel One WebSocket Quote Streaming
====================================
Real-time quote streaming via WebSocket for MCX Silver futures.
More reliable than REST API endpoint.
"""

import websocket
import json
import logging
import threading
import time
import ssl
import certifi
from typing import Optional, Callable, Dict
from datetime import datetime
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class WSQuote:
    """WebSocket quote data structure."""
    symbol: str
    exchange: str
    ltp: float           # Last Traded Price
    volume: int
    bid: float
    ask: float
    open_price: float
    high: float
    low: float
    close_price: float
    oi: int              # Open Interest
    timestamp: str
    
    def __repr__(self):
        return f"{self.symbol}@₹{self.ltp:,.0f} (Vol: {self.volume:,}, OI: {self.oi:,})"


class AngelOneWebSocketClient:
    """
    WebSocket client for Angel One smart quotes.
    Provides real-time streaming data for MCX instruments.
    """
    
    # Angel One WebSocket endpoints (works with free tier)
    WS_URLS = [
        "wss://smartapisocket.angelone.in/smart-stream",  # Primary: Free-tier endpoint
        "wss://smartapi.angelbroking.com/NorenWS",         # Fallback: NorenWS protocol
        "wss://smartapi.angelbroking.com/feed",            # Fallback: Feed endpoint
        "wss://smartapi.angelbroking.com/ws"               # Fallback: Standard WebSocket
    ]
    WS_URL = WS_URLS[0]  # Primary endpoint
    QUOTE_MODE = "QUOTE"  # QUOTE mode = OHLCV (free tier compatible)
    
    def __init__(self, auth_token: str, api_key: str, client_id: str):
        """
        Initialize WebSocket client.
        
        Args:
            auth_token: JWT token from Angel One authentication
            api_key: API key from Angel One account
            client_id: Client ID (usually same as username)
        """
        self.auth_token = auth_token
        self.api_key = api_key
        self.client_id = client_id
        
        self.ws = None
        self.connected = False
        self.last_quote = None
        self.quote_cache: Dict[str, WSQuote] = {}
        
        self.ws_thread = None
        self.running = False
        
        # Callbacks
        self.on_quote_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None
        
        log.info("WebSocket client initialized")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            if data.get('type') == 'quote':
                quote_data = data.get('data', {})
                
                # Parse quote data
                quote = WSQuote(
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
                    oi=int(quote_data.get('oi', 0)),
                    timestamp=datetime.now().isoformat()
                )
                
                # Cache quote
                key = f"{quote.exchange}:{quote.symbol}"
                self.quote_cache[key] = quote
                self.last_quote = quote
                
                # Invoke callback if set
                if self.on_quote_callback:
                    self.on_quote_callback(quote)
                
                log.debug(f"Quote received: {quote}")
                
            elif data.get('type') == 'ack':
                log.info(f"✅ WebSocket subscription acknowledged")
            
            elif data.get('type') == 'error':
                error_msg = data.get('message', 'Unknown error')
                log.error(f"❌ WebSocket error: {error_msg}")
                if self.on_error_callback:
                    self.on_error_callback(error_msg)
        
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            log.error(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        log.error(f"❌ WebSocket error: {error}")
        self.connected = False
        if self.on_error_callback:
            self.on_error_callback(str(error))
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        log.warning(f"⚠️  WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
    
    def _on_open(self, ws):
        """Handle WebSocket open."""
        log.info("✅ WebSocket connected")
        self.connected = True
        
        # Send subscription request
        self._subscribe_to_instruments()
    
    def _subscribe_to_instruments(self):
        """Subscribe to MCX Silver quotes."""
        try:
            # Angel One WebSocket subscription format
            subscription_payload = {
                "type": "subscribe",
                "mode": self.QUOTE_MODE,
                "tokenSet": [
                    {
                        "exchangeTokens": {
                            "MCX": ["SILVER"]  # MCX code for Silver
                        }
                    }
                ],
                "clientId": self.client_id
            }
            
            self.ws.send(json.dumps(subscription_payload))
            log.info("📡 Subscription request sent for MCX SILVER")
            
        except Exception as e:
            log.error(f"Failed to subscribe: {e}")
    
    def connect(self) -> bool:
        """
        Establish WebSocket connection with endpoint fallback.
        Tries multiple free-tier compatible endpoints.
        """
        # Headers for authentication
        header = [
            f"Authorization: Bearer {self.auth_token}",
            f"X-API-KEY: {self.api_key}",
            f"X-CLIENT-ID: {self.client_id}",
            "Connection: Upgrade",
            "Upgrade: websocket",
            "Sec-WebSocket-Version: 13"
        ]
        
        # Try each endpoint in fallback order
        for endpoint_idx, endpoint_url in enumerate(self.WS_URLS):
            try:
                log.info(f"🔌 Connecting to WebSocket [{endpoint_idx + 1}/{len(self.WS_URLS)}]: {endpoint_url}")
                
                # Set up WebSocket
                websocket.enableTrace(False)  # Set to True for debugging
                
                self.ws = websocket.WebSocketApp(
                    endpoint_url,
                    header=header,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )
                
                # Run in background thread
                self.running = True
                
                # Create SSL context with certifi certificates
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                
                self.ws_thread = threading.Thread(
                    target=self.ws.run_forever, 
                    kwargs={"sslopt": {"context": ssl_context}},
                    daemon=True
                )
                self.ws_thread.start()
                
                # Wait for connection to establish
                max_wait = 10
                elapsed = 0
                while not self.connected and elapsed < max_wait:
                    time.sleep(0.5)
                    elapsed += 0.5
                
                if self.connected:
                    log.info(f"✅ WebSocket connected successfully to: {endpoint_url}")
                    return True
                else:
                    log.warning(f"⚠️  Connection timeout on endpoint {endpoint_idx + 1}, trying next...")
                    self.running = False
                    if self.ws_thread:
                        self.ws_thread.join(timeout=2)
                    continue
            
            except Exception as e:
                log.warning(f"⚠️  Failed to connect to endpoint {endpoint_idx + 1}: {e}")
                self.running = False
                if self.ws_thread:
                    try:
                        self.ws_thread.join(timeout=2)
                    except:
                        pass
                continue
        
        log.error("❌ Failed to connect to any WebSocket endpoint")
        return False
    
    def disconnect(self):
        """Disconnect WebSocket."""
        try:
            self.running = False
            if self.ws:
                self.ws.close()
            if self.ws_thread:
                self.ws_thread.join(timeout=2)
            log.info("WebSocket disconnected")
        except Exception as e:
            log.error(f"Error disconnecting WebSocket: {e}")
    
    def get_quote(self, symbol: str = "SILVER", exchange: str = "MCX") -> Optional[WSQuote]:
        """Get latest cached quote."""
        key = f"{exchange}:{symbol}"
        return self.quote_cache.get(key)
    
    def set_quote_callback(self, callback: Callable):
        """Set callback function for new quotes."""
        self.on_quote_callback = callback
    
    def set_error_callback(self, callback: Callable):
        """Set callback function for errors."""
        self.on_error_callback = callback


# ────────────────────────────────────────────────────────────────────────────
# Integration with existing AngelOneConnector

def setup_websocket_quotes(connector):
    """
    Upgrade existing AngelOneConnector with WebSocket streaming.
    Call this after authentication to enable WebSocket quotes.
    """
    try:
        auth_token = connector.auth_token
        api_key = connector.api_key
        client_id = connector.client_id
        
        if not all([auth_token, api_key, client_id]):
            log.warning("⚠️  Missing credentials for WebSocket setup")
            return None
        
        ws_client = AngelOneWebSocketClient(auth_token, api_key, client_id)
        
        if ws_client.connect():
            log.info("✅ WebSocket quotes streaming enabled")
            return ws_client
        else:
            log.warning("⚠️  WebSocket connection failed, falling back to REST/replay")
            return None
    
    except Exception as e:
        log.error(f"Failed to setup WebSocket: {e}")
        return None


# ────────────────────────────────────────────────────────────────────────────
# Test the WebSocket client

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    import os
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    load_dotenv()
    
    auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')
    api_key = os.getenv('ANGEL_ONE_API_KEY')
    client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
    
    if not all([auth_token, api_key, client_id]):
        print("❌ Missing credentials in .env")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("Testing Angel One WebSocket Quote Streaming")
    print("="*80 + "\n")
    
    client = AngelOneWebSocketClient(auth_token, api_key, client_id)
    
    # Add callback to print quotes
    def on_quote(quote):
        print(f"📊 {quote}")
    
    client.set_quote_callback(on_quote)
    
    if client.connect():
        print("\n📡 Listening for quotes (Ctrl+C to stop)...\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopping WebSocket client...")
            client.disconnect()
            print("✅ Disconnected")
    else:
        print("❌ Failed to connect WebSocket")
        sys.exit(1)
