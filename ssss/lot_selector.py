#!/usr/bin/env python3
"""
MCX Silver Futures - Automatic Lot Selection Module
==================================================
Dynamically calculates optimal lot sizes based on available capital and market conditions.

Features:
  • Fetches account balance from Dhan API
  • Calculates margin requirements for MCX Silver futures
  • Enforces risk constraints (max 5 lots, minimum capital)
  • Real-time lot size adjustment based on LTP

Usage:
    from lot_selector import LotSelector
    
    selector = LotSelector(dhan_client)
    lot_info = selector.calculate_optimal_lots(current_price=28100.50)
"""

import logging
import math
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LotInfo:
    """Lot selection result structure."""
    symbol: str
    lot_size: int
    max_lots: int
    trade_quantity: int
    margin_per_lot: float
    contract_value: float
    available_capital: float
    utilization_pct: float


class LotSelector:
    """
    Automatic lot selection for MCX Silver futures trading.
    
    Calculates optimal position sizes based on:
    - Available account balance
    - Current market price
    - Margin requirements
    - Risk constraints
    """
    
    # MCX Silver futures contract specifications
    SILVER_LOT_SIZE = 30  # kg per lot
    MARGIN_REQUIREMENT_PCT = 0.12  # 12% margin requirement
    MAX_LOTS = 5  # Risk management cap
    MIN_CAPITAL_REQUIRED = 50000  # Minimum capital to trade
    
    def __init__(self, dhan_client=None, mock_balance: float = None):
        """
        Initialize lot selector.
        
        Args:
            dhan_client: Dhan API client instance
            mock_balance: Mock balance for testing (overrides API call)
        """
        self.dhan_client = dhan_client
        self.mock_balance = mock_balance
        self.symbol = "SILVERM2026"  # Current MCX Silver mini contract
        
    def get_account_balance(self) -> float:
        """
        Fetch available account balance from Dhan API.
        
        Returns:
            Available trading balance in INR
        """
        if self.mock_balance:
            logger.info(f"Using mock balance: ₹{self.mock_balance:,.2f}")
            return self.mock_balance
            
        if not self.dhan_client:
            logger.warning("No Dhan client provided, using default balance")
            return 100000.0  # Default for testing
            
        try:
            # In paper trading mode, use configured capital
            if hasattr(self.dhan_client, 'paper_trade') and self.dhan_client.paper_trade:
                if hasattr(self.dhan_client, 'capital'):
                    balance = self.dhan_client.capital
                    logger.info(f"Paper trading balance: ₹{balance:,.2f}")
                    return balance
                else:
                    return 100000.0  # Default paper trading capital
            
            # For live trading, fetch from API
            response = self.dhan_client.session.get(
                f"{self.dhan_client.base_url}/limits"
            )
            
            if response.status_code == 200:
                data = response.json()
                balance = float(data.get('net', 0))
                logger.info(f"Live account balance: ₹{balance:,.2f}")
                return balance
            else:
                logger.error(f"Failed to fetch balance: {response.status_code}")
                return 100000.0  # Fallback
                
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return 100000.0  # Safe fallback
    
    def calculate_margin_requirements(self, ltp: float) -> Tuple[float, float]:
        """
        Calculate margin per lot and total contract value.
        
        Args:
            ltp: Last traded price of Silver futures
            
        Returns:
            Tuple of (margin_per_lot, contract_value)
        """
        contract_value = ltp * self.SILVER_LOT_SIZE
        margin_per_lot = contract_value * self.MARGIN_REQUIREMENT_PCT
        
        logger.debug(f"Contract value: ₹{contract_value:,.2f}")
        logger.debug(f"Margin per lot: ₹{margin_per_lot:,.2f}")
        
        return margin_per_lot, contract_value
    
    def calculate_optimal_lots(self, current_price: float) -> LotInfo:
        """
        Calculate optimal number of lots based on available capital.
        
        Args:
            current_price: Current LTP of Silver futures
            
        Returns:
            LotInfo object with calculated parameters
        """
        # Get available capital
        available_capital = self.get_account_balance()
        
        # Check minimum capital requirement
        if available_capital < self.MIN_CAPITAL_REQUIRED:
            logger.warning(f"Insufficient capital: ₹{available_capital:,.2f} < ₹{self.MIN_CAPITAL_REQUIRED:,.2f}")
            return LotInfo(
                symbol=self.symbol,
                lot_size=self.SILVER_LOT_SIZE,
                max_lots=0,
                trade_quantity=0,
                margin_per_lot=0,
                contract_value=0,
                available_capital=available_capital,
                utilization_pct=0
            )
        
        # Calculate margin requirements
        margin_per_lot, contract_value = self.calculate_margin_requirements(current_price)
        
        # Calculate maximum lots based on capital
        max_lots_by_capital = math.floor(available_capital / margin_per_lot)
        
        # Apply risk constraints
        max_lots = min(max_lots_by_capital, self.MAX_LOTS, 5)  # Hard cap at 5 lots
        
        # Ensure at least 1 lot if capital is sufficient
        if max_lots < 1 and available_capital >= margin_per_lot:
            max_lots = 1
        elif max_lots < 1:
            max_lots = 0
        
        # Calculate total trade quantity
        trade_quantity = max_lots * self.SILVER_LOT_SIZE
        
        # Calculate capital utilization
        total_margin = max_lots * margin_per_lot
        utilization_pct = (total_margin / available_capital * 100) if available_capital > 0 else 0
        
        lot_info = LotInfo(
            symbol=self.symbol,
            lot_size=self.SILVER_LOT_SIZE,
            max_lots=max_lots,
            trade_quantity=trade_quantity,
            margin_per_lot=margin_per_lot,
            contract_value=contract_value,
            available_capital=available_capital,
            utilization_pct=utilization_pct
        )
        
        # Log calculation details
        logger.info("=== LOT SELECTION RESULTS ===")
        logger.info(f"Available Capital: ₹{available_capital:,.2f}")
        logger.info(f"Current Price: ₹{current_price:,.2f}")
        logger.info(f"Contract Value: ₹{contract_value:,.2f}")
        logger.info(f"Margin per Lot: ₹{margin_per_lot:,.2f}")
        logger.info(f"Maximum Lots: {max_lots}")
        logger.info(f"Trade Quantity: {trade_quantity} kg")
        logger.info(f"Capital Utilization: {utilization_pct:.1f}%")
        logger.info("=" * 30)
        
        return lot_info
    
    def to_dict(self, lot_info: LotInfo) -> Dict:
        """
        Convert LotInfo to dictionary format.
        
        Args:
            lot_info: LotInfo object
            
        Returns:
            Dictionary representation
        """
        return {
            "symbol": lot_info.symbol,
            "lot_size": lot_info.lot_size,
            "max_lots": lot_info.max_lots,
            "trade_quantity": lot_info.trade_quantity,
            "margin_per_lot": lot_info.margin_per_lot,
            "contract_value": lot_info.contract_value,
            "available_capital": lot_info.available_capital,
            "utilization_pct": round(lot_info.utilization_pct, 2)
        }
    
    def validate_risk_limits(self, lot_info: LotInfo) -> bool:
        """
        Validate if the selected lot size meets risk criteria.
        
        Args:
            lot_info: Lot selection result
            
        Returns:
            True if within risk limits, False otherwise
        """
        # Check if lots are allocated
        if lot_info.max_lots <= 0:
            logger.error("No lots allocated - insufficient capital")
            return False
        
        # Check maximum lot limit
        if lot_info.max_lots > self.MAX_LOTS:
            logger.error(f"Exceeds maximum lot limit: {lot_info.max_lots} > {self.MAX_LOTS}")
            return False
        
        # Check capital utilization (should not exceed 80%)
        if lot_info.utilization_pct > 80:
            logger.warning(f"High capital utilization: {lot_info.utilization_pct:.1f}%")
        
        # Check minimum capital requirement
        if lot_info.available_capital < self.MIN_CAPITAL_REQUIRED:
            logger.error(f"Insufficient capital: ₹{lot_info.available_capital:,.2f}")
            return False
        
        logger.info("✅ Risk validation passed")
        return True


# Example usage and testing
if __name__ == "__main__":
    # Test with mock data
    selector = LotSelector(mock_balance=200000.0)
    
    # Test at different price levels
    test_prices = [28000, 28500, 29000, 29500]
    
    for price in test_prices:
        print(f"\n--- Testing at ₹{price} ---")
        lot_info = selector.calculate_optimal_lots(price)
        
        if selector.validate_risk_limits(lot_info):
            print(f"✅ Can trade {lot_info.max_lots} lots ({lot_info.trade_quantity} kg)")
        else:
            print("❌ Cannot trade - risk limits exceeded")
