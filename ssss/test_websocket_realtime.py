#!/usr/bin/env python3
"""
Quick test: Verify WebSocket connection and real-time data fetch.
Run: python3 test_websocket_realtime.py
"""

import asyncio
import logging
from datetime import datetime
from angel_one_websocket_realtime import AngelOneRealTimeClient, TickData

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def test_websocket():
    """Test WebSocket connection + data fetch."""
    
    client = AngelOneRealTimeClient()
    tick_count = 0
    bar_count = 0

    def on_tick(tick: TickData):
        nonlocal tick_count
        tick_count += 1
        if tick_count <= 5:
            logger.info(
                f"✓ Tick {tick_count}: {tick.symbol_token} "
                f"@ ₹{tick.ltp:.2f} | Vol={tick.volume} | OI={tick.oi}"
            )

    def on_bar(bar):
        nonlocal bar_count
        bar_count += 1
        logger.info(
            f"✓ Bar {bar_count}: OHLC="
            f"{bar['open']:.2f}/{bar['high']:.2f}/"
            f"{bar['low']:.2f}/{bar['close']:.2f} "
            f"@ {bar['timestamp']}"
        )

    def on_connection(state: bool):
        logger.info(f"Connection: {'🟢 LIVE' if state else '🔴 LOST'}")

    client.on_tick(on_tick)
    client.on_bar(on_bar)
    client.on_connection(on_connection)

    # Login
    logger.info("🔐 Authenticating with Angel One...")
    if not await client.login():
        logger.error("❌ Authentication failed")
        return

    # Connect to WebSocket
    logger.info("🔌 Connecting to WebSocket...")
    tokens = [{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}]
    if not await client.connect(tokens):
        logger.error("❌ WebSocket connection failed")
        return

    # Listen for 30 seconds
    logger.info("📡 Listening for 30 seconds... (Ctrl+C to stop)")
    try:
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        logger.info("⏹️  Stopped by user")

    # Disconnect
    await client.disconnect()

    # Print results
    logger.info("\n" + "=" * 60)
    logger.info("✅ TEST SUMMARY")
    logger.info(f"   Ticks received: {tick_count}")
    logger.info(f"   Bars built: {bar_count}")
    logger.info(f"   WebSocket Status: {'Connected' if client.is_connected else 'Disconnected'}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_websocket())
