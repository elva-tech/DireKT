#!/usr/bin/env python3
"""Lightweight system verification without imports that cause hangs."""
import os
import sys
from pathlib import Path

print("=" * 60)
print("QUICK SYSTEM VERIFICATION")
print("=" * 60)

workspace = Path("/Users/renukaprasads/ssss")

# 1. Check critical files exist
files_check = {
    "integration_complete.py": "Main orchestrator",
    "angel_one_websocket_realtime.py": "WebSocket client",
    "prepare_data_march2.py": "Data preparation",
    "validate_integration.py": "System validator",
    "ml_training.py": "ML training module",
    "mcx_silver_ml_ready.csv": "Historical data",
    "best_model_random_forest_2025.pkl": "ML model",
    ".env": "Configuration",
}

print("\n📁 FILE CHECK:")
all_files_ok = True
for filename, desc in files_check.items():
    filepath = workspace / filename
    exists = filepath.exists()
    status = "✅" if exists else "❌"
    print(f"  {status} {filename:40} ({desc})")
    if not exists:
        all_files_ok = False

# 2. Check .env has credentials
print("\n🔐 CREDENTIALS CHECK:")
env_file = workspace / ".env"
if env_file.exists():
    with open(env_file) as f:
        env_content = f.read()
    checks = {
        "ANGEL_ONE_CLIENT_ID": "Angel One Client ID",
        "ANGEL_ONE_API_KEY": "Angel One API Key",
        "DHAN_CLIENT_ID": "Dhan Client ID",
        "DHAN_ACCESS_TOKEN": "Dhan Access Token",
    }
    for key, desc in checks.items():
        has_key = key in env_content
        status = "✅" if has_key else "❌"
        print(f"  {status} {desc}")
else:
    print("  ❌ .env file not found!")

# 3. Check data file has rows
print("\n📊 DATA CHECK:")
csv_file = workspace / "mcx_silver_ml_ready.csv"
if csv_file.exists():
    with open(csv_file) as f:
        lines = len(f.readlines())
    print(f"  ✅ Historical data: {lines-1} rows (plus header)")
    if lines > 250:
        print(f"     ✅ Sufficient data (>250 rows)")
    else:
        print(f"     ⚠️  Low data volume (<250 rows)")
else:
    print("  ❌ Historical data file not found!")

# 4. Check model file exists and has size
print("\n🤖 ML MODEL CHECK:")
model_file = workspace / "best_model_random_forest_2025.pkl"
if model_file.exists():
    size_mb = model_file.stat().st_size / (1024 * 1024)
    print(f"  ✅ Model file exists: {size_mb:.2f} MB")
    if size_mb > 0.1:
        print(f"     ✅ Model appears valid")
else:
    print("  ❌ Model file not found!")

# 5. Python environment
print("\n🐍 PYTHON ENVIRONMENT:")
print(f"  ✅ Python: {sys.version.split()[0]}")
print(f"  ✅ Executable: {sys.executable}")

# Summary
print("\n" + "=" * 60)
if all_files_ok:
    print("✅ SYSTEM READY - All core files present")
    print("\nTo start the system, run:")
    print("  python3 integration_complete.py")
else:
    print("⚠️  Some files missing - Check above")
print("=" * 60)
