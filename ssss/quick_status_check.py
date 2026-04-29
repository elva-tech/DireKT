#!/usr/bin/env python3
"""Quick System Status Check"""

import os
import sys
import json

print("\n" + "="*70)
print("TRADING SYSTEM STATUS CHECK")
print("="*70)

# Check 1: Files
print("\n📂 FILES:")
files = {
    'WebSocket Client': 'angel_one_websocket_realtime.py',
    'Complete Integration': 'integration_complete.py',
    'Data Preparation': 'prepare_data_march2.py',
    'Validation Script': 'validate_integration.py',
    'ML Training': 'ml_training.py',
}

for name, path in files.items():
    exists = "✓" if os.path.exists(path) else "✗"
    print(f"  {exists} {name:25} {path}")

# Check 2: Data Files
print("\n📊 DATA FILES:")
data_files = {
    'Historical Data (ML Ready)': 'mcx_silver_ml_ready.csv',
    'Random Forest Model': 'best_model_random_forest_2025.pkl',
    'Feature Scaler': 'feature_scaler.pkl',
}

for name, path in data_files.items():
    exists = os.path.exists(path)
    status = f"✓ ({os.path.getsize(path)/1024:.1f}KB)" if exists else "✗ (missing)"
    print(f"  {status:20} {name:30} {path}")

# Check 3: Credentials
print("\n🔐 CREDENTIALS (.env):")
from dotenv import load_dotenv
load_dotenv()

creds = {
    'Angel One': [
        'ANGEL_ONE_CLIENT_ID',
        'ANGEL_ONE_PASSWORD',
        'ANGEL_ONE_TOTP_SECRET',
        'ANGEL_ONE_API_KEY',
    ],
    'Dhan': [
        'DHAN_CLIENT_ID',
        'DHAN_API_KEY',
    ]
}

for provider, keys in creds.items():
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        print(f"  ⚠ {provider}: Missing {len(missing)}/{len(keys)} keys")
    else:
        print(f"  ✓ {provider}: All {len(keys)} keys configured")

# Check 4: Data Date Range
print("\n📅 DATA DATE RANGE:")
try:
    import pandas as pd
    if os.path.exists('mcx_silver_ml_ready.csv'):
        df = pd.read_csv('mcx_silver_ml_ready.csv')
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            min_date = df['trade_date'].min()
            max_date = df['trade_date'].max()
            print(f"  ✓ Data: {min_date.date()} to {max_date.date()}")
            print(f"  ✓ Rows: {len(df):,}")
            
            import pandas as pd
            target_date = pd.to_datetime('2026-03-02')
            if max_date >= target_date:
                print(f"  ✓ Extends to March 2, 2026 ✅")
            else:
                print(f"  ⚠ Ends {(target_date - max_date).days} days before March 2")
except Exception as e:
    print(f"  ✗ Error reading data: {e}")

# Check 5: Dependencies
print("\n📦 DEPENDENCIES:")
deps = ['pandas', 'numpy', 'sklearn', 'aiohttp', 'pyotp', 'dotenv']
missing_deps = []

for dep in deps:
    try:
        __import__(dep.replace('sklearn', 'sklearn').replace('dotenv', 'dotenv'))
        print(f"  ✓ {dep}")
    except ImportError:
        print(f"  ✗ {dep} (missing)")
        missing_deps.append(dep)

# Summary
print("\n" + "="*70)
print("SUMMARY")
print("="*70)

all_good = (
    all(os.path.exists(p) for p in files.values()) and
    all(os.path.exists(p) for p in data_files.values() if p.endswith('.py')) and
    not missing_deps
)

if all_good:
    print("✅ SYSTEM READY - All components verified")
    print("\nNext: Run training system with:")
    print("  python3 prepare_data_march2.py")
    print("  python3 integration_complete.py")
    exit_code = 0
else:
    print("⚠ SYSTEM INCOMPLETE - Fix issues above")
    if missing_deps:
        print(f"\nInstall missing: pip install {' '.join(missing_deps)}")
    exit_code = 1

print("="*70 + "\n")
sys.exit(exit_code)
