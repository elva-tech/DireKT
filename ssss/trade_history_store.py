"""
Persist trade OPEN/CLOSED events for the History UI.

- Local: append to TRADE_HISTORY_FILE (JSONL), same as before.
- Render / cloud: set DATABASE_URL → rows stored in PostgreSQL (survives restarts).
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
_jsonl_lock = Lock()

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[misc, assignment]
    dict_row = None  # type: ignore[misc, assignment]
    Json = None  # type: ignore[misc, assignment]


def _postgres_dsn() -> str:
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return ""
    if raw.startswith("postgres://"):
        return "postgresql://" + raw[len("postgres://") :]
    return raw


def use_postgres() -> bool:
    return bool(_postgres_dsn()) and psycopg is not None and Json is not None


def _jsonl_path() -> str:
    return (os.getenv("TRADE_HISTORY_FILE") or "trade_history.jsonl").strip()


def _owner_key_from_row(row: Dict[str, Any]) -> str:
    uid = (str(row.get("user_id") or "")).strip()
    uname = (str(row.get("username") or "")).strip().lower()
    return uid or uname


def _ensure_table_pg(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_history_events (
                id BIGSERIAL PRIMARY KEY,
                owner_key TEXT NOT NULL,
                event_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trade_history_owner_id
            ON trade_history_events (owner_key, id DESC)
            """
        )


def persist_trade_event(position_snapshot: dict, lifecycle: str, decision_engine: str) -> None:
    """Append one lifecycle event (same contract as trading_bot._persist_trade_history_event)."""
    snap = deepcopy(position_snapshot)
    snap["lifecycle"] = lifecycle
    snap["decision_engine"] = decision_engine

    if use_postgres():
        owner_key = _owner_key_from_row(snap)
        if not owner_key:
            logger.warning("trade_history_store: skip persist — event has no user_id/username")
            return
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn) as conn:
                _ensure_table_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO trade_history_events (owner_key, event_json) VALUES (%s, %s)",
                        (owner_key, Json(snap)),
                    )
            return
        except Exception as e:
            logger.warning("trade_history_store: Postgres persist failed, falling back to JSONL: %s", e)

    path = _jsonl_path()
    if not path:
        return
    try:
        line = json.dumps(snap, default=str)
        with _jsonl_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        logger.warning("trade_history_store: JSONL persist failed: %s", e)


def _read_events_jsonl(
    owner_key: str,
    limit: int,
    lifecycle: Optional[str] = None,
) -> List[Dict[str, Any]]:
    path = _jsonl_path()
    out: List[Dict[str, Any]] = []
    if not path or not os.path.isfile(path):
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _owner_key_from_row(row) != owner_key:
                    continue
                if lifecycle and str(row.get("lifecycle") or "").upper() != lifecycle.upper():
                    continue
                out.append(row)
    except OSError:
        pass
    if len(out) > limit:
        out = out[-limit:]
    return out


def _read_events_postgres(
    owner_key: str,
    limit: int,
    lifecycle: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not use_postgres():
        return []
    dsn = _postgres_dsn()
    if lifecycle:
        sql = """
            SELECT event_json FROM trade_history_events
            WHERE owner_key = %s AND upper(event_json->>'lifecycle') = upper(%s)
            ORDER BY id DESC
            LIMIT %s
        """
        params = (owner_key, lifecycle, limit)
    else:
        sql = """
            SELECT event_json FROM trade_history_events
            WHERE owner_key = %s
            ORDER BY id DESC
            LIMIT %s
        """
        params = (owner_key, limit)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        _ensure_table_pg(conn)
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            fetched = cur.fetchall()
    # restore chronological order (oldest first within window)
    events: List[Dict[str, Any]] = []
    for r in reversed(fetched):
        ej = r.get("event_json")
        if isinstance(ej, dict):
            events.append(ej)
        else:
            try:
                events.append(json.loads(ej))
            except (TypeError, json.JSONDecodeError):
                continue
    return events


def fetch_persisted_events(
    owner_key: str,
    limit: int,
    lifecycle: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Events for History / performance APIs. Matches previous JSONL semantics (last N for owner).
    """
    if use_postgres():
        return _read_events_postgres(owner_key, limit, lifecycle=lifecycle)
    return _read_events_jsonl(owner_key, limit, lifecycle=lifecycle)
