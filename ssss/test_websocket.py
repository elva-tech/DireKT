#!/usr/bin/env python3
"""
Angel One WebSocket Test
======================
Test different WebSocket endpoints to find working one
"""

import asyncio
import websockets
import json
import logging
import ssl
import certifi
from datetime import datetime

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Create SSL context with certifi certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

async def test_websocket_endpoint(url, name):
    """Test a WebSocket endpoint."""
    try:
        log.info(f"🔄 Testing {name}: {url}")
        
        async with websockets.connect(url, timeout=10, ssl=ssl_context) as websocket:
            log.info(f"✅ Connected to {name}")
            
            # Send test message with proper Angel One format
            test_msg = {
                "type": "subscribe",
                "mode": "LTP",
                "tokenSet": [
                    {
                        "exchangeTokens": {
                            "MCX": ["SILVER"]
                        }
                    }
                ],
                "clientId": "AACE648379"
            }
            
            await websocket.send(json.dumps(test_msg))
            log.info(f"📤 Sent test message to {name}")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                log.info(f"📥 Response from {name}: {response[:100]}...")
                return True
            except asyncio.TimeoutError:
                log.warning(f"⏰ Timeout waiting for response from {name}")
                return False
                
    except Exception as e:
        log.error(f"❌ {name} failed: {e}")
        return False

async def main():
    """Test multiple WebSocket endpoints."""
    log.info("🔄 Testing Angel One WebSocket endpoints...")
    
    # Different possible endpoints
    endpoints = [
        ("wss://smartquotews.angelbroking.com/smart-stream", "Smart Quote Stream"),
        ("wss://smartapi.angelbroking.com/feed", "Main Feed"),
        ("wss://smartapi.angelbroking.com/NorenWS", "NorenWS"),
        ("wss://smartapi.angelbroking.com/ws", "WebSocket"),
    ]
    
    for url, name in endpoints:
        success = await test_websocket_endpoint(url, name)
        if success:
            log.info(f"✅ {name} works! URL: {url}")
            break
        else:
            log.info(f"❌ {name} failed")
        
        await asyncio.sleep(1)  # Brief pause between tests

if __name__ == "__main__":
    asyncio.run(main())
