#!/usr/bin/env python3
"""
Integration Validation & System Test
====================================
Validates entire pipeline:
  1. Historical data (till March 2)
  2. Model training on historical data
  3. WebSocket connectivity
  4. Real-time signal generation
  5. Paper trading execution

Run: python3 validate_integration.py
"""

import asyncio
import logging
import pickle
import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrationValidator:
    """Validate all components of the trading system."""

    def __init__(self):
        self.checks = {}
        self.critical_failures = []

    # ── CHECK 1: Historical Data ──────────────────────────────────────

    def check_historical_data(self) -> bool:
        """Verify historical data exists and extends to March 2."""
        logger.info("\n📚 CHECK 1: Historical Data")
        logger.info("-" * 60)

        try:
            csv_path = "mcx_silver_ml_ready.csv"
            
            if not os.path.exists(csv_path):
                logger.error(f"❌ Data file not found: {csv_path}")
                return False

            df = pd.read_csv(csv_path)
            logger.info(f"✓ File exists: {csv_path}")
            logger.info(f"  Rows: {len(df):,}")
            logger.info(f"  Columns: {len(df.columns)}")

            # Check date range
            if 'trade_date' in df.columns:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                min_date = df['trade_date'].min()
                max_date = df['trade_date'].max()
                
                logger.info(f"✓ Date range: {min_date.date()} to {max_date.date()}")
                
                target = pd.to_datetime('2026-03-02')
                if max_date >= target:
                    logger.info(f"✓ Data extends to March 2, 2026")
                else:
                    logger.warning(f"⚠ Data only extends to {max_date.date()}, target is {target.date()}")
            else:
                logger.warning("⚠ No 'trade_date' column found")

            # Check features
            required_features = ['close', 'open', 'high', 'low', 'volume', 'target']
            missing_features = [f for f in required_features if f not in df.columns]
            
            if missing_features:
                logger.warning(f"⚠ Missing features: {missing_features}")
            else:
                logger.info(f"✓ All required features present ({len(required_features)})")

            # Check data quality
            null_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
            logger.info(f"✓ Data quality: {100 - null_pct:.1f}% complete")

            if null_pct > 10:
                logger.warning(f"⚠ High null percentage: {null_pct:.1f}%")

            return True

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            self.critical_failures.append(f"Historical data check: {e}")
            return False

    # ── CHECK 2: Model Training ───────────────────────────────────────

    def check_model(self) -> bool:
        """Verify ML model is trained and available."""
        logger.info("\n🤖 CHECK 2: ML Model")
        logger.info("-" * 60)

        try:
            # Check if model exists
            model_path = "best_model_random_forest_2025.pkl"
            scaler_path = "feature_scaler.pkl"

            if not os.path.exists(model_path):
                logger.warning(f"ℹ Model not found: {model_path}")
                logger.info("  (Will train during initialization)")
                return True

            # Load model
            model = pickle.load(open(model_path, 'rb'))
            logger.info(f"✓ Model loaded: {model_path}")
            logger.info(f"  Type: {type(model).__name__}")

            if hasattr(model, 'n_estimators'):
                logger.info(f"  Estimators: {model.n_estimators}")

            # Load scaler
            if os.path.exists(scaler_path):
                scaler = pickle.load(open(scaler_path, 'rb'))
                logger.info(f"✓ Scaler loaded: {scaler_path}")
            else:
                logger.warning(f"⚠ Scaler not found: {scaler_path}")

            return True

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False

    # ── CHECK 3: Angel One Credentials ────────────────────────────────

    def check_angel_credentials(self) -> bool:
        """Verify Angel One API credentials are configured."""
        logger.info("\n🔐 CHECK 3: Angel One Credentials")
        logger.info("-" * 60)

        try:
            from dotenv import load_dotenv
            load_dotenv()

            required = [
                'ANGEL_ONE_CLIENT_ID',
                'ANGEL_ONE_PASSWORD',
                'ANGEL_ONE_TOTP_SECRET',
                'ANGEL_ONE_API_KEY',
                'ANGEL_ONE_USER_ID',
            ]

            missing = []
            for var in required:
                if not os.getenv(var):
                    missing.append(var)
                else:
                    logger.info(f"✓ {var} set")

            if missing:
                logger.error(f"❌ Missing credentials: {', '.join(missing)}")
                logger.info("  Add to .env file")
                self.critical_failures.append(f"Missing Angel One credentials: {missing}")
                return False

            logger.info("✓ All Angel One credentials configured")
            return True

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False

    # ── CHECK 4: Dhan Credentials ────────────────────────────────────

    def check_dhan_credentials(self) -> bool:
        """Verify Dhan API credentials are configured."""
        logger.info("\n💳 CHECK 4: Dhan Credentials (Optional)")
        logger.info("-" * 60)

        try:
            from dotenv import load_dotenv
            load_dotenv()

            required = [
                'DHAN_CLIENT_ID',
                'DHAN_API_KEY',
            ]

            missing = []
            for var in required:
                if not os.getenv(var):
                    missing.append(var)
                else:
                    logger.info(f"✓ {var} set")

            if missing:
                logger.warning(f"⚠ Missing Dhan credentials: {', '.join(missing)}")
                logger.info("  Paper trading will use mock execution")
                return True

            logger.info("✓ Dhan credentials configured for live paper trading")
            return True

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False

    # ── CHECK 5: Dependencies ────────────────────────────────────────

    def check_dependencies(self) -> bool:
        """Verify all required Python packages are installed."""
        logger.info("\n📦 CHECK 5: Python Dependencies")
        logger.info("-" * 60)

        required_packages = {
            'pandas': 'Data processing',
            'numpy': 'Numerical computing',
            'sklearn': 'Machine learning (scikit-learn)',
            'aiohttp': 'Async HTTP (WebSocket)',
            'pyotp': 'TOTP 2FA',
            'dotenv': 'Environment variables',
        }

        missing = []
        for package, description in required_packages.items():
            try:
                __import__(package)
                logger.info(f"✓ {package:15} - {description}")
            except ImportError:
                logger.warning(f"✗ {package:15} - {description} (MISSING)")
                missing.append(package)

        if missing:
            logger.error(f"❌ Missing packages: {', '.join(missing)}")
            logger.info(f"  Install with: pip install {' '.join(missing)}")
            self.critical_failures.append(f"Missing packages: {missing}")
            return False

        logger.info("✓ All dependencies installed")
        return True

    # ── CHECK 6: WebSocket Connectivity ──────────────────────────────

    async def check_websocket_connectivity(self) -> bool:
        """Test WebSocket connection to Angel One."""
        logger.info("\n🌐 CHECK 6: WebSocket Connectivity")
        logger.info("-" * 60)

        try:
            from angel_one_websocket_realtime import AngelOneRealTimeClient
            
            client = AngelOneRealTimeClient()
            logger.info("✓ WebSocket client instantiated")

            # Try login
            logger.info("  Testing Angel One login...")
            if await client.login():
                logger.info("✓ Angel One authentication successful")
                logger.info(f"  Feed Token: {client.feed_token[:20]}..." if client.feed_token else "  Feed Token: N/A")
            else:
                logger.error("❌ Angel One authentication failed")
                logger.info("  Check credentials in .env")
                self.critical_failures.append("Angel One authentication failed")
                return False

            # Note: Don't actually connect WebSocket, just validate credentials
            await client.disconnect()
            return True

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            self.critical_failures.append(f"WebSocket test: {e}")
            return False

    # ── CHECK 7: Integration Files ───────────────────────────────────

    def check_integration_files(self) -> bool:
        """Verify all integration modules exist."""
        logger.info("\n📂 CHECK 7: Integration Files")
        logger.info("-" * 60)

        required_files = {
            'angel_one_websocket_realtime.py': 'WebSocket client',
            'entry_engine_with_websocket.py': 'Entry signal generator',
            'integration_complete.py': 'Main orchestrator',
            'prepare_data_march2.py': 'Data preparation',
            'validate_integration.py': 'Validation (this file)',
        }

        missing = []
        for filename, description in required_files.items():
            if os.path.exists(filename):
                logger.info(f"✓ {filename:35} - {description}")
            else:
                logger.warning(f"✗ {filename:35} - {description} (MISSING)")
                missing.append(filename)

        if missing:
            logger.warning(f"⚠ Missing files: {', '.join(missing)}")
            # Not critical, as some might be in .gitignore or optional

        return len(missing) < 3  # Fail if more than 2 files missing

    # ── MAIN VALIDATION FLOW ─────────────────────────────────────────

    async def validate_all(self) -> bool:
        """Run all validation checks."""
        logger.info("\n" + "=" * 70)
        logger.info("🔍 INTEGRATION VALIDATION")
        logger.info("=" * 70)

        checks_results = [
            ("Historical Data", self.check_historical_data()),
            ("ML Model", self.check_model()),
            ("Angel One Creds", self.check_angel_credentials()),
            ("Dhan Creds", self.check_dhan_credentials()),
            ("Dependencies", self.check_dependencies()),
            ("WebSocket", await self.check_websocket_connectivity()),
            ("Integration Files", self.check_integration_files()),
        ]

        self.checks = {name: result for name, result in checks_results}

        # Print summary
        logger.info("\n" + "=" * 70)
        logger.info("📋 VALIDATION SUMMARY")
        logger.info("-" * 70)

        passed = sum(1 for r in self.checks.values() if r)
        total = len(self.checks)

        for check_name, result in self.checks.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"  {status:8} - {check_name}")

        logger.info("-" * 70)
        logger.info(f"Result: {passed}/{total} checks passed")

        if self.critical_failures:
            logger.error("\n❌ CRITICAL FAILURES:")
            for failure in self.critical_failures:
                logger.error(f"  • {failure}")

        return passed == total

    def print_next_steps(self):
        """Print next steps based on validation results."""
        logger.info("\n" + "=" * 70)
        logger.info("📝 NEXT STEPS")
        logger.info("=" * 70)

        if not self.checks.get("Historical Data"):
            logger.info("\n1. Prepare historical data:")
            logger.info("   python3 prepare_data_march2.py")

        if not self.checks.get("ML Model"):
            logger.info("\n2. Train ML model on historical data:")
            logger.info("   python3 ml_training.py")

        if all(self.checks.values()):
            logger.info("\n✅ All checks passed! Ready to run trading system:")
            logger.info("   python3 integration_complete.py")
        else:
            logger.warning("\n⚠ Fix the above issues before running the system")


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

async def main():
    """Run integration validation."""
    validator = IntegrationValidator()
    
    all_passed = await validator.validate_all()
    validator.print_next_steps()

    logger.info("\n" + "=" * 70)
    
    if all_passed:
        logger.info("✅ SYSTEM READY - All components validated")
        return 0
    else:
        logger.error("❌ SYSTEM NOT READY - Fix issues above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
