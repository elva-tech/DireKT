# ✅ DEPLOYMENT CHECKLIST - MCX Silver Futures Trading Bot

## 🔴 CRITICAL BEFORE RUNNING BOT

You have provided credentials. Now you need to complete a few final steps:

### Step 1: Generate Angel One Auth Token (REQUIRED)

The credentials you provided don't include the auth token. You need to generate it:

**Option A: Via Web Panel (Recommended - 2 minutes)**
1. Log in to https://www.angelbroking.com
2. Go to Settings → API Management
3. Find "SmartAPI" section
4. Generate or view your token
5. Copy the `jwtToken` value

**Option B: Via Python Helper (May fail due to API restrictions)**
```bash
python3 auth_helper.py
```

### Step 2: Add Auth Token to .env

Open `.env`:
```bash
nano .env
```

Add these lines at the bottom:
```env
ANGEL_ONE_AUTH_TOKEN=<paste_your_jwtToken_here>
ANGEL_ONE_FEED_TOKEN=<paste_your_feedToken_here>
```

Example:
```env
ANGEL_ONE_AUTH_TOKEN=eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9...
ANGEL_ONE_FEED_TOKEN=abc123xyz789...
```

**Save:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step 3: Verify Credentials Are Set

Check that .env has all required fields:
```bash
grep -E "ANGEL_ONE|DHAN" .env
```

Should show:
- ✅ ANGEL_ONE_CLIENT_ID
- ✅ ANGEL_ONE_CLIENT_SECRET
- ✅ ANGEL_ONE_API_KEY
- ✅ ANGEL_ONE_TOTP_SECRET
- ✅ ANGEL_ONE_PASSWORD
- ✅ ANGEL_ONE_USER_ID
- ✅ ANGEL_ONE_AUTH_TOKEN (← NEW!)
- ✅ ANGEL_ONE_FEED_TOKEN (← NEW!)
- ✅ DHAN_CLIENT_ID
- ✅ DHAN_ACCESS_TOKEN

### Step 4: Run in Paper Mode First

Start the bot in PAPER TRADING mode (safe, no real money):

```bash
# Ensure bot is in paper mode
grep "PAPER_TRADE_ENABLED" .env
# Should show: PAPER_TRADE_ENABLED=true

# Start bot
python3 trading_bot.py
```

Expected output:
```
✅ Angel One authentication successful
📄 PAPER TRADING MODE ACTIVE
✅ Trading bot started successfully
```

Monitor for 1-2 hours:
- Check that signals are being generated
- Verify orders are executing in paper mode
- Review P&L in session_trades.json

### Step 5: Switch to Live Mode (OPTIONAL - After 1-2 weeks testing)

Only if you're confident:

1. Edit .env:
```bash
nano .env
# Change: PAPER_TRADE_ENABLED=false
```

2. Start bot:
```bash
python3 trading_bot.py
```

3. Monitor continuously:
```bash
tail -f trading_bot.log
```

---

## 📋 CREDENTIALS SUMMARY

### What You Provided ✅
```
✅ ANGEL_ONE_CLIENT_ID = AACE648379
✅ ANGEL_ONE_CLIENT_SECRET = 1acbae55-8e51-45b6-8388-707e43910c01
✅ ANGEL_ONE_TOTP_SECRET = YPNWTO32HOA7IZ5KFNSMBZUQCE
✅ ANGEL_ONE_PASSWORD = 2607
✅ ANGEL_ONE_USER_ID = AACE648379
✅ ANGEL_ONE_API_KEY = ZztbYWQr
✅ DHAN_CLIENT_ID = 1110620077
✅ DHAN_ACCESS_TOKEN = eyJ0eXAi...
```

### What You Still Need ⏳
```
⏳ ANGEL_ONE_AUTH_TOKEN = [Generate from web panel]
⏳ ANGEL_ONE_FEED_TOKEN = [Generate from web panel]
```

---

## ⚠️ IMPORTANT NOTES

### Token Expiration
- Angel One auth tokens expire after **120 minutes**
- You may need to refresh every 1-2 hours
- Bot will attempt auto-refresh (may fail)
- **Solution:** Periodically update .env with new token

### Security
- ✅ .env is in .gitignore (never commit)
- ⚠️ You've shared credentials in this chat
- 🔒 ROTATE these credentials after setup:
  1. Change Angel One password
  2. Generate new API key
  3. Update client secret

### Testing
- Start with PAPER mode only
- Monitor for 1-2 weeks minimum
- Track P&L and signal quality
- Only go live if confident

---

## 🚀 QUICK START COMMAND

After adding auth tokens to .env:

```bash
# Test connection
python3 -c "
from angel_one_connector import AngelOneConnector
import os
from dotenv import load_dotenv
load_dotenv()

c = AngelOneConnector(
    os.getenv('ANGEL_ONE_CLIENT_ID'),
    os.getenv('ANGEL_ONE_CLIENT_SECRET'),
    os.getenv('ANGEL_ONE_API_KEY'),
    os.getenv('ANGEL_ONE_TOTP_SECRET'),
    os.getenv('ANGEL_ONE_PASSWORD'),
    os.getenv('ANGEL_ONE_USER_ID')
)

if c.authenticate():
    print('✅ Authentication works!')
    q = c.get_quote('SILVER', 'MCX')
    if q:
        print(f'📊 Current price: ₹{q.ltp:,.0f}')
else:
    print('❌ Auth failed')
"

# Start trading bot
python3 trading_bot.py
```

---

## 📞 NEXT STEPS

1. **Get auth token from Angel One web panel** (2 min)
2. **Add to .env file** (1 min)
3. **Run bot in paper mode** (ongoing)
4. **Monitor logs** (daily)
5. **Switch to live after 2 weeks** (optional)

---

## 🆘 HELP & TROUBLESHOOTING

### Bot won't start
```bash
# Check .env is complete
grep -c "=" .env  # Should show 20+ lines

# Check no syntax errors
python3 -m py_compile trading_bot.py

# Check env file is valid
python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('ANGEL_ONE_CLIENT_ID'))"
```

### Authentication fails
See: [ANGEL_ONE_AUTH_GUIDE.md](ANGEL_ONE_AUTH_GUIDE.md)

### No signals generated
- Check network connectivity
- Verify auth token is fresh (< 120 min old)
- Check trading hours (MCX closes at certain times)
- Increase MIN_CONFIDENCE to see fewer but stronger signals

---

**Status:** 🟡 READY FOR FINAL STEP (need auth token)

**Last Updated:** March 5, 2026
