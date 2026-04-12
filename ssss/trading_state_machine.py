"""
Trading State Machine
Based on the user's V1 design: single-position, event-driven, deterministic.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

log = logging.getLogger("trading_sm")


class TradeState(str, Enum):
    IDLE = "IDLE"
    ENTRY_PENDING = "ENTRY_PENDING"
    IN_POSITION = "IN_POSITION"
    EXIT_PENDING = "EXIT_PENDING"
    CLOSED = "CLOSED"
    BLOCKED = "BLOCKED"


class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class EventType(str, Enum):
    LLM_ENTRY_SIGNAL = "LLM_ENTRY_SIGNAL"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    LLM_EXIT_SIGNAL = "LLM_EXIT_SIGNAL"
    STOPLOSS_HIT = "STOPLOSS_HIT"
    TIMEOUT = "TIMEOUT"
    RISK_BREACH = "RISK_BREACH"
    COOLDOWN_COMPLETE = "COOLDOWN_COMPLETE"
    MANUAL_RESET = "MANUAL_RESET"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"


@dataclass
class Trade:
    contract: str
    lot_size: float
    stop_loss: float
    target: float
    direction: TradeDirection
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TradeState = TradeState.IDLE
    entry_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    notes: list[str] = field(default_factory=list)

    def log_note(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self.notes.append(f"[{ts}] {msg}")
        log.info("[%s] %s", self.id[:8], msg)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "contract": self.contract,
            "lot_size": self.lot_size,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "direction": self.direction.value,
            "status": self.status.value,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "notes": list(self.notes),
        }


class TradingStateMachine:
    """Single-position state machine with sync dispatch."""

    def __init__(self, entry_pending_timeout_secs: int = 5, cooldown_secs: int = 120):
        self.ENTRY_PENDING_TIMEOUT_SECS = int(entry_pending_timeout_secs)
        self.COOLDOWN_SECS = int(cooldown_secs)
        self.state: TradeState = TradeState.IDLE
        self.current_trade: Optional[Trade] = None
        self.trade_history: list[Trade] = []
        self.block_reason: Optional[str] = None
        self.entry_pending_since: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _set_state(self, new_state: TradeState, reason: str = "") -> None:
        old = self.state
        self.state = new_state
        msg = f"STATE: {old.value} -> {new_state.value}" + (f" | {reason}" if reason else "")
        log.info(msg)
        if self.current_trade:
            self.current_trade.log_note(msg)

    def _archive_trade(self, reason: str) -> None:
        if self.current_trade:
            self.current_trade.log_note(f"Archived | reason={reason}")
            self.trade_history.append(self.current_trade)

    def _start_cooldown(self) -> None:
        self.cooldown_until = self._now() + timedelta(seconds=self.COOLDOWN_SECS)

    def _clear_timers(self) -> None:
        self.entry_pending_since = None
        self.cooldown_until = None

    def process_time_events(self) -> None:
        now = self._now()
        if (
            self.state == TradeState.ENTRY_PENDING
            and self.entry_pending_since is not None
            and (now - self.entry_pending_since).total_seconds() >= self.ENTRY_PENDING_TIMEOUT_SECS
        ):
            self.handle_event(EventType.TIMEOUT, {})
        if (
            self.state == TradeState.CLOSED
            and self.cooldown_until is not None
            and now >= self.cooldown_until
        ):
            self.handle_event(EventType.COOLDOWN_COMPLETE, {})

    def handle_event(self, event: EventType, payload: Optional[dict] = None) -> dict:
        payload = payload or {}
        log.info("EVENT: %s | STATE: %s | payload=%s", event.value, self.state.value, payload)

        if event == EventType.RISK_BREACH:
            reason = payload.get("reason", "unknown_risk_breach")
            self.block_reason = reason
            self._set_state(TradeState.BLOCKED, reason)
            return {"status": "blocked", "reason": reason}

        if event == EventType.EMERGENCY_EXIT:
            reason = payload.get("reason", "emergency")
            if self.current_trade and self.state in (
                TradeState.IN_POSITION,
                TradeState.EXIT_PENDING,
                TradeState.ENTRY_PENDING,
            ):
                px = float(payload.get("exit_price") or self.current_trade.stop_loss)
                self._close_trade(px, "EMERGENCY_EXIT")
            self.block_reason = reason
            self._set_state(TradeState.BLOCKED, f"Emergency exit: {reason}")
            return {"status": "blocked", "reason": reason}

        if event == EventType.MANUAL_RESET:
            if self.state != TradeState.BLOCKED:
                return {"status": "not_blocked", "state": self.state.value}
            self.block_reason = None
            self.current_trade = None
            self._clear_timers()
            self._set_state(TradeState.IDLE, "Manual reset")
            return {"status": "reset_ok", "state": self.state.value}

        if self.state == TradeState.IDLE:
            return self._handle_idle(event, payload)
        if self.state == TradeState.ENTRY_PENDING:
            return self._handle_entry_pending(event, payload)
        if self.state == TradeState.IN_POSITION:
            return self._handle_in_position(event, payload)
        if self.state == TradeState.EXIT_PENDING:
            return self._handle_exit_pending(event, payload)
        if self.state == TradeState.CLOSED:
            return self._handle_closed(event, payload)
        return {"status": "blocked", "reason": self.block_reason}

    def _handle_idle(self, event: EventType, payload: dict) -> dict:
        if event != EventType.LLM_ENTRY_SIGNAL:
            return {"status": "ignored", "reason": f"Event {event.value} not valid in IDLE"}
        required = {"contract", "lot_size", "stop_loss", "target", "direction"}
        missing = required - payload.keys()
        if missing:
            return {"status": "rejected", "reason": f"Missing fields: {sorted(missing)}"}
        self.current_trade = Trade(
            contract=payload["contract"],
            lot_size=float(payload["lot_size"]),
            stop_loss=float(payload["stop_loss"]),
            target=float(payload["target"]),
            direction=TradeDirection(str(payload["direction"]).upper()),
        )
        self.current_trade.status = TradeState.ENTRY_PENDING
        self.entry_pending_since = self._now()
        self._set_state(TradeState.ENTRY_PENDING, "Entry signal accepted")
        self.current_trade.log_note("Entry order submitted")
        return {"status": "accepted", "trade_id": self.current_trade.id, "state": self.state.value}

    def _handle_entry_pending(self, event: EventType, payload: dict) -> dict:
        if event == EventType.ORDER_FILLED:
            fill_price = float(payload.get("fill_price") or 0)
            self.entry_pending_since = None
            if self.current_trade:
                self.current_trade.entry_price = fill_price
                self.current_trade.entry_time = self._now()
                self.current_trade.status = TradeState.IN_POSITION
                self.current_trade.log_note(f"Entry filled @ {fill_price}")
            self._set_state(TradeState.IN_POSITION, f"Filled @ {fill_price}")
            return {"status": "in_position", "trade_id": self.current_trade.id if self.current_trade else None}
        if event == EventType.ORDER_REJECTED:
            reason = payload.get("reason", "unknown")
            if self.current_trade:
                self.current_trade.log_note(f"Entry rejected: {reason}")
                self.current_trade.status = TradeState.CLOSED
                self._archive_trade("ENTRY_REJECTED")
            self.current_trade = None
            self.entry_pending_since = None
            self._set_state(TradeState.IDLE, "Order rejected")
            return {"status": "rejected", "reason": reason}
        if event == EventType.TIMEOUT:
            if self.current_trade:
                self.current_trade.log_note("Entry timed out")
                self.current_trade.status = TradeState.CLOSED
                self._archive_trade("ENTRY_TIMEOUT")
            self.current_trade = None
            self.entry_pending_since = None
            self._set_state(TradeState.IDLE, "Entry timeout")
            return {"status": "timeout"}
        if event == EventType.LLM_ENTRY_SIGNAL:
            return {"status": "ignored", "reason": "Duplicate entry"}
        return {"status": "ignored", "reason": f"Event {event.value} not valid in ENTRY_PENDING"}

    def _handle_in_position(self, event: EventType, payload: dict) -> dict:
        if event == EventType.STOPLOSS_HIT:
            sl_price = float(payload.get("sl_price") or (self.current_trade.stop_loss if self.current_trade else 0))
            self._close_trade(sl_price, "SL_HIT")
            self._set_state(TradeState.CLOSED, "Stoploss hit")
            self._start_cooldown()
            return {"status": "closed", "reason": "stoploss_hit"}
        if event == EventType.LLM_EXIT_SIGNAL:
            reason = payload.get("reason", "EXIT_SIGNAL")
            self._set_state(TradeState.EXIT_PENDING, reason)
            return {"status": "exit_pending"}
        if event == EventType.LLM_ENTRY_SIGNAL:
            return {"status": "ignored", "reason": "Duplicate entry"}
        return {"status": "ignored", "reason": f"Event {event.value} not valid in IN_POSITION"}

    def _handle_exit_pending(self, event: EventType, payload: dict) -> dict:
        if event == EventType.ORDER_FILLED:
            fill_price = float(payload.get("fill_price") or 0)
            self._close_trade(fill_price, "EXIT_FILLED")
            self._set_state(TradeState.CLOSED, f"Exit filled @ {fill_price}")
            self._start_cooldown()
            return {"status": "closed", "pnl": self.current_trade.pnl if self.current_trade else None}
        if event == EventType.ORDER_REJECTED:
            reason = payload.get("reason", "unknown")
            return self.handle_event(EventType.EMERGENCY_EXIT, {"reason": f"Exit rejection: {reason}"})
        if event == EventType.STOPLOSS_HIT:
            sl_price = float(payload.get("sl_price") or (self.current_trade.stop_loss if self.current_trade else 0))
            self._close_trade(sl_price, "SL_HIT_DURING_EXIT")
            self._set_state(TradeState.CLOSED, "SL hit during exit")
            self._start_cooldown()
            return {"status": "closed", "reason": "sl_hit_during_exit"}
        return {"status": "ignored", "reason": f"Event {event.value} not valid in EXIT_PENDING"}

    def _handle_closed(self, event: EventType, payload: dict) -> dict:
        if event == EventType.COOLDOWN_COMPLETE:
            self.current_trade = None
            self.cooldown_until = None
            self._set_state(TradeState.IDLE, "Cooldown done")
            return {"status": "idle_ready"}
        return {
            "status": "in_cooldown",
            "remaining_secs": max(
                0,
                int((self.cooldown_until - self._now()).total_seconds()) if self.cooldown_until else self.COOLDOWN_SECS,
            ),
        }

    def _close_trade(self, exit_price: float, reason: str) -> None:
        if not self.current_trade:
            return
        t = self.current_trade
        t.exit_price = float(exit_price)
        t.exit_time = self._now()
        t.status = TradeState.CLOSED
        multiplier = 1 if t.direction == TradeDirection.LONG else -1
        base_entry = float(t.entry_price or t.exit_price)
        t.pnl = round((t.exit_price - base_entry) * float(t.lot_size) * multiplier, 2)
        t.log_note(f"Trade closed | reason={reason} | PnL={t.pnl}")
        self._archive_trade(reason)

    def snapshot(self) -> dict:
        remaining = None
        if self.cooldown_until is not None:
            remaining = max(0, int((self.cooldown_until - self._now()).total_seconds()))
        return {
            "state": self.state.value,
            "block_reason": self.block_reason,
            "current_trade": self.current_trade.to_dict() if self.current_trade else None,
            "history_count": len(self.trade_history),
            "cooldown_remaining_secs": remaining,
        }
