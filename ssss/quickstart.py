#!/usr/bin/env python3
"""
Quick Start Setup Guide for MCX Silver Futures Trading Bot
"""

import os
import sys
from pathlib import Path

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_step(num, text):
    print(f"\n✓ STEP {num}: {text}")
    print("-" * 70)

def check_file(filepath, description):
    if Path(filepath).exists():
        print(f"  ✅ {description}: {filepath}")
        return True
    else:
        print(f"  ❌ {description}: NOT FOUND - {filepath}")
        return False

def main():
    print_header("🚀 MCX SILVER FUTURES BOT - QUICK START")
    
    # Step 1: Check files
    print_step(1, "Verify all required files exist")
    
    required_files = {
        'best_model_random_forest.pkl': 'Trained ML Model',
        'mcx_silver_ml_ready.csv': 'ML Training Data',
        'angel_one_connector.py': 'Angel One API Connector',
        'dhan_trader.py': 'Dhan Trading Client',
        'trading_bot.py': 'Main Trading Bot',
        'feature_engineering.py': 'Feature Engineering Pipeline',
        'prediction_service.py': 'Signal Generator',
        '.env.example': 'Credentials Template',
    }
    
    all_present = True
    for filename, description in required_files.items():
        if not check_file(filename, description):
            all_present = False
    
    if not all_present:
        print("\n❌ Some required files are missing!")
        print("Please ensure all files are in the current directory.")
        sys.exit(1)
    
    # Step 2: Check .env setup
    print_step(2, "Setup API credentials")
    
    env_exists = Path('.env').exists()
    if env_exists:
        print("  ✅ .env file exists")
        # Check if filled
        with open('.env', 'r') as f:
            content = f.read()
            if 'your_' in content or 'ADD_HERE' in content:
                print("  ⚠️  .env file contains placeholder values")
                print("  → Please fill in your actual API credentials")
            else:
                print("  ✅ .env appears to be configured")
    else:
        print("  ℹ️  .env file not found")
        print("\n  Creating .env from template...")
        if Path('.env.example').exists():
            with open('.env.example', 'r') as template:
                with open('.env', 'w') as env_file:
                    env_file.write(template.read())
            print("  ✅ .env created from .env.example")
            print("  → NOW EDIT .env WITH YOUR CREDENTIALS!")
        else:
            print("  ❌ .env.example not found")
            sys.exit(1)
    
    # Step 3: Check dependencies
    print_step(3, "Verify Python dependencies")
    
    required_packages = [
        'requests', 'pandas', 'numpy', 'sklearn', 'dotenv'
    ]
    
    all_installed = True
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - NOT INSTALLED")
            all_installed = False
    
    if not all_installed:
        print("\n  Run: pip install -r requirements.txt")
        response = input("\n  Install now? (y/n): ").lower()
        if response == 'y':
            os.system('pip install -r requirements.txt')
            print("  ✅ Dependencies installed")
        else:
            print("  ⚠️  Some dependencies missing. Bot may not run.")
    
    # Step 4: Test connections
    print_step(4, "Test API connections (optional)")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        angel_key = os.getenv('ANGEL_ONE_API_KEY')
        dhan_key = os.getenv('DHAN_API_KEY')
        
        if angel_key and 'your_' not in angel_key:
            response = input("  Test Angel One connection? (y/n): ").lower()
            if response == 'y':
                print("  Testing Angel One...")
                # Add connection test code here
                print("  ℹ️  Skipping for now (requires auth)")
        
        if dhan_key and 'your_' not in dhan_key:
            response = input("  Test Dhan connection? (y/n): ").lower()
            if response == 'y':
                print("  Testing Dhan...")
                # Add connection test code here
                print("  ℹ️  Skipping for now (requires auth)")
    
    except:
        pass
    
    # Step 5: Review configuration
    print_step(5, "Review trading configuration")
    
    print("\n  ⚙️  Current Settings from .env:")
    print("  " + "-" * 66)
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        config = {
            'TRADING_SYMBOL': os.getenv('TRADING_SYMBOL', 'SILVER'),
            'MIN_CONFIDENCE': os.getenv('MIN_CONFIDENCE', '0.65'),
            'MAX_POSITION_SIZE': os.getenv('MAX_POSITION_SIZE', '5'),
            'STOP_LOSS_PCT': os.getenv('STOP_LOSS_PCT', '1.5'),
            'PROFIT_TARGET_PCT': os.getenv('PROFIT_TARGET_PCT', '2.0'),
            'PAPER_TRADE_ENABLED': os.getenv('PAPER_TRADE_ENABLED', 'true'),
        }
        
        for key, value in config.items():
            status = "📄 PAPER" if key == 'PAPER_TRADE_ENABLED' and value.lower() == 'true' else ""
            status = "💰 LIVE" if key == 'PAPER_TRADE_ENABLED' and value.lower() == 'false' else status
            print(f"  • {key}: {value} {status}")
    
    except:
        print("  ⚠️  Could not load configuration")
    
    # Step 6: Next steps
    print_step(6, "Ready to run!")
    
    print("\n📌 NEXT STEPS:")
    print("\n  ✓ Step 1: Fill in your .env file with API credentials")
    print("     nano .env")
    print("\n  ✓ Step 2: Test the bot in PAPER TRADING mode")
    print("     python3 trading_bot.py")
    print("\n  ✓ Step 3: Monitor the logs")
    print("     tail -f trading_bot.log")
    print("\n  ✓ Step 4: After 1-2 weeks, switch to LIVE mode (if confident)")
    print("     Edit .env: PAPER_TRADE_ENABLED=false")
    print("\n  ✓ Step 5: Monitor trading performance")
    print("     python3 -c \"import json; print(json.load(open('session_trades.json')))\"")
    
    print("\n" + "="*70)
    print("⚠️  IMPORTANT REMINDERS:")
    print("="*70)
    print("\n  1. NEVER share your .env file or API keys")
    print("  2. Test in PAPER mode for at least 1-2 weeks")
    print("  3. Monitor bot logs daily")
    print("  4. Be ready to stop bot manually if needed (Ctrl+C)")
    print("  5. Past performance ≠ future results")
    print("  6. Trading carries financial risk - start with small positions")
    
    print("\n" + "="*70)
    print("📖 For full documentation, see SETUP_GUIDE.md")
    print("="*70 + "\n")
    
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
