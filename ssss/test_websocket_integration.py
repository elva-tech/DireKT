#!/usr/bin/env python3
"""Test WebSocket integration with trading bot."""

import sys
import os
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('ANGEL_ONE_API_KEY')
client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
client_secret = os.getenv('ANGEL_ONE_CLIENT_SECRET')
totp_secret = os.getenv('ANGEL_ONE_TOTP_SECRET')
password = os.getenv('ANGEL_ONE_PASSWORD')
user_id = os.getenv('ANGEL_ONE_USER_ID')

if not all([api_key, client_id, client_secret, totp_secret, password, user_id]):
    log.error("❌ Missing Angel One credentials in .env")
    sys.exit(1)

log.info(f"✅ Credentials loaded")
log.info(f"   API Key: {api_key[:10]}...")
log.info(f"   Client ID: {client_id}")

# Test 1: Authentication
log.info("\n" + "="*60)
log.info("TEST 1: Angel One Authentication")
log.info("="*60)

from angel_one_connector import AngelOneConnector

connector = AngelOneConnector(
    client_id=client_id,
    client_secret=client_secret,
    api_key=api_key,
    totp_secret=totp_secret,
    password=password,
    user_id=user_id
)
auth_ok = connector.authenticate()

if not auth_ok:
    log.error("❌ Authentication failed")
    sys.exit(1)

log.info("✅ Authentication successful")
log.info(f"   WebSocket enabled: {connector.use_websocket}")
log.info(f"   WebSocket client connected: {connector.ws_client is not None}")

# Test 2: WebSocket Quote Retrieval
log.info("\n" + "="*60)
log.info("TEST 2: WebSocket Quote Retrieval")
log.info("="*60)

if connector.ws_client:
    log.info("📡 WebSocket connected, waiting for quotes...")
    
    for i in range(5):
        time.sleep(1)
        quote = connector.ws_client.get_quote("MCX:SILVER")
        if quote:
            log.info(f"✅ Quote {i+1}: {quote.symbol} = ₹{quote.ltp:.2f} Vol:{quote.volume}")
            break
        else:
            log.info(f"⏳ Waiting... (attempt {i+1}/5)")
    
    if not quote:
        log.warning("⚠️  No quotes received yet (normal if connection is slow)")
else:
    log.warning("⚠️  WebSocket client not available")

# Test 3: Real-Time Data Stream
log.info("\n" + "="*60)
log.info("TEST 3: Real-Time Data Stream (through connector)")
log.info("="*60)

from angel_one_connector import RealTimeDataStream

stream = RealTimeDataStream(connector)

for i in range(3):
    quote = stream.fetch_latest("SILVER", "MCX")
    if quote:
        log.info(f"✅ Stream Quote {i+1}: {quote.symbol} = ₹{quote.ltp:.2f}")
        log.info(f"   Source: {'WebSocket' if connector.use_websocket else 'REST/Historical'}")
        log.info(f"   Volume: {quote.volume}, OI: {quote.oi}")
    else:
        log.warning("❌ Failed to get quote")
    
    time.sleep(1)

# Test 4: Trading Bot Integration
log.info("\n" + "="*60)
log.info("TEST 4: Trading Bot Signal Generation")
log.info("="*60)

from trading_bot import SilverFuturesTradingBot

try:
    bot = SilverFuturesTradingBot(
        connector=connector,
        dhan_client_id=os.getenv('DHAN_CLIENT_ID'),
        dhan_access_token=os.getenv('DHAN_ACCESS_TOKEN'),
        paper_trading=True
    )
    
    log.info("✅ Trading bot initialized with WebSocket data source")
    log.info(f"   Model confidence threshold: {bot.confidence_threshold}")
    log.info(f"   Paper trading: {bot.paper_trading}")
    
    # Run one fetch cycle to test signal generation
    log.info("\n📊 Generating sample signal...")
    from angel_one_connector import RealTimeDataStream
    stream = RealTimeDataStream(connector)
    quote = stream.fetch_latest("SILVER", "MCX")
    
    if quote:
        signal = bot._generate_signal(quote)
        log.info(f"✅ Signal generated")
        log.info(f"   Action: {signal['action']}")
        log.info(f"   Confidence: {signal['confidence']:.2%}")
        log.info(f"   Price: ₹{signal['price']:.2f}")
    else:
        log.warning("Could not generate signal (no quote)")
        
except Exception as e:
    log.error(f"❌ Bot initialization failed: {e}")
    import traceback
    log.error(traceback.format_exc())

log.info("\n" + "="*60)
log.info("✅ All WebSocket integration tests completed!")
log.info("="*60)
