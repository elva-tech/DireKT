#!/usr/bin/env python3
"""Quick WebSocket test with new endpoint"""

import sys
import os
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

import websocket
import json
import logging
import ssl
import certifi

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Test the new endpoint
NEW_ENDPOINT = "wss://smartapisocket.angelone.in/smart-stream"

log.info(f"Testing new endpoint: {NEW_ENDPOINT}")

auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')
api_key = os.getenv('ANGEL_ONE_API_KEY')
client_id = os.getenv('ANGEL_ONE_CLIENT_ID')

headers = [
    f"Authorization: Bearer {auth_token}",
    f"X-API-KEY: {api_key}",
    f"X-CLIENT-ID: {client_id}",
    "Connection: Upgrade",
    "Upgrade: websocket",
    "Sec-WebSocket-Version: 13"
]

def on_message(ws, message):
    log.info(f"✅ Message received: {message[:100]}...")
    ws.close()

def on_error(ws, error):
    log.error(f"❌ WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    log.info(f"⚠️ WebSocket closed: {close_status_code}")

def on_open(ws):
    log.info("✅ WebSocket connected!")
    
    subscription = {
        "type": "subscribe",
        "mode": "QUOTE",
        "tokenSet": [{
            "exchangeTokens": {
                "MCX": ["SILVER"]
            }
        }],
        "clientId": client_id
    }
    
    ws.send(json.dumps(subscription))
    log.info("📡 Subscription sent for MCX SILVER")

try:
    websocket.enableTrace(False)
    
    ws = websocket.WebSocketApp(
        NEW_ENDPOINT,
        header=headers,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    
    log.info("🔌 Attempting connection...")
    ws.run_forever(sslopt={"context": ssl_context}, ping_interval=30)
    
except Exception as e:
    log.error(f"❌ Exception: {e}")
