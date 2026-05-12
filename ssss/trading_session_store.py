"""
Persistent trading bot sessions (survives logout, browser close, process restart).

- With DATABASE_URL: Postgres tables trading_bot_sessions, trading_activity_log, order_execution_events.
- Without DB: JSON file TRADING_SESSIONS_FILE (default trading_sessions_store.json).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
_file_lock = threading.Lock()

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


def _sessions_file() -> str:
    return (os.getenv("TRADING_SESSIONS_FILE") or "trading_sessions_store.json").strip()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_tables_pg(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_bot_sessions (
                owner_key TEXT NOT NULL,
                username TEXT,
                strategy TEXT NOT NULL,
                desired_state TEXT NOT NULL DEFAULT 'stopped',
                config JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (owner_key, strategy)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_activity_log (
                id BIGSERIAL PRIMARY KEY,
                owner_key TEXT NOT NULL,
                strategy TEXT,
                level TEXT NOT NULL DEFAULT 'INFO',
                message TEXT NOT NULL,
                payload JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trading_activity_owner
            ON trading_activity_log (owner_key, id DESC)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS order_execution_events (
                id BIGSERIAL PRIMARY KEY,
                owner_key TEXT NOT NULL,
                strategy TEXT NOT NULL,
                action TEXT NOT NULL,
                details JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_order_exec_owner
            ON order_execution_events (owner_key, id DESC)
            """
        )


def log_activity(
    owner_key: str,
    message: str,
    strategy: Optional[str] = None,
    level: str = "INFO",
    payload: Optional[dict] = None,
) -> None:
    if not owner_key:
        return
    if use_postgres():
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn) as conn:
                _ensure_tables_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO trading_activity_log (owner_key, strategy, level, message, payload)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (owner_key, strategy, level, message, Json(payload or {})),
                    )
            return
        except Exception as e:
            logger.warning("trading_session_store: activity log PG failed: %s", e)
    # file fallback: append to nested structure (trim to last 500)
    try:
        path = _sessions_file()
        with _file_lock:
            data = _read_file_store(path)
            logs = data.setdefault("activity", [])
            logs.append(
                {
                    "owner_key": owner_key,
                    "strategy": strategy,
                    "level": level,
                    "message": message,
                    "payload": payload or {},
                    "created_at": _iso_now(),
                }
            )
            data["activity"] = logs[-500:]
            _write_file_store(path, data)
    except Exception as e:
        logger.warning("trading_session_store: activity log file failed: %s", e)


def log_order_execution(owner_key: str, strategy: str, action: str, details: Optional[dict] = None) -> None:
    if not owner_key or not strategy:
        return
    if use_postgres():
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn) as conn:
                _ensure_tables_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO order_execution_events (owner_key, strategy, action, details)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (owner_key, strategy, action, Json(details or {})),
                    )
            return
        except Exception as e:
            logger.warning("trading_session_store: order_exec PG failed: %s", e)
    try:
        path = _sessions_file()
        with _file_lock:
            data = _read_file_store(path)
            ev = data.setdefault("order_executions", [])
            ev.append(
                {
                    "owner_key": owner_key,
                    "strategy": strategy,
                    "action": action,
                    "details": details or {},
                    "created_at": _iso_now(),
                }
            )
            data["order_executions"] = ev[-2000:]
            _write_file_store(path, data)
    except Exception as e:
        logger.warning("trading_session_store: order_exec file failed: %s", e)


def _read_file_store(path: str) -> dict:
    if not path or not os.path.isfile(path):
        return {"sessions": {}, "activity": [], "order_executions": []}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"sessions": {}, "activity": [], "order_executions": []}


def _write_file_store(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0, default=str)
    os.replace(tmp, path)


def upsert_session_running(
    owner_key: str,
    username: Optional[str],
    strategy: str,
    config: Dict[str, Any],
) -> None:
    """Mark session as running and persist parameters needed for resume after deploy."""
    cfg = deepcopy(config or {})
    cfg["saved_at"] = _iso_now()
    if use_postgres():
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn) as conn:
                _ensure_tables_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO trading_bot_sessions (owner_key, username, strategy, desired_state, config, updated_at)
                        VALUES (%s, %s, %s, 'running', %s, NOW())
                        ON CONFLICT (owner_key, strategy) DO UPDATE SET
                            username = EXCLUDED.username,
                            desired_state = 'running',
                            config = EXCLUDED.config,
                            updated_at = NOW()
                        """,
                        (owner_key, username or None, strategy, Json(cfg)),
                    )
            return
        except Exception as e:
            logger.warning("trading_session_store: upsert running PG failed: %s", e)
    try:
        path = _sessions_file()
        with _file_lock:
            data = _read_file_store(path)
            sess = data.setdefault("sessions", {})
            sk = f"{owner_key}|{strategy}"
            sess[sk] = {
                "owner_key": owner_key,
                "username": username,
                "strategy": strategy,
                "desired_state": "running",
                "config": cfg,
                "updated_at": _iso_now(),
            }
            _write_file_store(path, data)
    except Exception as e:
        logger.warning("trading_session_store: upsert running file failed: %s", e)


def upsert_session_stopped(owner_key: str, username: Optional[str], strategy: str) -> None:
    if use_postgres():
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn) as conn:
                _ensure_tables_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO trading_bot_sessions (owner_key, username, strategy, desired_state, config, updated_at)
                        VALUES (%s, %s, %s, 'stopped', '{}'::jsonb, NOW())
                        ON CONFLICT (owner_key, strategy) DO UPDATE SET
                            username = COALESCE(EXCLUDED.username, trading_bot_sessions.username),
                            desired_state = 'stopped',
                            config = '{}'::jsonb,
                            updated_at = NOW()
                        """,
                        (owner_key, username or None, strategy),
                    )
            return
        except Exception as e:
            logger.warning("trading_session_store: upsert stopped PG failed: %s", e)
    try:
        path = _sessions_file()
        with _file_lock:
            data = _read_file_store(path)
            sess = data.setdefault("sessions", {})
            sk = f"{owner_key}|{strategy}"
            sess[sk] = {
                "owner_key": owner_key,
                "username": username,
                "strategy": strategy,
                "desired_state": "stopped",
                "config": {},
                "updated_at": _iso_now(),
            }
            _write_file_store(path, data)
    except Exception as e:
        logger.warning("trading_session_store: upsert stopped file failed: %s", e)


def fetch_session(owner_key: str, strategy: str) -> Optional[Dict[str, Any]]:
    if not owner_key or not strategy:
        return None
    if use_postgres():
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                _ensure_tables_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT owner_key, username, strategy, desired_state, config, updated_at
                        FROM trading_bot_sessions
                        WHERE owner_key = %s AND strategy = %s
                        """,
                        (owner_key, strategy),
                    )
                    row = cur.fetchone()
            if not row:
                return None
            cfg = row.get("config")
            if isinstance(cfg, str):
                try:
                    cfg = json.loads(cfg)
                except json.JSONDecodeError:
                    cfg = {}
            return {
                "owner_key": row["owner_key"],
                "username": row.get("username"),
                "strategy": row["strategy"],
                "desired_state": row["desired_state"],
                "config": cfg if isinstance(cfg, dict) else {},
                "updated_at": str(row.get("updated_at") or ""),
            }
        except Exception as e:
            logger.warning("trading_session_store: fetch_session PG failed: %s", e)
            return None
    path = _sessions_file()
    with _file_lock:
        data = _read_file_store(path)
        sk = f"{owner_key}|{strategy}"
        row = (data.get("sessions") or {}).get(sk)
    return deepcopy(row) if row else None


def fetch_sessions_for_owner(owner_key: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for s in ("ml", "llm", "hybrid"):
        row = fetch_session(owner_key, s)
        if row:
            out[s] = row
    return out


def fetch_all_running_sessions() -> List[Dict[str, Any]]:
    """Rows with desired_state=running for startup resume."""
    if use_postgres():
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                _ensure_tables_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT owner_key, username, strategy, desired_state, config, updated_at
                        FROM trading_bot_sessions
                        WHERE desired_state = 'running'
                        """
                    )
                    rows = cur.fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows or []:
                cfg = row.get("config")
                if isinstance(cfg, str):
                    try:
                        cfg = json.loads(cfg)
                    except json.JSONDecodeError:
                        cfg = {}
                out.append(
                    {
                        "owner_key": row["owner_key"],
                        "username": row.get("username"),
                        "strategy": row["strategy"],
                        "desired_state": row["desired_state"],
                        "config": cfg if isinstance(cfg, dict) else {},
                        "updated_at": str(row.get("updated_at") or ""),
                    }
                )
            return out
        except Exception as e:
            logger.warning("trading_session_store: fetch_all_running PG failed: %s", e)
            return []
    path = _sessions_file()
    with _file_lock:
        data = _read_file_store(path)
        sess = data.get("sessions") or {}
    out = []
    for row in sess.values():
        if isinstance(row, dict) and row.get("desired_state") == "running":
            out.append(deepcopy(row))
    return out


def fetch_order_executions(owner_key: str, limit: int = 200) -> List[Dict[str, Any]]:
    if not owner_key:
        return []
    if use_postgres():
        try:
            dsn = _postgres_dsn()
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                _ensure_tables_pg(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT strategy, action, details, created_at
                        FROM order_execution_events
                        WHERE owner_key = %s
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (owner_key, limit),
                    )
                    rows = cur.fetchall()
            rev = list(reversed(rows or []))
            return [dict(r) for r in rev]
        except Exception as e:
            logger.warning("trading_session_store: fetch_order_exec PG failed: %s", e)
            return []
    with _file_lock:
        data = _read_file_store(_sessions_file())
    ev = [e for e in (data.get("order_executions") or []) if e.get("owner_key") == owner_key]
    return ev[-limit:]
