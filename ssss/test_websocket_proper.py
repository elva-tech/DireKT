#!/usr/bin/env python3
"""
Angel One WebSocket Test (using same library as connector)
======================================================
Test WebSocket connection with proper Angel One authentication
"""

import websocket
import json
import logging
import threading
import time
import ssl
import certifi
from datetime import datetime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Create SSL context with certifi certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

class WebSocketTest:
    def __init__(self):
        self.auth_token = "eyJhbGciOiJIUzUxMiJ9.eyJ1c2VybmFtZSI6IkFBQ0U2NDgzNzkiLCJyb2xlcyI6MCwidXNlcnR5cGUiOiJVU0VSIiwidG9rZW4iOiJleUpoYkdjaU9pSlNVekkxTmlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKMWMyVnlYM1I1Y0dVaU9pSmpiR2xsYm5RaUxDSjBiMnRsYmw5MGVYQmxJam9pZEhKaFpHVmZZV05qWlhOelgzUnZhMlZ1SWl3aVoyMWZhV1FpT2pNc0luTnZkWEpqWlNJNklqTWlMQ0prWlhacFkyVmZhV1FpT2lJek5EVmxOak5tTmkxaU1ESTBMVE5pWmpBdFlUZGpPQzFrTXpGbFpUVmlNamRoWTJZaUxDSnJhV1FpT2lKMGNtRmtaVjlyWlhsZmRqSWlMQ0p2Ylc1bGJXRnVZV2RsY21sa0lqb3pMQ0p3Y201a2RXTjBjeUk2ZXlKa1pXMWhkQ0k2ZXlKemRHRjBkWE1pT2lKaFkzUnBkbVVpZlN3aWJXWWlPbnNpYzNSaGRIVnpJam9pWVdOMGFYWmxJbjE5TENKcGMzTWlPaUowY21Ga1pWOXNiMmRwYmw5elpYSjJhV05sSWl3aWMzVmlJam9pUVVGRFJUWTBPRE0zT1NJc0ltVjRjQ0k2TVRjM01qYzJNRFUxTlN3aWJtSm1Jam94TnpjeU5qY3pPVGMxTENKcFlYUWlPakUzTnpJMk56TTVOelVzSW1wMGFTSTZJbVU1WVRGaVpHUmlMVEJpTmpNdE5ETmtNUzA1WmpVMkxUTm1OREY0Wm1JelltTmpZU0lzSWxSdmEyVnVJam9pSW4wLkxRa2YxMUlLNnY4MkFmODlzV0t5TmdfdEEzWjFRRGdmUGZKLW9fR05taVZsdlZ6UjJRQk55WkhEbWFLT08zVExWaWViWWU3WUgwYmFnYW9HZjJMRURYcEFLSjdFOFdzcVRnR0lDSlZ1MjNaMWxwSDE1ekdiUHNtaXJDR1RCRm5rT2ZWX3hDRWV0M05wTk9yRWp0akRzNlc0VVhXZkJWSzZGWGtqSWtfa0RlSSIsIkFQSS1LRVkiOiJaenRiWVdRciIsIlgtT0xELUFQSS1LRVkiOmZhbHNlLCJpYXQiOjE3NzI2NzQxNTUsImV4cCI6MTc3MjczNTQwMH0.B2KrGW3la7Yzk_DA5x_LifQJKx4F5fggEIbp0GOelfJrquKg2X53oTjhHPHVZMqb9BU0fwm2X16wOl4YTkaPqw"
        self.api_key = "ZztbYWQr"
        self.client_id = "AACE648379"
        self.connected = False
        self.received_data = False
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            log.info(f"📥 Message received: {data}")
            self.received_data = True
            
            if data.get('type') == 'quote':
                quote_data = data.get('data', {})
                log.info(f"✅ Quote data: {quote_data}")
                
            elif data.get('type') == 'ack':
                log.info(f"✅ Subscription acknowledged")
                
            elif data.get('type') == 'error':
                error_msg = data.get('message', 'Unknown error')
                log.error(f"❌ WebSocket error: {error_msg}")
                
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse message: {e}")
        except Exception as e:
            log.error(f"Error processing message: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket error."""
        log.error(f"❌ WebSocket error: {error}")
        self.connected = False
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        log.warning(f"⚠️  WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
    
    def on_open(self, ws):
        """Handle WebSocket open."""
        log.info("✅ WebSocket connected")
        self.connected = True
        
        # Send subscription request
        subscription_payload = {
            "type": "subscribe",
            "mode": "LTP",
            "tokenSet": [
                {
                    "exchangeTokens": {
                        "MCX": ["SILVER"]
                    }
                }
            ],
            "clientId": self.client_id
        }
        
        ws.send(json.dumps(subscription_payload))
        log.info("📡 Subscription request sent for MCX SILVER")
    
    def test_connection(self, url):
        """Test WebSocket connection to given URL."""
        try:
            log.info(f"🔄 Testing: {url}")
            
            # Headers for authentication
            header = [
                f"Authorization: Bearer {self.auth_token}",
                f"X-API-KEY: {self.api_key}",
                f"X-CLIENT-ID: {self.client_id}"
            ]
            
            # Create WebSocket app
            ws = websocket.WebSocketApp(
                url,
                header=header,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # Run for a limited time
            def run_websocket():
                ws.run_forever()
            
            thread = threading.Thread(target=run_websocket, daemon=True)
            thread.start()
            
            # Wait for connection or data
            for i in range(10):  # Wait 10 seconds
                if self.connected or self.received_data:
                    log.info(f"✅ Success with {url}")
                    return True
                time.sleep(1)
            
            log.info(f"❌ Timeout with {url}")
            return False
            
        except Exception as e:
            log.error(f"❌ Connection failed: {e}")
            return False

def main():
    """Test Angel One WebSocket endpoints."""
    log.info("🔄 Testing Angel One WebSocket (proper library)...")
    
    tester = WebSocketTest()
    
    # Test endpoints
    endpoints = [
        "wss://smartquotews.angelbroking.com/smart-stream",
        "wss://smartapi.angelbroking.com/feed",
        "wss://smartapi.angelbroking.com/NorenWS",
    ]
    
    for url in endpoints:
        success = tester.test_connection(url)
        if success:
            log.info(f"✅ Working endpoint found: {url}")
            break
        else:
            log.info(f"❌ Failed: {url}")
        
        time.sleep(2)  # Brief pause between tests

if __name__ == "__main__":
    main()
