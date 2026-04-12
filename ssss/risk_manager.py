#!/usr/bin/env python3
"""
MCX Silver Futures - Enhanced Risk Management Module
===================================================
Advanced risk management with daily limits, position tracking, and dynamic adjustments.

Features:
  • Daily loss limit enforcement (3% default)
  • Position size validation and limits
  • ATR-based dynamic stop loss
  • Real-time risk monitoring
  • Trade execution validation
  • Portfolio risk metrics

Usage:
    from risk_manager import RiskManager
    
    risk_mgr = RiskManager(capital=100000)
    is_valid = risk_mgr.validate_trade(decision, lot_info)
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Risk metrics structure."""
    daily_pnl: float
    daily_trades: int
    daily_wins: int
    daily_losses: int
    max_drawdown: float
    current_drawdown: float
    risk_score: float
    sharpe_ratio: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float


@dataclass
class RiskLimits:
    """Risk limits configuration."""
    daily_loss_limit_pct: float = 3.0
    max_risk_per_trade_pct: float = 1.5
    max_position_size_lots: int = 5
    max_daily_trades: int = 20
    max_consecutive_losses: int = 5
    min_rr_ratio: float = 1.5
    max_portfolio_risk_pct: float = 10.0
    atr_multiplier: float = 1.5
    volatility_threshold: float = 0.02


class RiskManager:
    """
    Advanced risk management for MCX Silver futures trading.
    
    Enforces trading discipline through:
    - Daily loss limits
    - Position size controls
    - Risk-reward validation
    - Portfolio-level risk monitoring
    """
    
    def __init__(self, capital: float, limits: RiskLimits = None):
        """
        Initialize risk manager.
        
        Args:
            capital: Available trading capital
            limits: Risk limits configuration
        """
        self.capital = capital
        self.limits = limits or RiskLimits()
        
        # Tracking variables
        self.daily_start_time = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.consecutive_losses = 0
        self.max_portfolio_value = capital
        self.trade_history = []
        
        # Risk state
        self.trading_enabled = True
        self.risk_alerts = []
        
        logger.info(f"Risk manager initialized: ₹{capital:,.2f} capital")
        logger.info(f"Daily loss limit: {self.limits.daily_loss_limit_pct}%")
        logger.info(f"Max risk per trade: {self.limits.max_risk_per_trade_pct}%")
    
    def reset_daily_metrics(self):
        """Reset daily metrics at start of new trading day."""
        now = datetime.now()
        
        # Check if new trading day
        if now.date() > self.daily_start_time.date():
            logger.info("📅 New trading day - resetting metrics")
            
            # Save previous day's metrics
            if self.daily_trades > 0:
                self._save_daily_summary()
            
            # Reset metrics
            self.daily_start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.daily_wins = 0
            self.daily_losses = 0
            self.consecutive_losses = 0
            self.risk_alerts.clear()
            self.trading_enabled = True
            
            logger.info("✅ Daily metrics reset")
    
    def calculate_position_risk(self, entry_price: float, stop_loss: float, 
                              lot_size: int, quantity_per_lot: int) -> Dict[str, float]:
        """
        Calculate position risk metrics.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            lot_size: Number of lots
            quantity_per_lot: Quantity per lot
            
        Returns:
            Dictionary with risk metrics
        """
        total_quantity = lot_size * quantity_per_lot
        contract_value = entry_price * total_quantity
        risk_per_unit = abs(entry_price - stop_loss)
        total_risk = risk_per_unit * total_quantity
        risk_pct = (total_risk / self.capital) * 100
        
        return {
            'contract_value': contract_value,
            'risk_per_unit': risk_per_unit,
            'total_risk': total_risk,
            'risk_pct': risk_pct,
            'total_quantity': total_quantity
        }
    
    def validate_trade_size(self, lot_info, decision) -> Tuple[bool, str]:
        """
        Validate trade size against risk limits.
        
        Args:
            lot_info: Lot selection information
            decision: Trading decision
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if decision.action == "HOLD":
            return True, "No trade to validate"
        
        # Check position size limits
        if lot_info.max_lots > self.limits.max_position_size_lots:
            return False, f"Position size exceeds limit: {lot_info.max_lots} > {self.limits.max_position_size_lots}"
        
        # Calculate position risk
        risk_metrics = self.calculate_position_risk(
            decision.entry_price, decision.stop_loss,
            lot_info.max_lots, lot_info.lot_size
        )
        
        # Check risk per trade
        if risk_metrics['risk_pct'] > self.limits.max_risk_per_trade_pct:
            return False, f"Risk per trade too high: {risk_metrics['risk_pct']:.2f}% > {self.limits.max_risk_per_trade_pct}%"
        
        # Check risk-reward ratio
        if decision.risk_reward_ratio < self.limits.min_rr_ratio:
            return False, f"Risk-reward ratio too low: {decision.risk_reward_ratio:.2f} < {self.limits.min_rr_ratio}"
        
        return True, "Trade size validated"
    
    def validate_daily_limits(self) -> Tuple[bool, str]:
        """
        Validate against daily trading limits.
        
        Returns:
            Tuple of (can_trade, reason)
        """
        # Reset metrics if new day
        self.reset_daily_metrics()
        
        # Check daily loss limit
        daily_loss_limit = self.capital * (self.limits.daily_loss_limit_pct / 100)
        if self.daily_pnl <= -abs(daily_loss_limit):
            return False, f"Daily loss limit reached: ₹{self.daily_pnl:,.2f} ≤ -₹{daily_loss_limit:,.2f}"
        
        # Check max daily trades
        if self.daily_trades >= self.limits.max_daily_trades:
            return False, f"Daily trade limit reached: {self.daily_trades} ≥ {self.limits.max_daily_trades}"
        
        # Check consecutive losses
        if self.consecutive_losses >= self.limits.max_consecutive_losses:
            return False, f"Too many consecutive losses: {self.consecutive_losses} ≥ {self.limits.max_consecutive_losses}"
        
        return True, "Daily limits OK"
    
    def calculate_atr_stop_loss(self, current_price: float, atr: float, side: str) -> float:
        """
        Calculate ATR-based stop loss.
        
        Args:
            current_price: Current market price
            atr: Average True Range
            side: Trade side (BUY/SELL)
            
        Returns:
            Stop loss price
        """
        stop_distance = atr * self.limits.atr_multiplier
        
        if side == "BUY":
            return current_price - stop_distance
        else:  # SELL
            return current_price + stop_distance
    
    def adjust_position_size(self, base_lots: int, confidence: float, volatility: float) -> int:
        """
        Adjust position size based on confidence and volatility.
        
        Args:
            base_lots: Base number of lots
            confidence: Signal confidence (0-100)
            volatility: Market volatility
            
        Returns:
            Adjusted number of lots
        """
        # Reduce size for low confidence
        if confidence < 70:
            base_lots = max(1, base_lots - 1)
        
        # Reduce size for high volatility
        if volatility > self.limits.volatility_threshold:
            base_lots = max(1, base_lots - 1)
        
        # Increase size for high confidence and low volatility
        if confidence > 85 and volatility < self.limits.volatility_threshold / 2:
            base_lots = min(self.limits.max_position_size_lots, base_lots + 1)
        
        return max(0, base_lots)
    
    def record_trade(self, decision: Any, entry_price: float, exit_price: float = None):
        """
        Record trade execution and update metrics.
        
        Args:
            decision: Trading decision
            entry_price: Entry price
            exit_price: Exit price (if closed)
        """
        trade = {
            'timestamp': datetime.now().isoformat(),
            'action': decision.action,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'stop_loss': decision.stop_loss,
            'target': decision.target,
            'confidence': decision.confidence,
            'quantity': getattr(decision, 'quantity', 0)
        }
        
        self.trade_history.append(trade)
        self.daily_trades += 1
        
        # Calculate P&L if trade is closed
        if exit_price:
            pnl = self._calculate_pnl(decision.action, entry_price, exit_price, trade['quantity'])
            self.daily_pnl += pnl
            
            if pnl > 0:
                self.daily_wins += 1
                self.consecutive_losses = 0
            else:
                self.daily_losses += 1
                self.consecutive_losses += 1
        
        # Update portfolio value for drawdown calculation
        current_portfolio_value = self.capital + self.daily_pnl
        if current_portfolio_value > self.max_portfolio_value:
            self.max_portfolio_value = current_portfolio_value
        
        logger.info(f"Trade recorded: {decision.action} @ ₹{entry_price:.2f}, P&L: ₹{pnl if exit_price else 0:.2f}")
    
    def _calculate_pnl(self, action: str, entry_price: float, exit_price: float, quantity: int) -> float:
        """Calculate P&L for a trade."""
        if action == "BUY":
            return (exit_price - entry_price) * quantity
        else:  # SELL
            return (entry_price - exit_price) * quantity
    
    def get_risk_metrics(self) -> RiskMetrics:
        """
        Calculate current risk metrics.
        
        Returns:
            RiskMetrics object
        """
        # Calculate drawdown
        current_portfolio_value = self.capital + self.daily_pnl
        current_drawdown = (self.max_portfolio_value - current_portfolio_value) / self.max_portfolio_value * 100
        
        # Calculate win rate
        win_rate = (self.daily_wins / self.daily_trades * 100) if self.daily_trades > 0 else 0
        
        # Calculate average win/loss
        wins = [t['exit_price'] - t['entry_price'] for t in self.trade_history if t.get('exit_price') and t['exit_price'] > t['entry_price']]
        losses = [t['entry_price'] - t['exit_price'] for t in self.trade_history if t.get('exit_price') and t['exit_price'] < t['entry_price']]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        # Calculate profit factor
        total_wins = sum(wins)
        total_losses = sum(losses)
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Calculate risk score (0-100, higher is riskier)
        risk_score = min(100, (
            abs(self.daily_pnl) / self.capital * 50 +  # P&L impact
            self.consecutive_losses * 10 +              # Consecutive losses
            current_drawdown * 2 +                       # Drawdown
            (100 - win_rate) * 0.5                       # Win rate inverse
        ))
        
        return RiskMetrics(
            daily_pnl=self.daily_pnl,
            daily_trades=self.daily_trades,
            daily_wins=self.daily_wins,
            daily_losses=self.daily_losses,
            max_drawdown=0,  # Would need historical data
            current_drawdown=current_drawdown,
            risk_score=risk_score,
            sharpe_ratio=0,  # Would need more data
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor
        )
    
    def validate_trade(self, decision: Any, lot_info: Any, current_price: float, atr: float = None) -> Tuple[bool, str]:
        """
        Comprehensive trade validation.
        
        Args:
            decision: Trading decision
            lot_info: Lot selection information
            current_price: Current market price
            atr: Average True Range (optional)
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if decision.action == "HOLD":
            return True, "No trade to validate"
        
        # Check daily limits
        can_trade, reason = self.validate_daily_limits()
        if not can_trade:
            return False, reason
        
        # Validate trade size
        size_valid, size_reason = self.validate_trade_size(lot_info, decision)
        if not size_valid:
            return False, size_reason
        
        # Adjust stop loss with ATR if provided
        if atr and decision.stop_loss:
            atr_sl = self.calculate_atr_stop_loss(current_price, atr, decision.action)
            # Use the tighter stop loss
            if decision.action == "BUY":
                decision.stop_loss = max(decision.stop_loss, atr_sl)
            else:
                decision.stop_loss = min(decision.stop_loss, atr_sl)
        
        # Adjust position size based on confidence and volatility
        volatility = atr / current_price if atr and current_price > 0 else 0.01
        adjusted_lots = self.adjust_position_size(lot_info.max_lots, decision.confidence, volatility)
        
        if adjusted_lots != lot_info.max_lots:
            logger.info(f"Position size adjusted: {lot_info.max_lots} → {adjusted_lots} lots")
            lot_info.max_lots = adjusted_lots
            lot_info.trade_quantity = adjusted_lots * lot_info.lot_size
        
        return True, "Trade validated"
    
    def _save_daily_summary(self):
        """Save daily trading summary."""
        summary = {
            'date': self.daily_start_time.date().isoformat(),
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'daily_wins': self.daily_wins,
            'daily_losses': self.daily_losses,
            'win_rate': (self.daily_wins / self.daily_trades * 100) if self.daily_trades > 0 else 0,
            'risk_alerts': self.risk_alerts
        }
        
        # Save to file
        filename = f"daily_summary_{self.daily_start_time.date().isoformat()}.json"
        try:
            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Daily summary saved: {filename}")
        except Exception as e:
            logger.error(f"Error saving daily summary: {e}")
    
    def get_risk_alerts(self) -> list:
        """Get current risk alerts."""
        alerts = []
        
        # Check for risk alerts
        if self.daily_pnl < -self.capital * (self.limits.daily_loss_limit_pct * 0.5 / 100):
            alerts.append("⚠️ Approaching daily loss limit")
        
        if self.consecutive_losses >= 3:
            alerts.append(f"⚠️ {self.consecutive_losses} consecutive losses")
        
        if self.daily_trades >= self.limits.max_daily_trades * 0.8:
            alerts.append("⚠️ Approaching daily trade limit")
        
        return alerts
    
    def disable_trading(self, reason: str):
        """Disable trading due to risk limits."""
        self.trading_enabled = False
        self.risk_alerts.append(f"🛑 Trading disabled: {reason}")
        logger.error(f"Trading disabled: {reason}")
    
    def enable_trading(self):
        """Re-enable trading (new day or manual override)."""
        self.trading_enabled = True
        logger.info("✅ Trading enabled")


# Example usage and testing
if __name__ == "__main__":
    # Test risk manager
    risk_mgr = RiskManager(capital=100000)
    
    # Test trade validation
    from lot_selector import LotSelector, LotInfo
    from llm_engine import TradingDecision
    
    # Create sample data
    lot_selector = LotSelector(mock_balance=100000)
    lot_info = lot_selector.calculate_optimal_lots(28150.0)
    
    decision = TradingDecision(
        action="BUY",
        confidence=75.0,
        entry_price=28150.0,
        stop_loss=27980.0,
        target=28490.0,
        reason="Test trade",
        timestamp=datetime.now().isoformat(),
        risk_reward_ratio=2.0
    )
    
    # Validate trade
    is_valid, reason = risk_mgr.validate_trade(decision, lot_info, 28150.0, 85.5)
    print(f"Trade validation: {'✅' if is_valid else '❌'} {reason}")
    
    # Get risk metrics
    metrics = risk_mgr.get_risk_metrics()
    print(f"Risk score: {metrics.risk_score:.1f}/100")
    print(f"Daily P&L: ₹{metrics.daily_pnl:,.2f}")
