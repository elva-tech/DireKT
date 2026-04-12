# WebSocket Real-Time Data Client - Quick Reference

## Files Created

| File | Purpose |
|------|---------|
| `angel_one_websocket_realtime.py` | Core WebSocket client + OHLC builder |
| `entry_engine_with_websocket.py` | Entry signal generator + orchestrator |
| `test_websocket_realtime.py` | Connection test utility |
| `WEBSOCKET_REALTIME_README.md` | Complete documentation |

## 30-Second Startup

```bash
# 1. Install deps
pip install aiohttp pyotp pandas python-dotenv

# 2. Test connection (30 seconds)
python3 test_websocket_realtime.py

# 3. Run entry engine
python3 entry_engine_with_websocket.py
```

## Core Classes

### AngelOneRealTimeClient
```python
# Initialize
client = AngelOneRealTimeClient()

# Register callbacks
client.on_tick(lambda tick: ...)
client.on_bar(lambda bar: ...)
client.on_connection(lambda state: ...)

# Connect
await client.login()
await client.connect([{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
await client.listen()

# Data access
df = client.bar_builder.to_dataframe()
print(f"Ticks: {client.tick_count}")
print(f"Connected: {client.is_connected}")
```

### EntrySignalGenerator
```python
gen = EntrySignalGenerator()

# Process OHLC bar
signal = gen.process_bar(bar)
# Returns: {"signal": "BUY"|"SELL", "price": 28000.5, "timestamp": "..."}
# Or: None (no signal)

# Access history
signals = gen.signal_log  # List of all signals
```

### EntryEngineOrchestrator
```python
engine = EntryEngineOrchestrator(paper_mode=True)
await engine.start([{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}])
```

## Data Types

### TickData (from tick callback)
```python
tick.symbol_token    # "SILVER05MAY26FUT"
tick.ltp             # 28000.50 (float)
tick.volume          # 1250 (int)
tick.oi              # 15000 (int)
tick.timestamp       # datetime object
```

### OHLC Bar (from bar callback)
```python
bar["timestamp"]     # datetime object
bar["open"]          # float
bar["high"]          # float
bar["low"]           # float
bar["close"]         # float
bar["volume"]        # int
bar["oi"]            # int
```

## Common Operations

### Get latest OHLC as DataFrame
```python
df = client.bar_builder.to_dataframe()
# Columns: open, high, low, close, volume, oi
# Index: timestamp

# Calculate SMA
df['sma20'] = df['close'].rolling(20).mean()
```

### Filter signals
```python
buy_signals = [s for s in gen.signal_log if s['signal'] == 'BUY']
sell_signals = [s for s in gen.signal_log if s['signal'] == 'SELL']
```

### Check connection status
```python
if client.is_connected:
    print("✅ Live")
else:
    print("🔴 Disconnected")
```

## Customization

### Change signal logic
Edit `EntrySignalGenerator.process_bar()`:
```python
def process_bar(self, bar):
    close = bar["close"]
    # Your logic here
    if your_condition():
        return {"signal": "BUY", "price": close, "timestamp": bar["timestamp"]}
    return None
```

### Add more indicators
```python
# In process_bar, add:
atr = calculate_atr(self.prices[-14:])  # 14-period ATR
rsi = calculate_rsi(self.prices[-14:])  # 14-period RSI

if rsi < 30:  # Oversold
    return {"signal": "BUY", ...}
```

### Filter signals (avoid over-trading)
```python
if signal:
    last_signal_time = getattr(self, '_last_signal_time', None)
    if last_signal_time and (datetime.now() - last_signal_time).seconds < 300:
        return None  # Wait 5 mins between signals
    self._last_signal_time = datetime.now()
    return signal
```

## Paper vs Live Mode

### Paper Mode (Default)
```python
engine = EntryEngineOrchestrator(paper_mode=True)
# Logs signals without executing
```

### Live Mode
```python
engine = EntryEngineOrchestrator(paper_mode=False)
# Executes orders on Dhan (requires integration)
```

## Logging

All classes use `logging` module:
```python
import logging
logging.basicConfig(level=logging.INFO)
# Available levels: DEBUG, INFO, WARNING, ERROR

# Filter specific logger
logging.getLogger("aiohttp").setLevel(logging.WARNING)
```

## Error Handling

### Connection lost
- Auto-reconnects with exponential backoff
- Logs reconnection attempts
- Resumes listening after reconnect

### Authentication failed
- Check .env credentials
- Verify TOTP secret
- Check Angel One account status

### Binary frame errors
- Logged as DEBUG (doesn't stop processing)
- Check frame size >= 123 bytes
- Verify offsets match Angel One v3 format

## Performance Tuning

### Reduce memory (fewer bars)
```python
client.bar_builder = OHLCBarBuilder(window=100)  # Instead of 500
```

### Reduce callbacks overhead
```python
# Store data, process in batches
ticks_buffer = []
def on_tick(tick):
    ticks_buffer.append(tick)
    if len(ticks_buffer) >= 100:
        process_batch(ticks_buffer)
        ticks_buffer.clear()
```

### Async processing
```python
async def process_signal(signal):
    # Don't block the loop
    await asyncio.sleep(0)
    await execute_order(signal)

client.on_bar(lambda bar: process_signal(bar) if signal else None)
```

## Debugging

### Check WebSocket frames
```python
# Add to on_tick callback
if client.tick_count <= 10:
    print(f"Debug tick {client.tick_count}: {tick.to_dict()}")
```

### Monitor connection
```python
def on_connection(state):
    if state:
        print("🟢 WebSocket live")
    else:
        print("🔴 WebSocket lost - will reconnect")

client.on_connection(on_connection)
```

### Check bar aggregation
```python
def on_bar(bar):
    print(f"Bar: {bar['timestamp']} | Vol={bar['volume']} | " 
          f"OHLC={bar['open']:.2f}/{bar['high']:.2f}/"
          f"{bar['low']:.2f}/{bar['close']:.2f}")

client.on_bar(on_bar)
```

## Endpoints

- **WebSocket**: `wss://smartapisocket.angelone.in/smart-stream`
- **REST Auth**: `https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword`
- **Fallback**: `https://smartapi.angelbroking.com/rest/auth/...`

## Token Format

MCX Silver Instruments:
- `SILVER05MAY26FUT` - May 2026 contract
- Exchange: `MCX`
- Subscription: `[{"exchangeTokens": {"MCX": ["SILVER05MAY26FUT"]}}]`

## Support

- Test connection: `python3 test_websocket_realtime.py`
- Check logs: Look for `[ERROR]` and `[WARNING]` lines
- Review .env: Verify all credentials present
- Check market hours: MCX 09:00-17:00 IST, Mon-Fri
