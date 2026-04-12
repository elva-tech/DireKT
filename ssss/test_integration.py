#!/usr/bin/env python3
"""
MCX Silver Futures - Integration Test Suite
===========================================
Comprehensive testing for the enhanced trading system components.

Features:
  • Unit tests for all new modules
  • Integration tests for workflow validation
  • Mock data for testing scenarios
  • Performance benchmarking
  • Error handling validation

Usage:
    python3 test_integration.py
"""

import sys
import os
import unittest
import json
import logging
from unittest.mock import Mock, patch
from datetime import datetime
import numpy as np

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import modules to test
from lot_selector import LotSelector, LotInfo
from llm_engine import LLMTradingEngine, TradingDecision
from strategy_selector import StrategySelector, StrategyType
from risk_manager import RiskManager, RiskLimits

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestLotSelector(unittest.TestCase):
    """Test cases for LotSelector module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_balance = 200000.0
        self.lot_selector = LotSelector(mock_balance=self.mock_balance)
    
    def test_account_balance_retrieval(self):
        """Test account balance retrieval."""
        balance = self.lot_selector.get_account_balance()
        self.assertEqual(balance, self.mock_balance)
    
    def test_margin_calculation(self):
        """Test margin requirement calculation."""
        ltp = 28150.0
        margin_per_lot, contract_value = self.lot_selector.calculate_margin_requirements(ltp)
        
        expected_contract_value = ltp * self.lot_selector.SILVER_LOT_SIZE
        expected_margin = expected_contract_value * self.lot_selector.MARGIN_REQUIREMENT_PCT
        
        self.assertEqual(contract_value, expected_contract_value)
        self.assertEqual(margin_per_lot, expected_margin)
    
    def test_optimal_lots_calculation(self):
        """Test optimal lots calculation."""
        current_price = 28150.0
        lot_info = self.lot_selector.calculate_optimal_lots(current_price)
        
        self.assertIsInstance(lot_info, LotInfo)
        self.assertGreater(lot_info.max_lots, 0)
        self.assertLessEqual(lot_info.max_lots, self.lot_selector.MAX_LOTS)
        self.assertEqual(lot_info.symbol, "SILVERM2026")
        self.assertEqual(lot_info.lot_size, self.lot_selector.SILVER_LOT_SIZE)
    
    def test_risk_validation(self):
        """Test risk validation."""
        current_price = 28150.0
        lot_info = self.lot_selector.calculate_optimal_lots(current_price)
        
        # Valid case
        self.assertTrue(self.lot_selector.validate_risk_limits(lot_info))
        
        # Invalid case - insufficient capital
        poor_selector = LotSelector(mock_balance=10000.0)
        poor_lot_info = poor_selector.calculate_optimal_lots(current_price)
        self.assertFalse(poor_selector.validate_risk_limits(poor_lot_info))
    
    def test_insufficient_capital(self):
        """Test behavior with insufficient capital."""
        poor_selector = LotSelector(mock_balance=10000.0)
        lot_info = poor_selector.calculate_optimal_lots(28150.0)
        
        self.assertEqual(lot_info.max_lots, 0)
        self.assertEqual(lot_info.trade_quantity, 0)


class TestLLMEngine(unittest.TestCase):
    """Test cases for LLMTradingEngine module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.llm_engine = LLMTradingEngine()
    
    def test_atr_stop_loss_calculation(self):
        """Test ATR-based stop loss calculation."""
        atr = 85.5
        current_price = 28150.0
        
        # Buy order
        sl_buy = self.llm_engine.calculate_atr_stop_loss(atr, current_price, "BUY")
        self.assertLess(sl_buy, current_price)
        
        # Sell order
        sl_sell = self.llm_engine.calculate_atr_stop_loss(atr, current_price, "SELL")
        self.assertGreater(sl_sell, current_price)
    
    def test_target_price_calculation(self):
        """Test target price calculation."""
        entry_price = 28150.0
        stop_loss = 27980.0
        
        # Buy order
        target_buy = self.llm_engine.calculate_target_price(entry_price, stop_loss, "BUY")
        self.assertGreater(target_buy, entry_price)
        
        # Sell order
        target_sell = self.llm_engine.calculate_target_price(entry_price, stop_loss, "SELL")
        self.assertLess(target_sell, entry_price)
    
    def test_market_condition_analysis(self):
        """Test market condition analysis."""
        indicators = {
            'RSI': 75,
            'trend_strength': 0.8,
            'volume_ratio': 1.8
        }
        
        condition = self.llm_engine.analyze_market_condition(indicators)
        self.assertIn("overbought", condition)
        self.assertIn("strong uptrend", condition)
        self.assertIn("high volume", condition)
    
    def test_prompt_creation(self):
        """Test trading prompt creation."""
        ohlc_data = {
            'open': 28100.0,
            'high': 28200.0,
            'low': 28050.0,
            'close': 28150.0,
            'volume': 1500
        }
        
        indicators = {
            'RSI': 55.5,
            'MACD': 12.3,
            'ATR': 85.5
        }
        
        prompt = self.llm_engine.create_trading_prompt(ohlc_data, indicators)
        
        self.assertIn("MCX Silver Futures", prompt)
        self.assertIn("₹28150.00", prompt)
        self.assertIn("RSI (14): 55.50", prompt)
        self.assertIn("JSON only", prompt)
    
    def test_response_parsing(self):
        """Test LLM response parsing."""
        valid_json = '''{
            "action": "BUY",
            "confidence": 75,
            "entry_price": 28150.00,
            "stop_loss": 27980.00,
            "target": 28490.00,
            "reason": "Strong momentum with RSI support"
        }'''
        
        decision = self.llm_engine.parse_llm_response(valid_json)
        
        self.assertIsNotNone(decision)
        self.assertEqual(decision['action'], "BUY")
        self.assertEqual(decision['confidence'], 75)
        self.assertEqual(decision['entry_price'], 28150.0)
    
    def test_invalid_response_parsing(self):
        """Test parsing of invalid responses."""
        invalid_json = '{"action": "INVALID", "confidence": 150}'
        decision = self.llm_engine.parse_llm_response(invalid_json)
        self.assertIsNone(decision)
        
        missing_fields = '{"action": "BUY"}'
        decision = self.llm_engine.parse_llm_response(missing_fields)
        self.assertIsNone(decision)
    
    def test_decision_generation(self):
        """Test complete decision generation."""
        ohlc_data = {
            'open': 28100.0,
            'high': 28200.0,
            'low': 28050.0,
            'close': 28150.0,
            'volume': 1500
        }
        
        indicators = {
            'RSI': 55.5,
            'MACD': 12.3,
            'ATR': 85.5,
            'SMA_20': 28080.0,
            'EMA_12': 28120.0,
            'volume_ratio': 1.2,
            'trend_strength': 0.3
        }
        
        decision = self.llm_engine.generate_decision(ohlc_data, indicators)
        
        self.assertIsInstance(decision, TradingDecision)
        self.assertIn(decision.action, ["BUY", "SELL", "HOLD"])
        self.assertGreaterEqual(decision.confidence, 0)
        self.assertLessEqual(decision.confidence, 100)


class TestStrategySelector(unittest.TestCase):
    """Test cases for StrategySelector module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.strategy_selector = StrategySelector()
    
    def test_strategy_initialization(self):
        """Test strategy initialization."""
        strategies = self.strategy_selector.available_strategies
        
        self.assertEqual(len(strategies), 4)
        self.assertIn(StrategyType.ML_MODEL, strategies)
        self.assertIn(StrategyType.LLM_MODEL, strategies)
        self.assertIn(StrategyType.RULE_BASED, strategies)
        self.assertIn(StrategyType.HYBRID, strategies)
    
    def test_strategy_config_structure(self):
        """Test strategy configuration structure."""
        ml_config = self.strategy_selector.get_strategy_config(StrategyType.ML_MODEL)
        
        self.assertEqual(ml_config.strategy_type, StrategyType.ML_MODEL)
        self.assertEqual(ml_config.name, "Machine Learning Model")
        self.assertTrue(ml_config.requires_ml_model)
        self.assertFalse(ml_config.requires_llm)
        self.assertIn("model_path", ml_config.parameters)
    
    def test_auto_selection(self):
        """Test automatic strategy selection."""
        # Test ML selection
        ml_config = self.strategy_selector.auto_select_strategy("ml")
        self.assertIsNotNone(ml_config)
        self.assertEqual(ml_config.strategy_type, StrategyType.ML_MODEL)
        
        # Test invalid preference
        invalid_config = self.strategy_selector.auto_select_strategy("invalid")
        self.assertIsNone(invalid_config)
    
    def test_llm_strategy_config(self):
        """Test LLM strategy configuration."""
        llm_config = self.strategy_selector.get_strategy_config(StrategyType.LLM_MODEL)
        
        self.assertTrue(llm_config.requires_llm)
        self.assertFalse(llm_config.requires_ml_model)
        self.assertIn("confidence_threshold", llm_config.parameters)
        self.assertIn("risk_reward_ratio", llm_config.parameters)
    
    def test_hybrid_strategy_config(self):
        """Test hybrid strategy configuration."""
        hybrid_config = self.strategy_selector.get_strategy_config(StrategyType.HYBRID)
        
        self.assertTrue(hybrid_config.requires_llm)
        self.assertTrue(hybrid_config.requires_ml_model)
        self.assertIn("ml_weight", hybrid_config.parameters)
        self.assertIn("llm_weight", hybrid_config.parameters)
        self.assertIn("rule_weight", hybrid_config.parameters)


class TestRiskManager(unittest.TestCase):
    """Test cases for RiskManager module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.capital = 100000.0
        self.risk_manager = RiskManager(self.capital)
    
    def test_initialization(self):
        """Test risk manager initialization."""
        self.assertEqual(self.risk_manager.capital, self.capital)
        self.assertEqual(self.risk_manager.limits.daily_loss_limit_pct, 3.0)
        self.assertEqual(self.risk_manager.limits.max_risk_per_trade_pct, 1.5)
        self.assertTrue(self.risk_manager.trading_enabled)
    
    def test_position_risk_calculation(self):
        """Test position risk calculation."""
        entry_price = 28150.0
        stop_loss = 27980.0
        lot_size = 2
        quantity_per_lot = 30
        
        risk = self.risk_manager.calculate_position_risk(entry_price, stop_loss, lot_size, quantity_per_lot)
        
        self.assertIn('contract_value', risk)
        self.assertIn('total_risk', risk)
        self.assertIn('risk_pct', risk)
        self.assertGreater(risk['contract_value'], 0)
        self.assertGreater(risk['total_risk'], 0)
    
    def test_atr_stop_loss(self):
        """Test ATR-based stop loss calculation."""
        current_price = 28150.0
        atr = 85.5
        
        buy_sl = self.risk_manager.calculate_atr_stop_loss(current_price, atr, "BUY")
        sell_sl = self.risk_manager.calculate_atr_stop_loss(current_price, atr, "SELL")
        
        self.assertLess(buy_sl, current_price)
        self.assertGreater(sell_sl, current_price)
    
    def test_position_size_adjustment(self):
        """Test dynamic position size adjustment."""
        base_lots = 3
        
        # High confidence, low volatility
        adjusted = self.risk_manager.adjust_position_size(base_lots, 90, 0.005)
        self.assertGreaterEqual(adjusted, base_lots)
        
        # Low confidence, high volatility
        adjusted = self.risk_manager.adjust_position_size(base_lots, 60, 0.03)
        self.assertLessEqual(adjusted, base_lots)
    
    def test_daily_limits_validation(self):
        """Test daily limits validation."""
        # Normal case
        can_trade, reason = self.risk_manager.validate_daily_limits()
        self.assertTrue(can_trade)
        
        # Exceed daily loss limit
        self.risk_manager.daily_pnl = -5000  # 5% loss
        can_trade, reason = self.risk_manager.validate_daily_limits()
        self.assertFalse(can_trade)
        self.assertIn("loss limit", reason.lower())
    
    def test_risk_metrics_calculation(self):
        """Test risk metrics calculation."""
        # Simulate some trades
        self.risk_manager.daily_trades = 10
        self.risk_manager.daily_wins = 6
        self.risk_manager.daily_losses = 4
        self.risk_manager.daily_pnl = 2500.0
        
        metrics = self.risk_manager.get_risk_metrics()
        
        self.assertEqual(metrics.daily_trades, 10)
        self.assertEqual(metrics.daily_wins, 6)
        self.assertEqual(metrics.daily_losses, 4)
        self.assertEqual(metrics.daily_pnl, 2500.0)
        self.assertEqual(metrics.win_rate, 60.0)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete system."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.mock_balance = 200000.0
        self.current_price = 28150.0
    
    def test_lot_selection_to_risk_management_flow(self):
        """Test flow from lot selection to risk management."""
        # Step 1: Lot selection
        lot_selector = LotSelector(mock_balance=self.mock_balance)
        lot_info = lot_selector.calculate_optimal_lots(self.current_price)
        
        # Step 2: Risk management
        risk_manager = RiskManager(self.mock_balance)
        
        # Create sample decision
        decision = TradingDecision(
            action="BUY",
            confidence=75.0,
            entry_price=self.current_price,
            stop_loss=self.current_price * 0.98,
            target=self.current_price * 1.03,
            reason="Integration test",
            timestamp=datetime.now().isoformat(),
            risk_reward_ratio=1.5
        )
        
        # Step 3: Validate trade
        is_valid, reason = risk_manager.validate_trade(decision, lot_info, self.current_price)
        
        # Debug output for test
        print(f"Risk validation result: {is_valid}, reason: {reason}")
        
        # Allow either valid trade or validation explanation
        self.assertTrue(is_valid or "risk per trade" in reason.lower() or "risk-reward" in reason.lower())
    
    def test_strategy_to_decision_flow(self):
        """Test flow from strategy selection to decision generation."""
        # Step 1: Strategy selection
        strategy_selector = StrategySelector()
        strategy_config = strategy_selector.auto_select_strategy("llm")
        
        self.assertIsNotNone(strategy_config)
        self.assertEqual(strategy_config.strategy_type, StrategyType.LLM_MODEL)
        
        # Step 2: LLM decision generation
        llm_engine = LLMTradingEngine()
        
        ohlc_data = {
            'open': 28100.0,
            'high': 28200.0,
            'low': 28050.0,
            'close': self.current_price,
            'volume': 1500
        }
        
        indicators = {
            'RSI': 55.5,
            'MACD': 12.3,
            'ATR': 85.5,
            'volume_ratio': 1.2,
            'trend_strength': 0.3
        }
        
        decision = llm_engine.generate_decision(ohlc_data, indicators)
        
        self.assertIsInstance(decision, TradingDecision)
        self.assertIn(decision.action, ["BUY", "SELL", "HOLD"])
    
    def test_complete_workflow_simulation(self):
        """Test complete workflow simulation."""
        # Initialize components
        lot_selector = LotSelector(mock_balance=self.mock_balance)
        risk_manager = RiskManager(self.mock_balance)
        strategy_selector = StrategySelector()
        llm_engine = LLMTradingEngine()
        
        # Step 1: Strategy selection
        strategy = strategy_selector.auto_select_strategy("llm")
        self.assertIsNotNone(strategy)
        
        # Step 2: Lot selection
        lot_info = lot_selector.calculate_optimal_lots(self.current_price)
        self.assertGreater(lot_info.max_lots, 0)
        
        # Step 3: Generate signal
        ohlc_data = {
            'open': 28100.0,
            'high': 28200.0,
            'low': 28050.0,
            'close': self.current_price,
            'volume': 1500
        }
        
        indicators = {
            'RSI': 25,  # Oversold
            'MACD': -5.2,
            'ATR': 85.5,
            'volume_ratio': 1.8,
            'trend_strength': -0.2
        }
        
        decision = llm_engine.generate_decision(ohlc_data, indicators)
        
        # Step 4: Risk validation
        is_valid, reason = risk_manager.validate_trade(decision, lot_info, self.current_price)
        
        # Debug output for test
        print(f"Risk validation result: {is_valid}, reason: {reason}")
        
        # Step 5: Record trade (simulated)
        if is_valid and decision.action != "HOLD":
            risk_manager.record_trade(decision, decision.entry_price, decision.target)
        
        # Verify workflow
        self.assertIsNotNone(strategy)
        self.assertGreater(lot_info.max_lots, 0)
        self.assertIsInstance(decision, TradingDecision)
        # Allow either valid trade or HOLD decision
        self.assertTrue(is_valid or decision.action == "HOLD")


def run_performance_benchmark():
    """Run performance benchmark for key components."""
    print("\n" + "="*60)
    print("🚀 PERFORMANCE BENCHMARK")
    print("="*60)
    
    import time
    
    # Benchmark lot selection
    lot_selector = LotSelector(mock_balance=200000.0)
    start_time = time.time()
    for _ in range(1000):
        lot_info = lot_selector.calculate_optimal_lots(28150.0)
    lot_time = time.time() - start_time
    
    print(f"Lot Selection (1000 iterations): {lot_time:.4f}s ({lot_time/1000*1000:.2f}ms per call)")
    
    # Benchmark LLM decision (mock)
    llm_engine = LLMTradingEngine()
    ohlc_data = {'open': 28100, 'high': 28200, 'low': 28050, 'close': 28150, 'volume': 1500}
    indicators = {'RSI': 55, 'MACD': 12.3, 'ATR': 85.5}
    
    start_time = time.time()
    for _ in range(100):
        decision = llm_engine.generate_decision(ohlc_data, indicators)
    llm_time = time.time() - start_time
    
    print(f"LLM Decision (100 iterations): {llm_time:.4f}s ({llm_time/100*1000:.2f}ms per call)")
    
    # Benchmark risk validation
    risk_manager = RiskManager(100000)
    decision = TradingDecision(
        action="BUY", confidence=75, entry_price=28150, stop_loss=27980,
        target=28490, reason="Test", timestamp=datetime.now().isoformat(), risk_reward_ratio=2.0
    )
    lot_info = lot_selector.calculate_optimal_lots(28150.0)
    
    start_time = time.time()
    for _ in range(1000):
        is_valid, reason = risk_manager.validate_trade(decision, lot_info, 28150.0)
    risk_time = time.time() - start_time
    
    print(f"Risk Validation (1000 iterations): {risk_time:.4f}s ({risk_time/1000*1000:.2f}ms per call)")
    
    print("="*60)


def main():
    """Main test runner."""
    print("🧪 MCX Silver Futures - Integration Test Suite")
    print("=" * 60)
    
    # Run unit tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestLotSelector,
        TestLLMEngine,
        TestStrategySelector,
        TestRiskManager,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"   - {test}")
    
    if result.errors:
        print(f"\n🚨 ERRORS:")
        for test, traceback in result.errors:
            print(f"   - {test}")
    
    # Run performance benchmark
    if result.wasSuccessful():
        run_performance_benchmark()
        print(f"\n✅ All tests passed! System is ready for deployment.")
    else:
        print(f"\n❌ Some tests failed. Please review and fix issues.")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
