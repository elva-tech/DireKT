#!/usr/bin/env python3
"""Test the fixed WebSocket client with free-tier endpoints"""

import sys
import os
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from angel_one_websocket import AngelOneWebSocketClient
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# Get credentials from environment
api_key = os.getenv('ANGEL_ONE_API_KEY')
client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')

if not all([api_key, client_id, auth_token]):
    log.error("❌ Missing credentials in .env file")
    sys.exit(1)

log.info("🚀 Starting WebSocket test with free-tier endpoints...")
log.info(f"Client ID: {client_id}")
log.info(f"API Key: {api_key}")

# Create WebSocket client
client = AngelOneWebSocketClient(auth_token, api_key, client_id)

# Track quotes received
quotes_received = []

def on_quote_received(quote):
    """Callback when quote received"""
    quotes_received.append(quote)
    log.info(f"📊 Quote received: {quote.exchange}:{quote.symbol} = ₹{quote.ltp}")

def on_error_received(error):
    """Callback when error occurs"""
    log.error(f"❌ WebSocket error: {error}")

# Set callbacks
client.set_quote_callback(on_quote_received)
client.set_error_callback(on_error_received)

# Attempt to connect
log.info("🔌 Attempting to connect...")
if client.connect():
    log.info("✅ WebSocket connected successfully!")
    
    # Wait for quotes
    log.info("⏳ Waiting 20 seconds for quotes...")
    time.sleep(20)
    
    # Get latest quote
    quote = client.get_quote("SILVER", "MCX")
    if quote:
        log.info(f"📊 Current SILVER quote: ₹{quote.ltp}")
    
    # Disconnect
    client.disconnect()
    
    # Report results
    log.info(f"\n" + "="*60)
    log.info(f"✅ TEST PASSED")
    log.info(f"Quotes received: {len(quotes_received)}")
    log.info(f"Free-tier endpoints working!")
    log.info(f"="*60)
else:
    log.error(f"\n" + "="*60)
    log.error(f"❌ TEST FAILED - Could not connect to any endpoint")
    log.error(f"Check WebSocket endpoints configuration")
    log.error(f"="*60)
    sys.exit(1)
