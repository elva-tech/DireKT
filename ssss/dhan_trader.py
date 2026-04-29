"""
Dhan Platform - Paper Trading Executor
======================================
Execute paper trades (and live trades) on Dhan platform.
"""

import os
import logging
import json
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
DHAN_BASE_URL = "https://api.dhan.co/v1"
ORDER_STATUS = {
    'PENDING': 'Order pending',
    'CONFIRMED': 'Order confirmed',
    'REJECTED': 'Order rejected',
    'CANCELLED': 'Order cancelled',
    'TRADED': 'Order traded',
    'EXPIRED': 'Order expired'
}


@dataclass
class TradeOrder:
    """Trade order structure."""
    order_id: str
    symbol: str
    exchange: str
    quantity: int
    price: float
    side: str           # BUY or SELL
    order_type: str     # LIMIT, MARKET
    status: str
    timestamp: str
    sl_price: Optional[float] = None
    target_price: Optional[float] = None
    
    def __repr__(self):
        return f"Order #{self.order_id}: {self.side} {self.quantity} {self.symbol} @ ₹{self.price}"


class DhanTradingClient:
    """Execute trades on Dhan platform."""
    
    def __init__(self, access_token: str, client_id: str, paper_trade: bool = True):
        """
        Initialize Dhan trading client.
        
        Args:
            access_token: Dhan access token / API key
            client_id: Your Dhan client ID
            paper_trade: True for paper trading, False for live (use with caution!)
        """
        self.access_token = access_token
        self.client_id = client_id
        self.paper_trade = paper_trade
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        })
        
        self.orders = {}  # Track all orders locally
        self.positions = {}  # Track open positions
        
        mode = "📄 PAPER TRADING" if paper_trade else "💰 LIVE TRADING"
        log.warning(f"⚠️ {mode} MODE ACTIVE")
        log.info(f"Initialized Dhan client: {client_id}")
    
    def place_order(self, 
                   symbol: str,
                   quantity: int,
                   side: str,
                   price: float,
                   exchange: str = 'MCX',
                   order_type: str = 'LIMIT',
                   sl_price: Optional[float] = None,
                   target_price: Optional[float] = None) -> Optional[TradeOrder]:
        """
        Place a new order.
        
        Args:
            symbol: Trading symbol
            quantity: Number of contracts
            side: 'BUY' or 'SELL'
            price: Limit price
            exchange: Exchange code
            order_type: 'LIMIT' or 'MARKET'
            sl_price: Stop loss price
            target_price: Target/profit booking price
        
        Returns:
            TradeOrder object or None if failed
        """
        
        try:
            # Validate inputs
            if side.upper() not in ['BUY', 'SELL']:
                log.error(f"Invalid side: {side}. Use BUY or SELL")
                return None
            
            if quantity <= 0:
                log.error(f"Invalid quantity: {quantity}")
                return None
            
            # Paper trading - simulate order
            if self.paper_trade:
                return self._simulate_order(symbol, quantity, side, price, exchange, 
                                           order_type, sl_price, target_price)
            
            # Live trading - send to Dhan API
            payload = {
                'clientID': self.client_id,
                'instrumentKey': self._get_instrument_key(symbol, exchange),
                'orderType': order_type,
                'legNo': 1,
                'quantity': quantity,
                'price': price,
                'disclosedQuantity': 0,
                'side': side.upper(),
                'productType': 'MIS' if order_type == 'MARKET' else 'CNC',
                'orderTimestamp': datetime.now().isoformat(),
                'stopPrice': sl_price or 0,
                'targetPrice': target_price or 0
            }
            
            response = self.session.post(
                f"{DHAN_BASE_URL}/orders/place",
                json=payload,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                order = TradeOrder(
                    order_id=data.get('orderId', str(datetime.now().timestamp())),
                    symbol=symbol,
                    exchange=exchange,
                    quantity=quantity,
                    price=price,
                    side=side.upper(),
                    order_type=order_type,
                    status='CONFIRMED',
                    timestamp=datetime.now().isoformat(),
                    sl_price=sl_price,
                    target_price=target_price
                )
                
                self.orders[order.order_id] = order
                log.info(f"✅ Order placed: {order}")
                return order
            else:
                log.error(f"❌ Order placement failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            log.error(f"❌ Error placing order: {e}")
            return None
    
    def _simulate_order(self, symbol: str, quantity: int, side: str, price: float,
                       exchange: str, order_type: str, sl_price: Optional[float],
                       target_price: Optional[float]) -> TradeOrder:
        """Simulate order for paper trading."""
        order_id = f"PAPER_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        order = TradeOrder(
            order_id=order_id,
            symbol=symbol,
            exchange=exchange,
            quantity=quantity,
            price=price,
            side=side.upper(),
            order_type=order_type,
            status='TRADED',  # Paper trading assumes immediate execution
            timestamp=datetime.now().isoformat(),
            sl_price=sl_price,
            target_price=target_price
        )
        
        self.orders[order_id] = order
        
        # Update position
        key = f"{symbol}_{side.upper()}"
        if key not in self.positions:
            self.positions[key] = {
                'symbol': symbol,
                'quantity': 0,
                'avg_price': 0,
                'side': side.upper()
            }
        
        self.positions[key]['quantity'] += quantity
        self.positions[key]['avg_price'] = price
        
        log.info(f"📄 PAPER ORDER EXECUTED: {order}")
        log.info(f"   SL: ₹{sl_price or 'N/A'} | Target: ₹{target_price or 'N/A'}")
        
        return order
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get status of an order."""
        try:
            if order_id in self.orders:
                return asdict(self.orders[order_id])
            
            # Fetch from API (live trading)
            response = self.session.get(
                f"{DHAN_BASE_URL}/orders/{order_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                log.warning(f"Could not fetch status for order {order_id}")
                return None
                
        except Exception as e:
            log.error(f"Error getting order status: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            if self.paper_trade:
                if order_id in self.orders:
                    self.orders[order_id].status = 'CANCELLED'
                    log.info(f"✅ PAPER ORDER CANCELLED: {order_id}")
                    return True
                return False
            
            # Live trading
            response = self.session.delete(
                f"{DHAN_BASE_URL}/orders/{order_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                log.info(f"✅ Order cancelled: {order_id}")
                return True
            else:
                log.error(f"❌ Failed to cancel order: {response.text}")
                return False
                
        except Exception as e:
            log.error(f"Error cancelling order: {e}")
            return False
    
    def get_open_positions(self) -> Dict:
        """Get all open positions."""
        if self.paper_trade:
            return self.positions
        
        try:
            response = self.session.get(
                f"{DHAN_BASE_URL}/positions",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                log.warning("Could not fetch positions")
                return {}
                
        except Exception as e:
            log.error(f"Error fetching positions: {e}")
            return {}
    
    def get_trade_history(self) -> List[Dict]:
        """Get trade execution history."""
        return list(self.orders.values())
    
    def close_position(self, symbol: str, side: str, quantity: int, 
                      current_price: float) -> Optional[TradeOrder]:
        """Close an open position with opposite order."""
        opposite_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
        
        order = self.place_order(
            symbol=symbol,
            quantity=quantity,
            side=opposite_side,
            price=current_price,
            order_type='MARKET'
        )
        
        if order:
            log.info(f"✅ Position closed: {symbol} {quantity} @ ₹{current_price}")
        
        return order
    
    def _get_instrument_key(self, symbol: str, exchange: str) -> str:
        """Get instrument key for API call."""
        # Format: EXCHANGE|SYMBOL|EXPIRY|TYPE
        # Example: MCX|SILVER|25MAR2024|FUT
        return f"{exchange}|{symbol}|FUT"
    
    def export_trades(self, filepath: str = 'trade_history.json'):
        """Export trade history to JSON."""
        trades = [asdict(order) for order in self.orders.values()]
        
        with open(filepath, 'w') as f:
            json.dump(trades, f, indent=2)
        
        log.info(f"Trade history exported to {filepath}")


# ── Example Usage ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    access_token = os.getenv('DHAN_ACCESS_TOKEN')
    client_id = os.getenv('DHAN_CLIENT_ID')
    
    if not all([access_token, client_id]):
        log.error("❌ Missing Dhan credentials. Add to .env file")
        exit(1)
    
    # Initialize trading client (PAPER TRADING MODE)
    client = DhanTradingClient(access_token, client_id, paper_trade=True)
    
    # Example: Place a paper trade
    log.info("\n💡 Example: Placing a sample paper trade...")
    
    order = client.place_order(
        symbol='SILVER',
        quantity=5,
        side='BUY',
        price=72000,
        sl_price=71500,
        target_price=72700
    )
    
    if order:
        log.info(f"\nOrder Status: {order.status}")
        
        # Get positions
        positions = client.get_open_positions()
        log.info(f"\n📊 Open Positions:\n{json.dumps(positions, indent=2)}")
        
        # Export trades
        client.export_trades()
