"""
Angel One Smart WebSocket v2 — MCX tick streaming (Colab / Silver v3 pattern).

Uses the official SmartApi.SmartWebSocketV2 binary stream (same as your Colab script):
  - exchangeType 5 = MCX_FO
  - mode 1 = LTP (lightest), 2 = QUOTE, 3 = SNAP_QUOTE (richest; matches many Colab samples)

This path is ideal for **high-frequency ticks** without hammering the REST quote API (helps rate limits).

Env (same as the rest of this repo):
  ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_ID, ANGEL_ONE_PASSWORD, ANGEL_ONE_TOTP_SECRET
Optional:
  LIVE_QUOTE_TRADINGSYMBOL (default SILVER05MAY26FUT)
  ANGEL_WS_SUBSCRIBE_MODE — 1 | 2 | 3 (default 3)
  ANGEL_WS_LTP_DIVISOR — default 100 (paise → ₹; set 1 if your stream already looks like rupees)

Run:
  python angel_v2_tick_stream.py
"""

from __future__ import annotations

import os
import sys
import time
import threading
from typing import Any, Callable, Dict, List, Optional

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

load_dotenv()

try:
    from smart_allocator_external import resolve_token_for_tradingsymbol, angel_search_scrip
except ImportError:
    resolve_token_for_tradingsymbol = None  # type: ignore

    def angel_search_scrip(obj: SmartConnect, exchange: str, q: str) -> dict:
        return obj.searchScrip(exchange, q)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def _login_smartapi() -> tuple:
    api_key = os.getenv("ANGEL_ONE_API_KEY", "").strip()
    client_id = os.getenv("ANGEL_ONE_CLIENT_ID", "").strip()
    password = os.getenv("ANGEL_ONE_PASSWORD", "").strip()
    totp_secret = os.getenv("ANGEL_ONE_TOTP_SECRET", "").strip()
    if not all([api_key, client_id, password, totp_secret]):
        raise RuntimeError(
            "Set ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_ID, ANGEL_ONE_PASSWORD, ANGEL_ONE_TOTP_SECRET"
        )
    obj = SmartConnect(api_key=api_key)
    totp = pyotp.TOTP(totp_secret).now()
    sess = obj.generateSession(client_id, password, totp)
    if not sess.get("status"):
        raise RuntimeError(sess.get("message", "Angel login failed"))
    jwt = sess["data"]["jwtToken"]
    feed = sess["data"].get("feedToken") or obj.getfeedToken()
    return obj, jwt, str(feed or ""), client_id


def _scrip_ts(it: dict) -> str:
    return str(it.get("tradingsymbol") or it.get("tradingSymbol") or "").strip()


def _scrip_tok(it: dict) -> str:
    v = it.get("symboltoken") or it.get("symbolToken")
    return str(v).strip() if v is not None else ""


def _resolve_mcx_token_with_obj(obj: SmartConnect, sym: str) -> str:
    """One login session: search MCX until exact tradingsymbol match."""
    keys: List[str] = []
    for q in (
        sym,
        sym.replace("FUT", "").strip()[:16],
        sym[:8],
        "SILVER",
    ):
        if q and q not in keys:
            keys.append(q)
    last_err: object = None
    for q in keys:
        try:
            search = angel_search_scrip(obj, "MCX", q)
        except Exception as e:
            last_err = e
            continue
        if not search.get("status"):
            last_err = search.get("message")
            continue
        for it in search.get("data") or []:
            if _scrip_ts(it).upper() == sym:
                tok = _scrip_tok(it)
                if tok:
                    return tok
    raise RuntimeError(f"Could not resolve token for {sym!r} (last: {last_err})")


def resolve_mcx_fut_token(tradingsymbol: str, obj: Optional[SmartConnect] = None) -> str:
    """Numeric Angel token for MCX futures symbol."""
    sym = (tradingsymbol or "").strip().upper()
    if not sym:
        raise ValueError("tradingsymbol required")
    if obj is not None:
        return _resolve_mcx_token_with_obj(obj, sym)
    if resolve_token_for_tradingsymbol:
        tok, _ = resolve_token_for_tradingsymbol(sym)
        return str(tok).strip()
    obj2, _, _, _ = _login_smartapi()
    return _resolve_mcx_token_with_obj(obj2, sym)


def normalize_ltp_from_v2_tick(tick: Dict[str, Any]) -> float:
    """
    Colab divides last_traded_price by 100 (paise → rupees). Same default here.
    OHLC fields in SNAP_QUOTE are also typically in paise — use same divisor when present.
    """
    raw = tick.get("last_traded_price")
    if raw is None:
        return 0.0
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.0
    div = float(_env_int("ANGEL_WS_LTP_DIVISOR", 100))
    if div <= 0:
        div = 100.0
    return v / div


class AngelV2TickStream:
    """
    Thin wrapper: connect, subscribe one MCX token, forward parsed tick dicts to on_tick.
    """

    def __init__(
        self,
        jwt: str,
        api_key: str,
        client_code: str,
        feed_token: str,
        mcx_token: str,
        *,
        mode: int = 3,
        on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self._jwt = jwt
        self._api_key = api_key
        self._client_code = client_code
        self._feed_token = feed_token
        self._mcx_token = str(mcx_token).strip()
        self._mode = mode
        self._on_tick = on_tick
        self._sws: Optional[SmartWebSocketV2] = None
        self._thread: Optional[threading.Thread] = None

    def _on_open(self, wsapp) -> None:
        token_list: List[Dict[str, Any]] = [{"exchangeType": SmartWebSocketV2.MCX_FO, "tokens": [self._mcx_token]}]
        self._sws.subscribe(correlation_id="mcxsilver", mode=self._mode, token_list=token_list)

    def _on_data(self, wsapp, tick: Dict[str, Any]) -> None:
        if self._on_tick and isinstance(tick, dict) and tick.get("subscription_mode", -1) > 0:
            self._on_tick(tick)

    def _on_error(self, wsapp, error) -> None:
        print(f"[Angel V2 WS] error: {error}", file=sys.stderr, flush=True)

    def _on_close(self, wsapp) -> None:
        print("[Angel V2 WS] closed", flush=True)

    def start_background(self) -> None:
        self._sws = SmartWebSocketV2(
            self._jwt,
            self._api_key,
            self._client_code,
            self._feed_token,
            max_retry_attempt=2,
            retry_strategy=0,
            retry_delay=10,
            retry_duration=30,
        )
        self._sws.on_open = self._on_open
        self._sws.on_data = self._on_data
        self._sws.on_error = self._on_error
        self._sws.on_close = self._on_close

        def _run():
            self._sws.connect()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def close(self) -> None:
        if self._sws:
            try:
                self._sws.close_connection()
            except Exception:
                pass


def main() -> None:
    sym = (os.getenv("LIVE_QUOTE_TRADINGSYMBOL") or "SILVER05MAY26FUT").strip().upper()
    mode = _env_int("ANGEL_WS_SUBSCRIBE_MODE", 3)
    if mode not in (1, 2, 3):
        mode = 3

    print(f"Login + resolve {sym!r}…", flush=True)
    obj, jwt, feed, client_id = _login_smartapi()
    tok = resolve_mcx_fut_token(sym, obj=obj)
    print(f"Token {tok} | WS mode {mode} (1=LTP 2=QUOTE 3=SNAP)", flush=True)

    ticks = []

    def on_tick(t: Dict[str, Any]) -> None:
        ltp = normalize_ltp_from_v2_tick(t)
        ticks.append(ltp)
        token = t.get("token", "")
        print(f"\rLTP ₹{ltp:,.2f} | token={token}", end="", flush=True)

    stream = AngelV2TickStream(jwt, obj.api_key, client_id, feed, tok, mode=mode, on_tick=on_tick)
    stream.start_background()
    time.sleep(25)
    stream.close()
    print(f"\nReceived ~{len(ticks)} tick packets (same feed family as your Colab script).", flush=True)


if __name__ == "__main__":
    main()
