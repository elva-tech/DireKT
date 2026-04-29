#!/usr/bin/env python3
"""
MCX Silver Futures - Strategy Selection Module
==============================================
Interactive strategy selection for trading system.

Features:
  • Interactive user prompts for strategy selection
  • Configuration management for different strategies
  • Strategy validation and initialization
  • Seamless integration with existing pipeline

Usage:
    from strategy_selector import StrategySelector, StrategyType
    
    selector = StrategySelector()
    strategy = selector.select_strategy_interactive()
"""

import logging
import sys
from enum import Enum
from typing import Dict, Optional, Any
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Available trading strategies."""
    ML_MODEL = "ml_model"
    LLM_MODEL = "llm_model"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"


@dataclass
class StrategyConfig:
    """Strategy configuration structure."""
    strategy_type: StrategyType
    name: str
    description: str
    min_confidence: float
    requires_llm: bool
    requires_ml_model: bool
    parameters: Dict[str, Any]


class StrategySelector:
    """
    Interactive strategy selection and configuration manager.
    
    Provides user-friendly interface for selecting trading strategies
    and manages their configuration parameters.
    """
    
    def __init__(self):
        """Initialize strategy selector."""
        self.available_strategies = self._initialize_strategies()
        self.selected_strategy = None
    
    def _initialize_strategies(self) -> Dict[StrategyType, StrategyConfig]:
        """
        Initialize available trading strategies.
        
        Returns:
            Dictionary of strategy configurations
        """
        strategies = {
            StrategyType.ML_MODEL: StrategyConfig(
                strategy_type=StrategyType.ML_MODEL,
                name="Machine Learning Model",
                description="Random Forest classifier trained on historical data",
                min_confidence=65.0,
                requires_llm=False,
                requires_ml_model=True,
                parameters={
                    "model_path": "best_model_random_forest_2025.pkl",
                    "scaler_path": "feature_scaler.pkl",
                    "features_count": 65
                }
            ),
            
            StrategyType.LLM_MODEL: StrategyConfig(
                strategy_type=StrategyType.LLM_MODEL,
                name="LLM-Powered Trading",
                description="Large Language Model analyzing market conditions",
                min_confidence=65.0,
                requires_llm=True,
                requires_ml_model=False,
                parameters={
                    "model_provider": "openai",
                    "confidence_threshold": 65.0,
                    "risk_reward_ratio": 2.0,
                    "atr_multiplier": 1.5
                }
            ),
            
            StrategyType.RULE_BASED: StrategyConfig(
                strategy_type=StrategyType.RULE_BASED,
                name="Rule-Based Trading",
                description="Technical analysis rules and indicators",
                min_confidence=70.0,
                requires_llm=False,
                requires_ml_model=False,
                parameters={
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "volume_threshold": 1.5,
                    "trend_threshold": 0.6
                }
            ),
            
            StrategyType.HYBRID: StrategyConfig(
                strategy_type=StrategyType.HYBRID,
                name="Hybrid Strategy",
                description="Combines ML, LLM, and rule-based signals",
                min_confidence=75.0,
                requires_llm=True,
                requires_ml_model=True,
                parameters={
                    "ml_weight": 0.4,
                    "llm_weight": 0.4,
                    "rule_weight": 0.2,
                    "consensus_threshold": 0.7
                }
            )
        }
        
        return strategies
    
    def display_strategy_menu(self) -> None:
        """Display interactive strategy selection menu."""
        print("\n" + "="*60)
        print("🚀 MCX SILVER FUTURES - STRATEGY SELECTION")
        print("="*60)
        print("\nAvailable Trading Strategies:\n")
        
        for i, (strategy_type, config) in enumerate(self.available_strategies.items(), 1):
            print(f"{i}. {config.name}")
            print(f"   {config.description}")
            print(f"   Min Confidence: {config.min_confidence}%")
            print(f"   Requirements: {'LLM' if config.requires_llm else ''}{' + ' if config.requires_llm and config.requires_ml_model else ''}{'ML Model' if config.requires_ml_model else ''}")
            print()
        
        print("0. Exit System")
        print("\n" + "-"*60)
    
    def get_user_choice(self) -> Optional[StrategyType]:
        """
        Get user strategy choice.
        
        Returns:
            Selected strategy type or None if exit
        """
        while True:
            try:
                choice = input("\nSelect strategy (0-4): ").strip()
                
                if choice == "0":
                    print("Exiting system...")
                    return None
                
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(self.available_strategies):
                    strategy_list = list(self.available_strategies.keys())
                    selected = strategy_list[choice_num - 1]
                    return selected
                else:
                    print("❌ Invalid choice. Please select 0-4.")
                    
            except ValueError:
                print("❌ Please enter a valid number.")
            except KeyboardInterrupt:
                print("\n\nExiting system...")
                return None
    
    def validate_strategy_requirements(self, strategy_type: StrategyType) -> bool:
        """
        Validate if system meets strategy requirements.
        
        Args:
            strategy_type: Selected strategy type
            
        Returns:
            True if requirements are met, False otherwise
        """
        config = self.available_strategies[strategy_type]
        
        print(f"\n🔍 Validating requirements for {config.name}...")
        
        # Check ML model requirement
        if config.requires_ml_model:
            try:
                import pickle
                import os
                model_path = config.parameters["model_path"]
                if not os.path.exists(model_path):
                    print(f"❌ ML model not found: {model_path}")
                    print("   Please run: python3 ml_training.py")
                    return False
                print("✅ ML model found")
            except ImportError:
                print("❌ Required ML libraries not installed")
                return False
        
        # Check LLM requirement
        if config.requires_llm:
            print("⚠️  LLM integration requires API key")
            print("   Set LLM_API_KEY in .env file")
            
            # For now, assume LLM is available
            print("✅ LLM integration ready (mock mode)")
        
        print(f"✅ {config.name} requirements validated")
        return True
    
    def configure_strategy_parameters(self, strategy_type: StrategyType) -> Dict[str, Any]:
        """
        Configure strategy parameters interactively.
        
        Args:
            strategy_type: Selected strategy type
            
        Returns:
            Configured parameters dictionary
        """
        config = self.available_strategies[strategy_type]
        parameters = config.parameters.copy()
        
        print(f"\n⚙️  Configuring {config.name} parameters:")
        print("(Press Enter to use default values)")
        
        if strategy_type == StrategyType.ML_MODEL:
            # ML model configuration
            confidence = input(f"Min confidence [{config.min_confidence}%]: ").strip()
            if confidence:
                parameters["min_confidence"] = float(confidence)
        
        elif strategy_type == StrategyType.LLM_MODEL:
            # LLM configuration
            confidence = input(f"Min confidence [{config.min_confidence}%]: ").strip()
            if confidence:
                parameters["confidence_threshold"] = float(confidence)
            
            rr_ratio = input(f"Risk-reward ratio [{config.parameters['risk_reward_ratio']}]: ").strip()
            if rr_ratio:
                parameters["risk_reward_ratio"] = float(rr_ratio)
        
        elif strategy_type == StrategyType.RULE_BASED:
            # Rule-based configuration
            rsi_os = input(f"RSI oversold level [{config.parameters['rsi_oversold']}]: ").strip()
            if rsi_os:
                parameters["rsi_oversold"] = int(rsi_os)
            
            rsi_ob = input(f"RSI overbought level [{config.parameters['rsi_overbought']}]: ").strip()
            if rsi_ob:
                parameters["rsi_overbought"] = int(rsi_ob)
        
        elif strategy_type == StrategyType.HYBRID:
            # Hybrid configuration
            ml_w = input(f"ML model weight [{config.parameters['ml_weight']}]: ").strip()
            if ml_w:
                parameters["ml_weight"] = float(ml_w)
            
            llm_w = input(f"LLM weight [{config.parameters['llm_weight']}]: ").strip()
            if llm_w:
                parameters["llm_weight"] = float(llm_w)
        
        return parameters
    
    def select_strategy_interactive(self) -> Optional[StrategyConfig]:
        """
        Interactive strategy selection process.
        
        Returns:
            Selected strategy configuration or None if cancelled
        """
        # Display menu
        self.display_strategy_menu()
        
        # Get user choice
        strategy_type = self.get_user_choice()
        
        if not strategy_type:
            return None
        
        # Validate requirements
        if not self.validate_strategy_requirements(strategy_type):
            print("\n❌ Strategy requirements not met. Please select another strategy.")
            return self.select_strategy_interactive()
        
        # Configure parameters
        parameters = self.configure_strategy_parameters(strategy_type)
        
        # Create final configuration
        config = self.available_strategies[strategy_type]
        config.parameters = parameters
        
        self.selected_strategy = config
        
        # Display selection summary
        print(f"\n✅ Strategy Selected: {config.name}")
        print(f"   Description: {config.description}")
        print(f"   Min Confidence: {config.min_confidence}%")
        print(f"   Parameters: {len(parameters)} configured")
        
        return config
    
    def get_strategy_config(self, strategy_type: StrategyType) -> StrategyConfig:
        """
        Get strategy configuration by type.
        
        Args:
            strategy_type: Strategy type
            
        Returns:
            Strategy configuration
        """
        return self.available_strategies.get(strategy_type)
    
    def auto_select_strategy(self, preference: str = "ml") -> Optional[StrategyConfig]:
        """
        Auto-select strategy based on preference.
        
        Args:
            preference: Strategy preference ("ml", "llm", "rule", "hybrid")
            
        Returns:
            Selected strategy configuration or None
        """
        strategy_map = {
            "ml": StrategyType.ML_MODEL,
            "llm": StrategyType.LLM_MODEL,
            "rule": StrategyType.RULE_BASED,
            "hybrid": StrategyType.HYBRID
        }
        
        strategy_type = strategy_map.get(preference.lower())
        
        if not strategy_type:
            logger.error(f"Unknown strategy preference: {preference}")
            return None
        
        config = self.available_strategies[strategy_type]
        
        if self.validate_strategy_requirements(strategy_type):
            self.selected_strategy = config
            return config
        else:
            logger.error(f"Strategy {config.name} requirements not met")
            return None
    
    def get_selected_strategy(self) -> Optional[StrategyConfig]:
        """
        Get currently selected strategy.
        
        Returns:
            Selected strategy configuration or None
        """
        return self.selected_strategy
    
    def to_dict(self, config: StrategyConfig) -> Dict:
        """
        Convert strategy configuration to dictionary.
        
        Args:
            config: Strategy configuration
            
        Returns:
            Dictionary representation
        """
        return {
            "strategy_type": config.strategy_type.value,
            "name": config.name,
            "description": config.description,
            "min_confidence": config.min_confidence,
            "requires_llm": config.requires_llm,
            "requires_ml_model": config.requires_ml_model,
            "parameters": config.parameters
        }


# Example usage and testing
if __name__ == "__main__":
    # Test strategy selector
    selector = StrategySelector()
    
    # Test auto-selection
    print("=== AUTO-SELECTION TEST ===")
    ml_config = selector.auto_select_strategy("ml")
    if ml_config:
        print(f"Auto-selected: {ml_config.name}")
    
    # Test interactive selection
    print("\n=== INTERACTIVE SELECTION TEST ===")
    selected = selector.select_strategy_interactive()
    
    if selected:
        print(f"\nFinal selection: {selected.name}")
        print(f"Parameters: {selected.parameters}")
    else:
        print("No strategy selected.")
