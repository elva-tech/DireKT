"""
Angel One SmartAPI Real-Time Data Fetcher
==========================================
Fetches live price data for MCX silver futures from Angel One SmartAPI.
"""

import os
import json
import logging
import hmac
import hashlib
import base64
import requests
import time as time_module
import threading
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
ANGEL_ONE_BASE_URL = "https://smartapi.angelbroking.com/rest/secure"
ANGEL_ONE_SOCKET_URL = "wss://smartapisocket.angelone.in/smart-stream"  # Free-tier endpoint
TOKEN_VALIDITY_MINUTES = 115  # SmartAPI tokens are valid for 120 minutes

def _env_clean(name: str, default: str = "") -> str:
    raw = os.getenv(name, default)
    if raw is None:
        return default
    return str(raw).split("#", 1)[0].strip()


# If enabled, the system will NOT fall back to local historical replay data.
# It will return `None` when live websocket/REST quotes fail.
EXTERNAL_DATA_ONLY = _env_clean("EXTERNAL_DATA_ONLY", "true").lower() in ("1", "true", "yes", "y")


@dataclass
class QuoteData:
    """Real-time quote data structure."""
    symbol: str
    exchange: str
    ltp: float           # Last Traded Price
    volume: int
    bid: float
    ask: float
    open_price: float
    high: float
    low: float
    close_price: float
    timestamp: str
    oi: int              # Open Interest

    def __repr__(self):
        return f"{self.symbol}@{self.ltp} (Vol: {self.volume}, OI: {self.oi})"


class AngelOneConnector:
    """Connect to Angel One SmartAPI for real-time data."""
    
    def __init__(self, client_id: str, client_secret: str, api_key: str, 
                 totp_secret: str, password: str, user_id: str):
        """
        Initialize Angel One SmartAPI connector.
        
        Args:
            client_id: SmartAPI client ID
            client_secret: SmartAPI client secret
            api_key: SmartAPI API key
            totp_secret: TOTP secret for 2FA
            password: Account password
            user_id: User ID
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_key = api_key
        self.totp_secret = totp_secret
        self.password = password
        self.user_id = user_id
        
        self.session = requests.Session()
        self.auth_token = None
        self.token_created_at = None
        self.is_authenticated = False
        self.feed_token = None
        self.smart_api = None
        
        # WebSocket streaming quotes
        self.ws_client = None
        self.use_websocket = False
        
        log.info(f"Initializing Angel One SmartAPI connector for client: {client_id}")
    
    def _generate_totp(self) -> str:
        """Generate TOTP token from secret."""
        try:
            import pyotp
            totp = pyotp.TOTP(self.totp_secret)
            return totp.now()
        except:
            # Fallback to manual TOTP generation if pyotp not available
            import time
            key = base64.b32decode(self.totp_secret)
            counter = int(time.time()) // 30
            msg = counter.to_bytes(8, 'big')
            hmac_hash = hmac.new(key, msg, hashlib.sha1).digest()
            offset = hmac_hash[-1] & 0xf
            code = (int.from_bytes(hmac_hash[offset:offset+4], 'big') & 0x7fffffff) % 1000000
            return f"{code:06d}"
    
    def authenticate(self, force_fresh: bool = False) -> bool:
        """
        Authenticate with Angel One SmartAPI.
        First tries to use pre-generated JWT token from environment.
        Falls back to OAuth flow if needed.
        """
        try:
            log.info("🔐 Authenticating with Angel One SmartAPI...")
            
            # CHECK 1: Try environment JWT token first (most reliable)
            env_auth_token = os.getenv('ANGEL_ONE_AUTH_TOKEN')
            if not force_fresh and env_auth_token and env_auth_token.startswith('eyJ'):
                log.info("✅ Using pre-generated JWT token from environment")
                self.auth_token = env_auth_token
                self.token_created_at = datetime.now()
                self.is_authenticated = True
                try:
                    from SmartApi import SmartConnect
                    self.smart_api = SmartConnect(api_key=self.api_key)
                    self.smart_api.setAccessToken(self.auth_token)
                except Exception as e:
                    log.warning(f"⚠️ SmartConnect init with env JWT failed: {e}")
                
                # Also try to get feed token if available
                env_feed_token = os.getenv('ANGEL_ONE_FEED_TOKEN')
                if env_feed_token:
                    self.feed_token = env_feed_token
                    if self.smart_api:
                        try:
                            self.smart_api.setFeedToken(env_feed_token)
                        except Exception:
                            pass
                
                log.info("✅ Angel One SmartAPI authentication successful (using JWT)")
                log.debug(f"   Auth Token: {self.auth_token[:30]}...")
                
                # Setup WebSocket for real-time quotes
                self._setup_websocket()
                
                return True

            # If env_auth_token is present but prefixed with "Bearer ", normalize it
            # (some users store "Bearer <jwt>" instead of just the JWT).
            if not force_fresh and env_auth_token and env_auth_token.lower().startswith("bearer "):
                jwt = env_auth_token[7:].strip()
                if jwt.startswith("eyJ"):
                    log.info("✅ Using pre-generated JWT token from environment (normalized Bearer prefix)")
                    self.auth_token = jwt
                    self.token_created_at = datetime.now()
                    self.is_authenticated = True
                    try:
                        from SmartApi import SmartConnect
                        self.smart_api = SmartConnect(api_key=self.api_key)
                        self.smart_api.setAccessToken(self.auth_token)
                    except Exception as e:
                        log.warning(f"⚠️ SmartConnect init with normalized JWT failed: {e}")
                    env_feed_token = os.getenv('ANGEL_ONE_FEED_TOKEN')
                    if env_feed_token:
                        self.feed_token = env_feed_token
                        if self.smart_api:
                            try:
                                self.smart_api.setFeedToken(env_feed_token)
                            except Exception:
                                pass
                    self._setup_websocket()
                    return True
            
            # FALLBACK: Generate TOTP and try OAuth endpoints
            log.debug("No usable env JWT token (or force_fresh=True), attempting SmartConnect login...")
            totp = self._generate_totp()
            log.debug(f"TOTP generated: {totp}")

            # RELIABLE fallback: use the official SmartApi SmartConnect flow.
            # (The raw REST endpoints above are more likely to break with plan/IP changes,
            # and your allocator already uses SmartConnect successfully.)
            try:
                from SmartApi import SmartConnect

                smart = SmartConnect(api_key=self.api_key)
                session = smart.generateSession(self.client_id, self.password, totp)
                if session.get("status") and session.get("data"):
                    self.auth_token = session["data"].get("jwtToken")
                    self.feed_token = session["data"].get("feedToken") or smart.getfeedToken()
                    self.smart_api = smart
                    self.token_created_at = datetime.now()
                    self.is_authenticated = True
                    log.info("✅ Angel One SmartAPI authentication successful (SmartConnect)")
                    # Setup WebSocket for real-time quotes
                    self._setup_websocket()
                    return True
                log.debug(f"SmartConnect session failed: {session}")
            except Exception as e:
                log.debug(f"SmartConnect fallback auth failed: {e}")

            # If SmartConnect also fails, return False so the integration can report it.
            log.error("❌ Authentication failed (no valid env JWT and SmartConnect login unsuccessful).")
            return False
                
        except Exception as e:
            log.error(f"❌ Authentication error: {e}")
            import traceback
            log.debug(traceback.format_exc())
            return False
    
    def is_token_valid(self) -> bool:
        """Check if token is still valid."""
        if not self.token_created_at:
            return False
        
        elapsed_minutes = (datetime.now() - self.token_created_at).total_seconds() / 60
        return elapsed_minutes < TOKEN_VALIDITY_MINUTES
    
    def _setup_websocket(self):
        """Setup WebSocket client for real-time quote streaming after authentication."""
        try:
            # Import here to avoid circular imports
            from angel_one_websocket import AngelOneWebSocketClient
            
            if self.ws_client:
                # Disconnect existing client
                self.ws_client.disconnect()
            
            # Create WebSocket client with authenticated credentials
            self.ws_client = AngelOneWebSocketClient(
                auth_token=self.auth_token,
                api_key=self.api_key,
                client_id=self.client_id
            )
            
            # Set up callbacks
            def on_quote(quote):
                log.debug(f"📊 WS Quote: {quote.symbol} = {quote.ltp} Vol:{quote.volume}")
            
            def on_error(error):
                log.warning(f"⚠️ WebSocket Error: {error}")
            
            self.ws_client.set_quote_callback(on_quote)
            self.ws_client.set_error_callback(on_error)
            
            # IMPORTANT: Do NOT block authentication waiting for WS handshake.
            # AngelOneWebSocketClient.connect() can take multiple seconds (tries endpoints + waits).
            # Run connect asynchronously; bot will still start and can fall back to REST.
            def _connect_ws():
                try:
                    ok = self.ws_client.connect()
                    self.use_websocket = bool(ok)
                    if ok:
                        log.info("✅ WebSocket client connected (async)")
                    else:
                        log.warning("⚠️ WebSocket connection failed; will rely on REST/replay")
                except Exception as e:
                    self.use_websocket = False
                    log.warning(f"⚠️ WebSocket async connect crashed: {e}")

            self.use_websocket = False
            threading.Thread(target=_connect_ws, daemon=True).start()
            log.info("✅ WebSocket client initialization started (async)")
            
        except Exception as e:
            log.warning(f"⚠️ WebSocket setup failed: {e}")
            self.use_websocket = False
            log.info("💡 WebSocket disabled (will rely on REST quotes)")
    
    def get_quote(self, symbol: str, exchange: str = 'MCX') -> Optional[QuoteData]:
        """
        Get real-time quote for a symbol using SmartAPI.
        WARNING: This endpoint may not be available depending on SmartAPI plan.
        Returns mock data for demonstration if live API is unavailable.
        
        Args:
            symbol: Trading symbol (e.g., 'SILVER')
            exchange: Exchange (MCX, NSE, BSE)
        
        Returns:
            QuoteData object or None if error
        """
        try:
            if not self.is_authenticated:
                log.warning("Not authenticated. Authenticating...")
                if not self.authenticate():
                    return None
            
            # SmartAPI requires token refresh if expired
            if not self.is_token_valid():
                log.warning("Token expired, re-authenticating...")
                if not self.authenticate():
                    return None
            sym_key = str(symbol).strip()

            # Resolve numeric token if caller passed tradingsymbol.
            token_for_api = sym_key
            if not token_for_api.isdigit():
                if not self.smart_api:
                    self.authenticate()
                if self.smart_api:
                    try:
                        q = token_for_api[:16]
                        search = self.smart_api.searchScrip(exchange, q)
                        rows = search.get("data") or []
                        target = sym_key.upper()
                        for it in rows:
                            ts = str(it.get("tradingsymbol") or "").strip().upper()
                            if ts == target:
                                token_for_api = str(it.get("symboltoken") or "").strip()
                                break
                    except Exception as e:
                        log.debug(f"Token resolve failed for {sym_key}: {e}")

            if not token_for_api.isdigit():
                log.debug(f"No numeric token for quote symbol={sym_key}")
                return None

            if not self.smart_api:
                if not self.authenticate() or not self.smart_api:
                    return None

            # Reliable quote path: SmartConnect.getMarketData (uses proper SmartAPI headers).
            result = self.smart_api.getMarketData("LTP", {exchange: [token_for_api]})
            if not result.get("status"):
                msg = str(result.get("message") or result)
                if "invalid token" in msg.lower() or "ag8001" in msg.lower():
                    if self.authenticate(force_fresh=True) and self.smart_api:
                        result = self.smart_api.getMarketData("LTP", {exchange: [token_for_api]})
                if not result.get("status"):
                    log.warning(f"LTP quote failed for {token_for_api}: {result.get('message') or result}")
                    return None

            fetch_data = (result.get("data", {}).get("fetched") or [{}])[0] or {}
            divisor_raw = os.getenv("ANGEL_MCX_LTP_DIVISOR", "100")
            try:
                divisor = float(divisor_raw) if float(divisor_raw) > 0 else 100.0
            except Exception:
                divisor = 100.0

            def _p(v):
                try:
                    fv = float(v or 0)
                    return fv / divisor if fv else 0.0
                except Exception:
                    return 0.0

            quote = QuoteData(
                symbol=sym_key,
                exchange=exchange,
                ltp=_p(fetch_data.get('ltp') or fetch_data.get('lastTradedPrice')),
                volume=int(fetch_data.get('volume') or fetch_data.get('tradeVolume') or 0),
                bid=_p(fetch_data.get('bid')),
                ask=_p(fetch_data.get('ask')),
                open_price=_p(fetch_data.get('open')),
                high=_p(fetch_data.get('high')),
                low=_p(fetch_data.get('low')),
                close_price=_p(fetch_data.get('close')),
                timestamp=datetime.now().isoformat(),
                oi=int(fetch_data.get('oi') or fetch_data.get('openInterest') or 0)
            )
            if quote.ltp <= 0 and quote.close_price > 0:
                quote.ltp = quote.close_price
            if quote.ltp > 0:
                return quote
            
            # FALLBACK: Use historical data replay if both APIs unavailable
            # This provides realistic data from actual MCX futures history
            log.warning("⚠️  Angel One API unavailable - falling back to historical data replay")
            log.info("💡 Data from real MCX Silver futures (historical replay with intraday variation)")
            
            # Replay will be handled by RealTimeDataStream's fallback
            return None
                
        except Exception as e:
            log.warning(f"⚠️  Quote fetch failed: {e}")
            return None
    
    def get_market_depth(self, symbol: str, exchange: str = 'MCX') -> Optional[Dict]:
        """
        Get order book depth (bid-ask levels).
        
        Returns:
            Dict with bid/ask levels or None
        """
        try:
            if not self.is_authenticated:
                return None
            
            headers = {
                'Authorization': f'Bearer {self.auth_token}',
                'Content-Type': 'application/json',
                'X-UserType': 'USER',
                'X-SourceID': 'WEB'
            }
            
            payload = {
                'mode': 'MARKET_DEPTH',
                'exchangeTokens': {
                    exchange: {
                        symbol: ['all']
                    }
                }
            }
            
            response = self.session.post(
                f"{ANGEL_ONE_BASE_URL}/quote",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') and data.get('data'):
                    log.debug(f"📊 Market depth: {data['data']}")
                    return data['data']
            
            return None
            
        except Exception as e:
            log.error(f"Error fetching market depth: {e}")
            return None


class RealTimeDataStream:
    """Manage continuous real-time data stream."""
    
    def __init__(self, connector: AngelOneConnector):
        self.connector = connector
        self.last_quote = None
        self.quote_history = []
        self.max_history = 100
        
        # Optional historical replay fallback.
        # Disabled by default when `EXTERNAL_DATA_ONLY=true`.
        self.replay = None
        if not EXTERNAL_DATA_ONLY:
            try:
                from historical_data_replay import HistoricalDataReplay
                self.replay = HistoricalDataReplay('mcx_silver_futures_2025.csv')
                log.info("✅ Historical data replay initialized (for API fallback)")
            except Exception as e:
                log.debug(f"⚠️  Could not load historical replay: {e}")
    
    def fetch_latest(self, symbol: str, exchange: str = 'MCX') -> Optional[QuoteData]:
        """
        Fetch latest quote. 
        Priority: WebSocket → REST API → Historical data replay
        """
        sym_key = str(symbol or "").strip().upper()
        # When trading by exact futures contract or numeric token from the allocator,
        # prefer REST so we use the requested instrument instead of the websocket's
        # generic hardcoded SILVER subscription.
        prefer_rest_for_symbol = bool(sym_key.isdigit() or sym_key.endswith("FUT"))

        # Priority 1: Try WebSocket first only for generic family symbols.
        if not prefer_rest_for_symbol and self.connector.use_websocket and self.connector.ws_client:
            try:
                ws_quote = self.connector.ws_client.get_quote(f"{exchange}:{symbol}")
                if ws_quote:
                    # Convert WebSocket quote to QuoteData format
                    quote_data = QuoteData(
                        symbol=symbol,
                        exchange=exchange,
                        ltp=ws_quote.ltp,
                        volume=ws_quote.volume,
                        bid=ws_quote.bid if hasattr(ws_quote, 'bid') else ws_quote.ltp,
                        ask=ws_quote.ask if hasattr(ws_quote, 'ask') else ws_quote.ltp,
                        open_price=ws_quote.open if hasattr(ws_quote, 'open') else ws_quote.ltp,
                        high=ws_quote.high if hasattr(ws_quote, 'high') else ws_quote.ltp,
                        low=ws_quote.low if hasattr(ws_quote, 'low') else ws_quote.ltp,
                        close_price=ws_quote.close if hasattr(ws_quote, 'close') else ws_quote.ltp,
                        timestamp=ws_quote.timestamp if hasattr(ws_quote, 'timestamp') else datetime.now().isoformat(),
                        oi=ws_quote.oi if hasattr(ws_quote, 'oi') else 0
                    )
                    self.last_quote = quote_data
                    self.quote_history.append(asdict(quote_data))
                    if len(self.quote_history) > self.max_history:
                        self.quote_history.pop(0)
                    return quote_data
            except Exception as e:
                log.debug(f"WebSocket quote fetch failed: {e}")
        
        # Priority 2: Try REST API
        quote_data = self.connector.get_quote(symbol, exchange)
        
        if quote_data:
            self.last_quote = quote_data
            self.quote_history.append(asdict(quote_data))
            
            # Keep only recent history
            if len(self.quote_history) > self.max_history:
                self.quote_history.pop(0)
            
            return quote_data
        
        # Priority 3: Optional fallback to historical replay if both APIs fail
        if self.replay:
            replay_quote = self.replay.get_next_quote()
            if replay_quote:
                # Convert replay quote to QuoteData format
                quote_data = QuoteData(
                    symbol=symbol,
                    exchange=exchange,
                    ltp=replay_quote.ltp,
                    volume=replay_quote.volume,
                    bid=replay_quote.bid,
                    ask=replay_quote.ask,
                    open_price=replay_quote.open_price,
                    high=replay_quote.high,
                    low=replay_quote.low,
                    close_price=replay_quote.close_price,
                    timestamp=replay_quote.timestamp,
                    oi=replay_quote.oi
                )
                
                self.last_quote = quote_data
                self.quote_history.append(asdict(quote_data))
                
                if len(self.quote_history) > self.max_history:
                    self.quote_history.pop(0)
                
                return quote_data
        
        return None
    
    def get_price_change(self) -> Tuple[float, float]:
        """Calculate price change from last close."""
        if not self.last_quote:
            return 0.0, 0.0
        
        change = self.last_quote.ltp - self.last_quote.close_price
        change_pct = (change / self.last_quote.close_price * 100) if self.last_quote.close_price else 0
        
        return change, change_pct
    
    def export_history(self, filepath: str = 'price_history.json'):
        """Export quote history to JSON."""
        with open(filepath, 'w') as f:
            json.dump(self.quote_history, f, indent=2)
        log.info(f"Price history exported to {filepath}")


# ── Example Usage ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Load credentials from environment
    from dotenv import load_dotenv
    load_dotenv()
    
    client_id = os.getenv('ANGEL_ONE_CLIENT_ID')
    client_secret = os.getenv('ANGEL_ONE_CLIENT_SECRET')
    api_key = os.getenv('ANGEL_ONE_API_KEY')
    totp = os.getenv('ANGEL_ONE_TOTP_SECRET')
    password = os.getenv('ANGEL_ONE_PASSWORD')
    user_id = os.getenv('ANGEL_ONE_USER_ID')
    
    if not all([client_id, client_secret, api_key, totp, password, user_id]):
        log.error("❌ Missing Angel One credentials. Add to .env file")
        exit(1)
    
    # Initialize connector
    connector = AngelOneConnector(client_id, client_secret, api_key, totp, password, user_id)
    
    # Authenticate
    if connector.authenticate():
        # Create data stream
        stream = RealTimeDataStream(connector)
        
        # Fetch real-time data
        log.info("\n📊 Fetching real-time SILVER futures data...")
        for i in range(3):
            quote = stream.fetch_latest('SILVER', 'MCX')
            if quote:
                change, change_pct = stream.get_price_change()
                log.info(f"\n{quote}")
                log.info(f"Change from close: {change:+.2f} ({change_pct:+.3f}%)")
            
            if i < 2:
                time_module.sleep(2)
    else:
        log.error("❌ Failed to authenticate with Angel One")
