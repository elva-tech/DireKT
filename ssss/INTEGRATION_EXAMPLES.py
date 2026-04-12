#!/usr/bin/env python3
"""
Integration Template: Connect WebSocket to Your Existing Entry Engine
======================================================================

Use this template to integrate the Angel One WebSocket client
with your existing entry signal generation code.

Example: Merging with `entry_algo.py` or similar
"""

import asyncio
import logging
from angel_one_websocket_realtime import AngelOneRealTimeClient, TickData

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 1: Basic Integration
# ═══════════════════════════════════════════════════════════════════

async def example_basic():
    """
    Simplest integration: feed live data to your signal function.
    """
    from angel_one_websocket_realtime import AngelOneRealTimeClient

    client = AngelOneRealTimeClient()

    # Your existing signal generation function
    def my_signal_generator(bar):
        """Replace with your existing signal logic."""
        close = bar["close"]
        volume = bar["volume"]
        
        # Example: your custom logic
        if close > 28000 and volume > 1000:
            return {"signal": "BUY", "price": close}
        return None

    # Connect WebSocket callback to your logic
    async def on_bar(bar):
        signal = my_signal_generator(bar)
        if signal:
            logger.info(f"Signal: {signal['signal']} @ {signal['price']}")
            # Execute your order placement logic
            # await place_order(signal)

    client.on_bar(on_bar)

    # Start WebSocket
    await client.login()
    await client.connect([{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
    await client.listen()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 2: Use OHLC DataFrame for Technical Analysis
# ═══════════════════════════════════════════════════════════════════

async def example_with_dataframe():
    """
    Use OHLC data as pandas DataFrame for advanced analysis.
    """
    import pandas as pd
    from angel_one_websocket_realtime import AngelOneRealTimeClient

    client = AngelOneRealTimeClient()

    def calculate_signals(df: pd.DataFrame):
        """Your technical analysis function."""
        if len(df) < 20:
            return None

        close = df['close'].iloc[-1]
        sma20 = df['close'].rolling(20).mean().iloc[-1]
        rsi = calculate_rsi(df['close'], 14)  # Your RSI function

        # Your signal logic
        if close > sma20 and rsi < 70:
            return {"signal": "BUY", "price": close, "rsi": rsi}
        elif close < sma20 and rsi > 30:
            return {"signal": "SELL", "price": close, "rsi": rsi}
        
        return None

    def on_bar(bar):
        # Get all bars as DataFrame
        df = client.bar_builder.to_dataframe()
        
        signal = calculate_signals(df)
        if signal:
            logger.info(f"Signal: {signal}")

    client.on_bar(on_bar)

    await client.login()
    await client.connect([{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
    await client.listen()


def calculate_rsi(prices, period=14):
    """Example: Your existing RSI calculation."""
    if len(prices) < period:
        return 50
    
    changes = prices.diff()
    gains = (changes.where(changes > 0, 0)).rolling(window=period).mean()
    losses = (-changes.where(changes < 0, 0)).rolling(window=period).mean()
    
    rs = gains / losses
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 3: Multi-instrument with different strategies
# ═══════════════════════════════════════════════════════════════════

async def example_multi_instrument():
    """
    Track multiple instruments with different signal strategies.
    """
    client = AngelOneRealTimeClient()
    
    # Store strategy per instrument
    strategies = {
        "SILVER05MAY26FUT": {
            "name": "Silver Momentum",
            "signals": [],
            "params": {"sma_period": 20, "volume_threshold": 1000}
        },
        "GOLD05MAY26FUT": {
            "name": "Gold Breakout",
            "signals": [],
            "params": {"sma_period": 10, "volume_threshold": 500}
        }
    }

    def on_bar(bar):
        # Example: bar includes symbol info if available
        # Use strategies[symbol] to apply per-instrument logic
        pass

    client.on_bar(on_bar)

    # Subscribe to multiple instruments
    tokens = [
        {"exchangeTokens": {
            "MCX": ["SILVER05MAY26FUT", "GOLD05MAY26FUT"]
        }}
    ]

    await client.login()
    await client.connect(tokens)
    await client.listen()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 4: Connect to Existing Entry Engine Class
# ═══════════════════════════════════════════════════════════════════

class MyExistingEntryEngine:
    """Your existing entry engine class."""
    
    def __init__(self):
        self.positions = {}
        self.signals = []
    
    def generate_signal(self, bar):
        """Your existing signal logic."""
        # Your existing code here
        return None
    
    def place_order(self, signal):
        """Your existing order execution."""
        pass


async def example_integrate_existing_engine():
    """
    Integrate WebSocket with your existing entry engine class.
    """
    from angel_one_websocket_realtime import AngelOneRealTimeClient

    client = AngelOneRealTimeClient()
    engine = MyExistingEntryEngine()

    # Connect WebSocket to your engine methods
    def on_bar(bar):
        signal = engine.generate_signal(bar)
        if signal:
            engine.place_order(signal)

    def on_tick(tick):
        # Could update real-time price display, etc.
        pass

    def on_connection(state):
        logger.info(f"Engine connection: {'online' if state else 'offline'}")

    client.on_bar(on_bar)
    client.on_tick(on_tick)
    client.on_connection(on_connection)

    await client.login()
    await client.connect([{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
    await client.listen()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 5: Custom Signal Aggregation (Multiple Indicators)
# ═══════════════════════════════════════════════════════════════════

class MultiIndicatorSignal:
    """Combine multiple indicators for robust signals."""
    
    def __init__(self):
        self.prices = []
        self.volumes = []
    
    def process_bar(self, bar):
        """Generate signal from multiple indicators."""
        self.prices.append(bar["close"])
        self.volumes.append(bar["volume"])
        
        if len(self.prices) < 20:
            return None
        
        # Calculate indicators
        sma20 = sum(self.prices[-20:]) / 20
        rsi = self._calc_rsi()
        trend = self._calc_trend()
        
        # Voting system
        votes = 0
        if bar["close"] > sma20:
            votes += 1
        if rsi < 30:
            votes += 1
        if trend == "up":
            votes += 1
        
        # Signal confidence
        confidence = votes / 3.0 * 100
        
        if votes >= 2:
            return {
                "signal": "BUY",
                "price": bar["close"],
                "confidence": confidence,
                "indicators": {"sma20": sma20, "rsi": rsi, "trend": trend}
            }
        
        return None
    
    def _calc_rsi(self):
        """Your RSI calculation."""
        return 50  # Placeholder
    
    def _calc_trend(self):
        """Your trend detection."""
        return "up"  # Placeholder


async def example_multi_indicator():
    """Example using custom multi-indicator signal generator."""
    from angel_one_websocket_realtime import AngelOneRealTimeClient

    client = AngelOneRealTimeClient()
    signal_gen = MultiIndicatorSignal()

    def on_bar(bar):
        signal = signal_gen.process_bar(bar)
        if signal:
            logger.info(
                f"Signal: {signal['signal']} @ {signal['price']} "
                f"({signal['confidence']:.1f}% confidence)"
            )

    client.on_bar(on_bar)

    await client.login()
    await client.connect([{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
    await client.listen()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 6: Rate Limiting (Avoid Over-Trading)
# ═══════════════════════════════════════════════════════════════════

class RateLimitedSignals:
    """Generate signals with minimum time between trades."""
    
    def __init__(self, min_seconds_between_trades=300):
        self.min_seconds = min_seconds_between_trades
        self.last_signal_time = None
        self.signal_count = 0
    
    def should_trade(self):
        """Check if enough time has passed since last signal."""
        if self.last_signal_time is None:
            return True
        
        from datetime import datetime
        elapsed = (datetime.now() - self.last_signal_time).total_seconds()
        return elapsed >= self.min_seconds
    
    def on_signal(self, signal):
        """Process signal with rate limiting."""
        if not self.should_trade():
            logger.debug(f"Skipping signal, rate limited")
            return None
        
        self.last_signal_time = datetime.now()
        self.signal_count += 1
        return signal


async def example_rate_limited():
    """Example with rate limiting."""
    from angel_one_websocket_realtime import AngelOneRealTimeClient
    from datetime import datetime

    client = AngelOneRealTimeClient()
    rate_limiter = RateLimitedSignals(min_seconds_between_trades=300)

    def on_bar(bar):
        # Your signal generation
        if bar["close"] > 28000:
            signal = {"signal": "BUY", "price": bar["close"]}
            
            # Apply rate limiting
            if rate_limiter.should_trade():
                logger.info(f"Executing: {signal}")
                rate_limiter.last_signal_time = datetime.now()
            else:
                logger.debug("Signal filtered (rate limited)")

    client.on_bar(on_bar)

    await client.login()
    await client.connect([{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
    await client.listen()


# ═══════════════════════════════════════════════════════════════════
#  MAIN SELECTOR
# ═══════════════════════════════════════════════════════════════════

async def main():
    """Run desired example."""
    
    # Choose which example to run:
    examples = {
        "1": ("Basic integration", example_basic),
        "2": ("DataFrame analysis", example_with_dataframe),
        "3": ("Multi-instrument", example_multi_instrument),
        "4": ("Existing engine", example_integrate_existing_engine),
        "5": ("Multi-indicator", example_multi_indicator),
        "6": ("Rate limited", example_rate_limited),
    }
    
    for key, (name, _) in examples.items():
        print(f"{key}. {name}")
    
    choice = input("\nSelect example (1-6, or press Enter for default): ").strip() or "1"
    
    if choice in examples:
        _, example_func = examples[choice]
        await example_func()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Or directly run specific example:
    # asyncio.run(example_basic())
    
    asyncio.run(main())
