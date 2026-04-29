# 🚀 MCX Silver Futures - Real-Time Automated Trading Bot

Complete end-to-end system for live algorithmic trading on MCX using Angel One data + Dhan execution.

## 📋 Table of Contents
1. [Setup](#setup)
2. [Configuration](#configuration)
3. [Running the Bot](#running-the-bot)
4. [Monitoring & Logs](#monitoring--logs)
5. [Architecture](#architecture)
6. [API Credentials Guide](#api-credentials-guide)
7. [Safety Features](#safety-features)

---

## 🔧 Setup

### Prerequisites
- Python 3.8+
- Active Angel One trading account
- Active Dhan trading account
- ₹50,000+ for trading

### Installation

```bash
# 1. Navigate to project directory
cd /Users/renukaprasads/ssss

# 2. Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# Or install manually:
pip install python-dotenv requests pandas numpy scikit-learn
```

### Project Structure

```
/ssss/
├── .env                              # ⚠️ Your API credentials (NEVER commit)
├── .env.example                      # Template for .env
├── .gitignore                        # Protects .env from git
│
├── 📊 MODEL & FEATURES
├── best_model_random_forest.pkl      # Trained ML model
├── mcx_silver_futures.csv            # Raw historical data
├── mcx_silver_features.csv           # All 65 engineered features
├── mcx_silver_ml_ready.csv           # ML training dataset
│
├── 🤖 CONNECTORS & EXECUTION
├── angel_one_connector.py            # Angel One API client
├── dhan_trader.py                    # Dhan trading client
├── trading_bot.py                    # Main orchestrator
├── prediction_service.py             # Signal generator
│
├── 🔧 TOOLS & UTILITIES
├── feature_engineering.py            # Feature generation pipeline
├── ml_training.py                    # Model training pipeline
│
└── 📁 OUTPUT FILES (Generated at runtime)
    ├── trading_bot.log               # Detailed logs
    ├── session_signals.json          # Generated signals
    ├── session_trades.json           # Executed trades
    ├── session_price_history.json    # Price data
    └── session_order_history.json    # Order details
```

---

## ⚙️ Configuration

### Step 1: Create `.env` File

Copy the template and fill in your credentials:

```bash
cp .env.example .env
```

### Step 2: Add Your API Credentials

Edit `.env` with your credentials:

```env
# ANGEL ONE - Get from https://www.angelbroking.com
ANGEL_ONE_API_KEY=your_api_key_here
ANGEL_ONE_AUTH_TOKEN=your_auth_token_here
ANGEL_ONE_CLIENT_CODE=your_client_code_here

# DHAN - Get from https://www.dhan.co
DHAN_API_KEY=your_api_key_here
DHAN_CLIENT_ID=your_client_id_here

# TRADING PARAMETERS
TRADING_SYMBOL=SILVER           # MCX Symbol
TRADING_EXCHANGE=MCX            # Exchange
PAPER_TRADE_ENABLED=true        # ⚠️ Set to false ONLY for live trading
MIN_CONFIDENCE=0.65             # Signal confidence threshold (0-1)
MAX_POSITION_SIZE=5             # Max contracts per trade
STOP_LOSS_PCT=1.5               # Stop loss percentage
PROFIT_TARGET_PCT=2.0           # Profit target percentage
FETCH_INTERVAL_SECONDS=5        # Data fetch frequency

# LOGGING
LOG_LEVEL=INFO
```

**⚠️ SECURITY WARNING:**
- **NEVER** share `.env` file or credentials
- **NEVER** commit `.env` to git (use `.gitignore`)
- Store credentials in environment variables on production servers
- Rotate API keys regularly

---

## 🎬 Running the Bot

### Option 1: Paper Trading (Recommended for Testing)

```bash
# Ensure PAPER_TRADE_ENABLED=true in .env

python3 trading_bot.py
```

Example output:
```
2026-03-05 06:45:00 [INFO] =======================================================
2026-03-05 06:45:00 [INFO] 🚀 MCX SILVER FUTURES - AUTOMATED TRADING BOT
2026-03-05 06:45:00 [INFO] =======================================================
2026-03-05 06:45:00 [INFO] ✅ ML model loaded: best_model_random_forest.pkl
2026-03-05 06:45:00 [INFO] ✅ Angel One authentication successful
2026-03-05 06:45:00 [INFO] 📄 PAPER TRADING MODE ACTIVE
2026-03-05 06:45:00 [INFO] ✅ Trading bot started successfully
2026-03-05 06:45:05 [INFO] 📈 Fetching real-time SILVER futures data...
2026-03-05 06:45:05 [INFO] 🔔 SIGNAL GENERATED
2026-03-05 06:45:05 [INFO]    Price: ₹115,573.00
2026-03-05 06:45:05 [INFO]    Volume: 152,890
2026-03-05 06:45:05 [INFO]    OI: 98,765
2026-03-05 06:45:05 [INFO]    Action: BUY
2026-03-05 06:45:05 [INFO]    Confidence: 82.5%
2026-03-05 06:45:05 [INFO] 🔵 EXECUTING BUY ORDER
2026-03-05 06:45:05 [INFO]    Quantity: 5 contracts
2026-03-05 06:45:05 [INFO]    Entry: ₹115,573.00
2026-03-05 06:45:05 [INFO]    SL: ₹113,789.00 (−1.5%)
2026-03-05 06:45:05 [INFO]    Target: ₹117,888.00 (+2.0%)
2026-03-05 06:45:05 [INFO] ✅ BUY order executed: PAPER_20260305064505
```

### Option 2: Live Trading (⚠️ Use with Caution!)

```bash
# 1. First, test thoroughly in PAPER mode for 1-2 weeks
# 2. Only then set PAPER_TRADE_ENABLED=false
# 3. Verify all settings in .env

# Start bot
python3 trading_bot.py
```

### Option 3: Run with Monitoring

```bash
# Run in background and monitor logs
nohup python3 trading_bot.py > trading_bot.log 2>&1 &

# Monitor logs in real-time
tail -f trading_bot.log
```

---

## 📊 Monitoring & Logs

### Real-time Monitoring

```bash
# Watch logs as they're written
tail -f trading_bot.log

# Filter for specific events
grep "SIGNAL\|BUY\|SELL\|ERROR" trading_bot.log

# Count occurrences
grep -c "BUY" trading_bot.log
```

### Session Reports

After bot stops, check generated files:

```bash
# Trading signals generated
cat session_signals.json | python3 -m json.tool | head -50

# Executed trades
cat session_trades.json | python3 -m json.tool

# Order history
cat session_order_history.json | python3 -m json.tool

# Price history
cat session_price_history.json | python3 -m json.tool
```

### Metrics

```python
# Check session summary in Python
import json

with open('session_trades.json') as f:
    trades = json.load(f)

total_trades = len(trades)
winning = sum(1 for t in trades if t.get('pnl', 0) > 0)
total_pnl = sum(t.get('pnl', 0) for t in trades)
win_rate = winning / total_trades * 100 if total_trades > 0 else 0

print(f"Total Trades: {total_trades}")
print(f"Winning Trades: {winning}")
print(f"Win Rate: {win_rate:.1f}%")
print(f"Total P&L: ₹{total_pnl:,.2f}")
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRADING BOT SYSTEM                           │
└─────────────────────────────────────────────────────────────────┘

     ┌──────────────────────────────────────────────────┐
     │          REAL-TIME DATA LAYER                    │
     │  (angel_one_connector.py)                        │
     │                                                  │
     │  • Fetch live OHLCV data                        │
     │  • Maintain quote history                       │
     │  • Calculate price changes                      │
     └────────────────────┬─────────────────────────────┘
                          │
                          ↓ Real-time quote
     ┌──────────────────────────────────────────────────┐
     │       ML SIGNAL GENERATION LAYER                 │
     │  (prediction_service.py)                         │
     │                                                  │
     │  • Load trained model                           │
     │  • Compute technical indicators                 │
     │  • Generate entry signals                       │
     │  • Filter by confidence                         │
     └────────────────────┬─────────────────────────────┘
                          │
                          ↓ BUY/SELL signal
     ┌──────────────────────────────────────────────────┐
     │      EXECUTION LAYER                            │
     │  (dhan_trader.py)                               │
     │                                                  │
     │  • Place limit/market orders                    │
     │  • Set stop-loss & targets                      │
     │  • Manage positions                             │
     │  • Close trades                                 │
     └────────────────────┬─────────────────────────────┘
                          │
                          ↓ Order confirmed
     ┌──────────────────────────────────────────────────┐
     │                DHAN PLATFORM                     │
     │  (Paper Trade or Live Execution)                │
     └──────────────────────────────────────────────────┘
```

---

## 🔐 API Credentials Guide

### Angel One Credentials

1. **Get API Key & Auth Token:**
   - Log in to https://www.angelbroking.com
   - Go to **Settings → API Management**
   - Generate new API key
   - Note: Tokens expire after 20 minutes

2. **Sample Auth Flow:**
   ```
   API Key: your_unique_api_key_12345
   Auth Token: eyJhbGc...complex_jwt_token...
   Client Code: ABC1234567
   ```

3. **Common Issues:**
   - Token expired: Bot auto-refreshes. Check logs if fails.
   - IP Whitelisting: Some brokers require IP whitelist
   - Rate Limiting: Angel One has API rate limits (typically 60/min)

### Dhan Platform Credentials

1. **Get API Key & Client ID:**
   - Log in to https://www.dhan.co
   - Go to **API Console**
   - Generate API credentials
   - Save Client ID

2. **Sample Credentials:**
   ```
   API Key: dhan_api_key_xyz789
   Client ID: DHAN123456
   ```

3. **Paper Trading:**
   - Dhan provides virtual balance for testing
   - Same API credentials work for paper & live
   - Just toggle `PAPER_TRADE_ENABLED` in `.env`

---

## 🛡️ Safety Features

### Risk Management

- ✅ **Position Sizing**: Max 5 contracts per trade (configurable)
- ✅ **Stop Loss**: Automatic SL at -1.5% (configurable)
- ✅ **Profit Target**: TP at +2.0% (configurable)
- ✅ **Signal Filtering**: Min confidence 65% (configurable)
- ✅ **Paper Trading Mode**: Test without real money

### Emergency Stops

```python
# Stop bot gracefully
# Press Ctrl+C in terminal

# The bot will:
# 1. Stop accepting new signals
# 2. Export all session data
# 3. Log final summary
# 4. Exit cleanly
```

### Monitoring Alerts

Add this to `trading_bot.py` for email/SMS alerts:

```python
import smtplib
from email.mime.text import MIMEText

def send_alert(subject, message):
    """Send alert email on trade execution"""
    # Configure your email
    sender = "your_email@gmail.com"
    password = "your_app_password"
    receiver = "your_mobile@alerts.example.com"
    
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
```

---

## 🐛 Troubleshooting

### Bot Won't Start

```bash
# Check credentials
grep -E "ANGEL|DHAN" .env | head -5

# Check Python environment
python3 -c "import dotenv, requests, pandas; print('✅ Dependencies OK')"

# Check model file exists
ls -lh best_model_random_forest.pkl
```

### No Signals Generated

```bash
# Check API connectivity
python3 -c "
from angel_one_connector import AngelOneConnector
from dotenv import load_dotenv
import os

load_dotenv()
conn = AngelOneConnector(
    os.getenv('ANGEL_ONE_API_KEY'),
    os.getenv('ANGEL_ONE_AUTH_TOKEN'),
    os.getenv('ANGEL_ONE_CLIENT_CODE')
)
print('Connected!' if conn.authenticate() else 'Failed')
"

# Check data fetch
tail -50 trading_bot.log | grep "ERROR\|WARNING"
```

### Trades Not Executing

```bash
# Verify Dhan credentials
python3 -c "
from dhan_trader import DhanTradingClient
from dotenv import load_dotenv
import os

load_dotenv()
client = DhanTradingClient(
    os.getenv('DHAN_API_KEY'),
    os.getenv('DHAN_CLIENT_ID'),
    paper_trade=True
)
print('Dhan client initialized')
"

# Check paper trade mode
grep "PAPER_TRADE" .env
```

---

## 📊 Performance Tracking

Create a simple dashboard script:

```python
# save as dashboard.py
import json
from datetime import datetime
import pandas as pd

def load_trades():
    with open('session_trades.json') as f:
        return json.load(f)

def load_signals():
    with open('session_signals.json') as f:
        return json.load(f)

trades = load_trades()
signals = load_signals()

# Calculate metrics
df = pd.DataFrame(trades)
print("\n📊 TRADING SUMMARY")
print("="*50)
print(f"Total Trades: {len(df)}")
print(f"Winning: {(df['pnl'] > 0).sum()}")
print(f"Losing: {(df['pnl'] < 0).sum()}")
print(f"Total P&L: ₹{df['pnl'].sum():,.2f}")
print(f"Avg P&L: ₹{df['pnl'].mean():,.2f}")
print(f"Win Rate: {(df['pnl'] > 0).sum() / len(df) * 100:.1f}%")
```

---

## ✅ Deployment Checklist

- [ ] Copy `.env.example` to `.env`
- [ ] Fill in Angel One credentials
- [ ] Fill in Dhan credentials
- [ ] Set `PAPER_TRADE_ENABLED=true`
- [ ] Test signal generation: `python3 prediction_service.py`
- [ ] Test Angel One: Check fetch_latest in connector
- [ ] Test Dhan: Verify paper trade execution
- [ ] Run bot for 1-2 hours in paper mode
- [ ] Review session logs & trades
- [ ] Only then consider live trading
- [ ] Set up monitoring/alerts
- [ ] Document any custom changes

---

## 📞 Support

**Common Issues:**
- API Rate Limits: Increase fetch interval in .env
- Token Expiry: Bot auto-refreshes, check logs
- Connection Errors: Verify network & VPN
- Port Conflicts: Change WebSocket port if needed

**Documentation:**
- Angel One: https://www.angelbroking.com/api
- Dhan: https://dhan.co/api-docs
- Scikit-learn: https://scikit-learn.org

---

**⚠️ DISCLAIMER:** This bot is for educational purposes. Trading carries risk. Test thoroughly in paper mode before live trading. Past performance ≠ future results.
