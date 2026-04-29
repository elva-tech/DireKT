#!/usr/bin/env python3
"""
Entry Engine + Real-Time WebSocket Integration
===============================================
Feeds live Angel One WebSocket data into entry signal generation.

Components:
  1. AngelOneRealTimeClient → live ticks + OHLC bars
  2. Entry signal callbacks  → process bars & generate BUY/SELL signals
  3. Signal executor        → submit orders to Dhan (paper/live)

Usage:
  python3 entry_engine_with_websocket.py
"""

import asyncio
import logging
import os
from datetime import datetime, time
from typing import Dict, List, Optional

from dotenv import load_dotenv
from angel_one_websocket_realtime import (
    AngelOneRealTimeClient,
    TickData,
)

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


# ═══════════════════════════════════════════════════════════════════
#  SIMPLE ENTRY SIGNAL GENERATOR
# ═══════════════════════════════════════════════════════════════════

class EntrySignalGenerator:
    """
    Generates BUY/SELL signals from real-time OHLC bars.
    
    Example signals (customize as needed):
      • BUY: Close > SMA(20) & volume > avg_volume
      • SELL: Close < SMA(20) & volume > avg_volume
    """

    def __init__(self):
        self.symbol = "SILVER05MAY26FUT"
        self.prices: List[float] = []
        self.volumes: List[int] = []
        self.signal_log: List[Dict] = []

    def process_bar(self, bar: Dict) -> Optional[Dict]:
        """
        Process OHLC bar and return signal (or None).
        
        Returns: {"signal": "BUY"|"SELL", "price": 28000.5, "timestamp": "..."}
        """
        close = bar["close"]
        volume = bar["volume"]
        timestamp = bar["timestamp"]

        self.prices.append(close)
        self.volumes.append(volume)

        # Keep last 20 bars for trend analysis
        if len(self.prices) > 20:
            self.prices.pop(0)
            self.volumes.pop(0)

        if len(self.prices) < 3:
            return None  # Need minimum data

        # SMA20 calc
        sma20 = sum(self.prices[-20:]) / min(len(self.prices), 20)
        avg_vol = sum(self.volumes[-10:]) / min(len(self.volumes), 10)

        signal = None

        # BUY signal: Close > SMA20 & Volume uptick
        if close > sma20 and volume > avg_vol * 1.1:
            signal = "BUY"
            logger.info(
                f"📈 BUY SIGNAL @ {timestamp}"
                f" | Price={close:.2f} > SMA={sma20:.2f}"
                f" | Vol={volume} > Avg={avg_vol:.0f}"
            )

        # SELL signal: Close < SMA20 & Volume uptick
        elif close < sma20 and volume > avg_vol * 1.1:
            signal = "SELL"
            logger.info(
                f"📉 SELL SIGNAL @ {timestamp}"
                f" | Price={close:.2f} < SMA={sma20:.2f}"
                f" | Vol={volume} > Avg={avg_vol:.0f}"
            )

        if signal:
            event = {
                "signal": signal,
                "price": close,
                "timestamp": timestamp,
                "sma20": sma20,
                "volume": volume,
            }
            self.signal_log.append(event)
            return event

        return None


# ═══════════════════════════════════════════════════════════════════
#  ORDER EXECUTOR (Dhan)
# ═══════════════════════════════════════════════════════════════════

class OrderExecutor:
    """
    Execute orders on Dhan (paper or live trading).
    
    For now, logs signals. In production:
      - Connect to Dhan API
      - Place orders with risk management
      - Track P&L
    """

    def __init__(self, paper_mode: bool = True):
        self.paper_mode = paper_mode
        self.active_positions: Dict[str, Dict] = {}
        self.execution_log: List[Dict] = []

    async def on_signal(self, signal: Dict):
        """Execute trade when signal is received."""
        if self.paper_mode:
            logger.info(
                f"📋 [PAPER MODE] {signal['signal']} @ ₹{signal['price']:.2f}"
            )
        else:
            logger.info(
                f"🚀 [LIVE MODE] Executing {signal['signal']} @ ₹{signal['price']:.2f}"
            )

        self.execution_log.append({
            **signal,
            "executed_at": datetime.now().isoformat(),
            "mode": "paper" if self.paper_mode else "live",
        })


# ═══════════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════

class EntryEngineOrchestrator:
    """
    Coordinates WebSocket → Signal Generation → Order Execution.
    """

    def __init__(self, paper_mode: bool = True):
        self.ws_client = AngelOneRealTimeClient()
        self.signal_generator = EntrySignalGenerator()
        self.executor = OrderExecutor(paper_mode=paper_mode)
        self.paper_mode = paper_mode

        # Register callbacks
        self.ws_client.on_tick(self._on_tick)
        self.ws_client.on_bar(self._on_bar)
        self.ws_client.on_connection(self._on_connection)

    async def _on_tick(self, tick: TickData):
        """Tick received from WebSocket."""
        pass  # Could stream to UI or store for analysis

    async def _on_bar(self, bar: Dict):
        """OHLC bar completed - generate signals."""
        logger.debug(
            f"BAR: {bar['timestamp']} | "
            f"OHLC={bar['open']:.2f}/{bar['high']:.2f}/"
            f"{bar['low']:.2f}/{bar['close']:.2f} "
            f"Vol={bar['volume']}"
        )

        signal = self.signal_generator.process_bar(bar)
        if signal:
            await self.executor.on_signal(signal)

    async def _on_connection(self, state: bool):
        """Connection state changed."""
        status = "🟢 CONNECTED" if state else "🔴 DISCONNECTED"
        logger.info(f"WebSocket {status}")

    async def start(self, instruments: List[Dict]):
        """Start entry engine."""
        logger.info("=" * 60)
        logger.info("🚀 ENTRY ENGINE STARTING")
        logger.info(f"   Mode: {'📋 PAPER' if self.paper_mode else '💰 LIVE'}")
        logger.info(f"   Instruments: {len(instruments)}")
        logger.info("=" * 60)

        # Login
        if not await self.ws_client.login():
            logger.error("❌ Login failed")
            return

        # Connect
        if not await self.ws_client.connect(instruments):
            logger.error("❌ Connection failed")
            return

        # Listen for signals (blocking)
        try:
            await self.ws_client.listen()
        except KeyboardInterrupt:
            logger.info("\n⏹️  Shutdown requested")
        finally:
            await self.stop()

    async def stop(self):
        """Gracefully stop entry engine."""
        logger.info("🛑 Stopping entry engine...")
        await self.ws_client.disconnect()

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 SESSION SUMMARY")
        logger.info(f"   Ticks received: {self.ws_client.tick_count}")
        logger.info(f"   Bars built: {self.signal_generator.signal_log.__len__()}")
        logger.info(f"   Signals generated: {len(self.signal_generator.signal_log)}")
        logger.info(f"   Orders executed: {len(self.executor.execution_log)}")

        if self.signal_generator.signal_log:
            logger.info("\n   Signals:")
            for sig in self.signal_generator.signal_log[-5:]:  # Last 5
                logger.info(
                    f"     {sig['timestamp']} → "
                    f"{sig['signal']} @ ₹{sig['price']:.2f}"
                )
        logger.info("=" * 60)


# ═══════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

async def main():
    """Run entry engine with real-time WebSocket feed."""

    # Configuration
    PAPER_MODE = True  # Set False for live trading
    INSTRUMENTS = [
        {"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}
    ]

    # Create and start orchestrator
    entry_engine = EntryEngineOrchestrator(paper_mode=PAPER_MODE)
    await entry_engine.start(INSTRUMENTS)


if __name__ == "__main__":
    asyncio.run(main())
