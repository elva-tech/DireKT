#!/usr/bin/env python3
"""
Angel One WebSocket Real-Time Data Feed
=======================================
Fetches OHLCV tick data + builds 1-minute bars for entry engine.

Features:
  • Angel One SmartAPI v3 binary protocol
  • TOTP 2FA authentication
  • Auto-reconnect with exponential backoff
  • Tick callbacks + OHLC bar aggregation
  • Compatible with entry engine signal generation

Usage:
  from angel_one_websocket_realtime import AngelOneRealTimeClient
  
  client = AngelOneRealTimeClient()
  await client.login()
  await client.connect(tokens=[{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
  await client.listen()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import struct
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import aiohttp
import pyotp
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  TICK DATA STRUCTURE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TickData:
    """Single tick from WebSocket feed."""
    symbol_token: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: int
    bid: float
    ask: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.symbol_token,
            "ltp": self.ltp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "oi": self.oi,
            "bid": self.bid,
            "ask": self.ask,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════
#  OHLC BAR BUILDER
# ═══════════════════════════════════════════════════════════════════

class OHLCBarBuilder:
    """Aggregates ticks into 1-minute OHLC bars."""

    def __init__(self, window: int = 500):
        self._bars: deque = deque(maxlen=window)
        self._current: Optional[Dict] = None
        self._current_minute: Optional[int] = None

    def update(self, tick: TickData) -> Optional[Dict]:
        """Returns completed bar when minute rolls over, else None."""
        minute_ts = tick.timestamp.replace(second=0, microsecond=0)
        minute_key = int(minute_ts.timestamp())

        if self._current_minute != minute_key:
            completed = dict(self._current) if self._current else None
            if completed:
                self._bars.append(completed)
            
            self._current = {
                "timestamp": minute_ts,
                "open": tick.ltp,
                "high": tick.ltp,
                "low": tick.ltp,
                "close": tick.ltp,
                "volume": tick.volume,
                "oi": tick.oi,
            }
            self._current_minute = minute_key
            return completed

        if self._current:
            self._current["high"] = max(self._current["high"], tick.ltp)
            self._current["low"] = min(self._current["low"], tick.ltp)
            self._current["close"] = tick.ltp
            self._current["volume"] = tick.volume
            self._current["oi"] = tick.oi

        return None

    def to_dataframe(self) -> pd.DataFrame:
        """Get all bars as DataFrame."""
        if not self._bars:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume", "oi"]
            )
        df = pd.DataFrame(list(self._bars))
        df.set_index("timestamp", inplace=True)
        return df

    @property
    def bar_count(self) -> int:
        return len(self._bars)


# ═══════════════════════════════════════════════════════════════════
#  ANGEL ONE WEBSOCKET CLIENT
# ═══════════════════════════════════════════════════════════════════

class AngelOneRealTimeClient:
    """
    Angel One SmartAPI WebSocket client for real-time OHLCV data.
    
    Binary frame format (token + LTP parsing):
      Token @ [2:27] → symbol identifier
      LTP @ [43]     → int32 LE / 100 → current price
      Volume @ [83]  → int32 LE
      OI @ [87]      → int32 LE
    """

    WS_URL = "wss://smartapisocket.angelone.in/smart-stream"
    REST_URL = "https://smartapi.angelbroking.com"
    MODE_LTP = 1
    MODE_QUOTE = 2

    def __init__(self):
        self.client_id = os.getenv("ANGEL_ONE_CLIENT_ID", "")
        self.password = os.getenv("ANGEL_ONE_PASSWORD", "")
        self.totp_secret = os.getenv("ANGEL_ONE_TOTP_SECRET", "")
        self.api_key = os.getenv("ANGEL_ONE_API_KEY", "")
        self.user_id = os.getenv("ANGEL_ONE_USER_ID", "")

        self.jwt_token: Optional[str] = None
        self.feed_token: Optional[str] = None

        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._is_connected = False
        self._shutdown_flag = False
        self._subscribed_tokens: List[Dict] = []
        self._reconnect_count = 0
        self._max_reconnects = 5
        self._reconnect_delay = 2.0

        self._tick_callbacks: List[Callable] = []
        self._bar_callbacks: List[Callable] = []
        self._connection_callbacks: List[Callable] = []

        self.bar_builder = OHLCBarBuilder(window=500)
        self._tick_count = 0
        self._heartbeat_task: Optional[asyncio.Task] = None

    # ── Callback Registration ─────────────────────────────────────

    def on_tick(self, fn: Callable):
        """Register handler for tick data."""
        self._tick_callbacks.append(fn)

    def on_bar(self, fn: Callable):
        """Register handler for completed 1-minute bars."""
        self._bar_callbacks.append(fn)

    def on_connection(self, fn: Callable):
        """Register handler for connection state changes."""
        self._connection_callbacks.append(fn)

    # ── Authentication ────────────────────────────────────────────

    def _generate_totp(self) -> str:
        """Generate TOTP token from secret."""
        return pyotp.TOTP(self.totp_secret).now()

    async def _create_session(self):
        """Create HTTPS session with SSL context."""
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_ctx)
        )

    async def login(self) -> bool:
        """Login to Angel One SmartAPI and get JWT + feed token."""
        try:
            if not self._session:
                await self._create_session()

            payload = {
                "clientcode": self.client_id,
                "password": self.password,
                "totp": self._generate_totp(),
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": self.api_key,
            }

            # Try multiple endpoints
            urls = [
                "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
                f"{self.REST_URL}/rest/auth/angelbroking/user/v1/loginByPassword",
            ]

            for url in urls:
                try:
                    async with self._session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status in (404, 405):
                            logger.warning(f"Skipping {url} (status={resp.status})")
                            continue

                        content_type = resp.headers.get("Content-Type", "")
                        if "text/html" in content_type:
                            logger.warning(f"Got HTML from {url}, skipping")
                            continue

                        try:
                            data = await resp.json()
                        except Exception as e:
                            logger.warning(f"Non-JSON response from {url}: {e}")
                            continue

                        if not data.get("status"):
                            logger.warning(f"Login failed: {data.get('message')}")
                            continue

                        if not data.get("data"):
                            continue

                        self.jwt_token = data["data"].get("jwtToken")
                        self.feed_token = data["data"].get("feedToken")

                        if self.jwt_token and self.feed_token:
                            logger.info("✅ Angel One login successful")
                            return True

                except asyncio.TimeoutError:
                    logger.warning(f"Login timeout at {url}")
                except Exception as e:
                    logger.warning(f"Login error at {url}: {e}")

            logger.error("❌ All login endpoints failed")
            return False

        except Exception as e:
            logger.error(f"Login exception: {e}")
            return False

    # ── WebSocket Connection ──────────────────────────────────────

    async def connect(self, tokens: List[Dict]) -> bool:
        """Connect to WebSocket and subscribe to instruments."""
        if not self.jwt_token:
            if not await self.login():
                return False

        self._subscribed_tokens = tokens

        try:
            logger.info(f"🔌 Connecting to {self.WS_URL}")
            self._ws = await self._session.ws_connect(
                self.WS_URL,
                headers=[
                    ("Authorization", self.jwt_token),
                    ("x-api-key", self.api_key),
                    ("x-client-code", self.client_id),
                    ("x-feed-token", self.feed_token),
                ],
                heartbeat=30,
            )

            self._is_connected = True
            self._reconnect_count = 0
            self._reconnect_delay = 2.0

            logger.info("✅ WebSocket connected")
            await self._notify_connection(True)
            await self._subscribe(tokens)
            
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            return True

        except Exception as e:
            logger.error(f"❌ WS connect error: {e}")
            await self._notify_connection(False)
            return False

    async def _subscribe(self, tokens: List[Dict]):
        """Send subscription request for tokens."""
        msg = {
            "correlationID": "entry_engine_sub",
            "action": 1,
            "params": {
                "mode": self.MODE_QUOTE,
                "tokenList": tokens,
            },
        }
        await self._ws.send_str(json.dumps(msg))
        logger.info(f"📡 Subscribed to {len(tokens)} token(s)")

    # ── Listen Loop ───────────────────────────────────────────────

    async def listen(self):
        """Blocking receive loop for WebSocket messages."""
        while not self._shutdown_flag:
            if not self._is_connected:
                if self._reconnect_count >= self._max_reconnects:
                    logger.error("❌ Max reconnections reached")
                    return

                await self._reconnect()
                continue

            try:
                async for msg in self._ws:
                    if self._shutdown_flag:
                        return

                    if msg.type == aiohttp.WSMsgType.BINARY:
                        await self._handle_binary(msg.data)
                    elif msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_text(msg.data)
                    elif msg.type in (
                        aiohttp.WSMsgType.ERROR,
                        aiohttp.WSMsgType.CLOSE,
                    ):
                        logger.warning(f"⚠️  WS closed/error: {msg.type}")
                        self._is_connected = False
                        await self._notify_connection(False)
                        break

            except Exception as e:
                if self._shutdown_flag:
                    return
                logger.error(f"❌ WS listen error: {e}")

            if self._is_connected:
                self._is_connected = False
                await self._notify_connection(False)

        logger.info("Listen loop exited")

    # ── Binary Frame Parser ───────────────────────────────────────

    async def _handle_binary(self, data: bytes):
        """
        Parse Angel One binary tick frame.
        
        Offsets (verified):
          [2:27]   token (25 bytes, null-padded)
          [43]     LTP int32 LE / 100
          [83]     volume int32 LE
          [87]     OI int32 LE
        """
        try:
            if len(data) < 51:
                return

            token = data[2:27].decode("utf-8").strip("\x00")

            tick_raw: Dict[str, Any] = {"token": token, "ltp": 0.0}

            if len(data) >= 123:
                try:
                    ltp = struct.unpack_from("<i", data, 43)[0] / 100.0
                    volume = struct.unpack_from("<i", data, 83)[0]
                    oi = struct.unpack_from("<i", data, 87)[0]

                    tick_raw.update({
                        "ltp": ltp,
                        "volume": volume,
                        "oi": oi,
                        "open": 0.0,
                        "high": 0.0,
                        "low": 0.0,
                        "close": 0.0,
                    })

                    # Debug first few ticks
                    if self._tick_count <= 2:
                        logger.info(
                            f"Tick {self._tick_count}: token={token} "
                            f"ltp={ltp:.2f} vol={volume} oi={oi}"
                        )

                except struct.error as e:
                    logger.debug(f"Binary parse error: {e}")
                    return

            tick = TickData(
                symbol_token=tick_raw.get("token", ""),
                ltp=tick_raw.get("ltp", 0.0),
                open=tick_raw.get("open", 0.0),
                high=tick_raw.get("high", 0.0),
                low=tick_raw.get("low", 0.0),
                close=tick_raw.get("close", 0.0),
                volume=tick_raw.get("volume", 0),
                oi=tick_raw.get("oi", 0),
                bid=0.0,
                ask=0.0,
                timestamp=datetime.now(),
            )

            await self._dispatch_tick(tick)
            self._tick_count += 1

        except Exception as e:
            logger.debug(f"Binary parse error: {e}")

    async def _handle_text(self, text: str):
        """Handle text frame (usually errors or status)."""
        try:
            data = json.loads(text)
            if data.get("type") == "error":
                logger.error(f"⚠️  WS error: {data.get('message')}")
        except Exception:
            pass

    async def _dispatch_tick(self, tick: TickData):
        """Call all registered tick callbacks."""
        for fn in self._tick_callbacks:
            try:
                if asyncio.iscoroutinefunction(fn):
                    await fn(tick)
                else:
                    fn(tick)
            except Exception as e:
                logger.error(f"Tick callback error: {e}")

        # Build OHLC bar
        completed_bar = self.bar_builder.update(tick)
        if completed_bar:
            for fn in self._bar_callbacks:
                try:
                    if asyncio.iscoroutinefunction(fn):
                        await fn(completed_bar)
                    else:
                        fn(completed_bar)
                except Exception as e:
                    logger.error(f"Bar callback error: {e}")

    async def _heartbeat_loop(self):
        """Send periodic heartbeat to keep connection alive."""
        while self._is_connected:
            try:
                await asyncio.sleep(25)
                if self._ws and not self._ws.closed:
                    await self._ws.ping()
            except Exception:
                break

    async def _reconnect(self):
        """Automatically reconnect with exponential backoff."""
        if self._shutdown_flag:
            return

        if self._reconnect_count >= self._max_reconnects:
            logger.error("❌ Max reconnections reached")
            self._shutdown_flag = True
            return

        self._reconnect_count += 1
        delay = min(self._reconnect_delay * (2 ** (self._reconnect_count - 1)), 60)

        logger.info(f"🔄 Reconnecting in {delay:.1f}s (attempt {self._reconnect_count})")
        await asyncio.sleep(delay)

        if self._shutdown_flag:
            return

        # Re-login every 3 attempts
        if self._reconnect_count % 3 == 0:
            await self.login()

        await self.connect(self._subscribed_tokens)

    async def _notify_connection(self, state: bool):
        """Notify all connection callbacks."""
        for fn in self._connection_callbacks:
            try:
                if asyncio.iscoroutinefunction(fn):
                    await fn(state)
                else:
                    fn(state)
            except Exception as e:
                logger.error(f"Connection callback error: {e}")

    # ── Data Access ───────────────────────────────────────────────

    def get_latest_ohlc(self) -> pd.DataFrame:
        """Get OHLC data as pandas DataFrame."""
        return self.bar_builder.to_dataframe()

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def tick_count(self) -> int:
        return self._tick_count

    # ── Cleanup ───────────────────────────────────────────────────

    async def disconnect(self):
        """Gracefully disconnect WebSocket."""
        self._shutdown_flag = True
        self._is_connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._ws:
            await self._ws.close()

        if self._session:
            await self._session.close()

        logger.info("WebSocket disconnected")


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE USAGE (for integration with entry engine)
# ═══════════════════════════════════════════════════════════════════

async def main():
    """Example: Connect and listen for real-time data."""
    client = AngelOneRealTimeClient()

    # Register tick handler (feed into entry engine)
    def on_tick(tick: TickData):
        logger.info(f"TICK: {tick.symbol_token} @ ₹{tick.ltp:.2f} Vol={tick.volume}")

    # Register bar handler (feed OHLC to signal generator)
    def on_bar(bar: Dict):
        logger.info(
            f"BAR: O={bar['open']:.2f} H={bar['high']:.2f} "
            f"L={bar['low']:.2f} C={bar['close']:.2f}"
        )

    def on_connection(state: bool):
        logger.info(f"Connection: {'🟢 LIVE' if state else '🔴 LOST'}")

    client.on_tick(on_tick)
    client.on_bar(on_bar)
    client.on_connection(on_connection)

    # Login and connect
    if not await client.login():
        logger.error("Login failed")
        return

    # Subscribe to MCX Silver
    tokens = [{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}]

    if not await client.connect(tokens):
        logger.error("Connection failed")
        return

    # Start listening (blocking)
    try:
        await client.listen()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
