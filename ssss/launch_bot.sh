#!/bin/bash
# MCX Silver Trading Bot - Quick Launcher
# Start the bot with all necessary monitoring

cd /Users/renukaprasads/ssss

echo "══════════════════════════════════════════════════════════════"
echo "   🚀 MCX SILVER FUTURES TRADING BOT - LAUNCHER"
echo "══════════════════════════════════════════════════════════════"
echo ""

# Check Python environment
echo "✓ Checking Python environment..."
python3 --version

# Verify key files exist
echo "✓ Verifying critical files..."
files=("best_model_random_forest_2025.pkl" "mcx_silver_futures_2025.csv" "trading_bot.py" ".env")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file MISSING"
        exit 1
    fi
done

echo ""
echo "✓ Checking configuration..."
if grep -q "PAPER_TRADE_ENABLED=true" .env; then
    echo "  📄 PAPER TRADING MODE (Safe for testing)"
else
    echo "  ⚠️  LIVE TRADING MODE (Real money!)"
fi

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "🟢 ALL SYSTEMS READY - STARTING BOT..."
echo "══════════════════════════════════════════════════════════════"
echo ""

# Start the bot
python3 trading_bot.py

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "Bot stopped. Check trading_bot.log for details."
echo "═══════════════════════════════════════════════════════════════"
