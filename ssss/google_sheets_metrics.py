"""
Google Sheets metrics logger for closed trades.
"""

import os
from typing import Dict, Optional


def _env_clean(name: str, default: str = "") -> str:
    raw = os.getenv(name, default)
    if raw is None:
        return default
    return str(raw).split("#", 1)[0].strip()


def _build_values(payload: Dict) -> list:
    return [
        str(payload.get("engine") or "").lower(),
        float(payload.get("winrate") or 0.0),
        float(payload.get("profit") or 0.0),
        float(payload.get("loss") or 0.0),
        float(payload.get("entry_price") or 0.0),
        float(payload.get("exit_price") or 0.0),
        str(payload.get("reasons") or ""),
        str(payload.get("trade_id") or ""),
        str(payload.get("execution_time") or ""),
    ]


def _target_for_engine(engine: str) -> tuple[str, str]:
    eng = str(engine or "").strip().lower()
    base_id = _env_clean("GOOGLE_SHEETS_SPREADSHEET_ID", "1LrofUJ-vAQm9rAdikkAM4nykHnxg8GBks1K24-6P7uc")
    base_tab = _env_clean("GOOGLE_SHEETS_TAB_NAME", "Sheet1")
    if eng == "ml":
        return (
            _env_clean("GOOGLE_SHEETS_SPREADSHEET_ID_ML", base_id),
            _env_clean("GOOGLE_SHEETS_TAB_NAME_ML", base_tab),
        )
    if eng == "llm":
        return (
            _env_clean("GOOGLE_SHEETS_SPREADSHEET_ID_LLM", base_id),
            _env_clean("GOOGLE_SHEETS_TAB_NAME_LLM", base_tab),
        )
    if eng == "hybrid":
        return (
            _env_clean("GOOGLE_SHEETS_SPREADSHEET_ID_HYBRID", base_id),
            _env_clean("GOOGLE_SHEETS_TAB_NAME_HYBRID", base_tab),
        )
    return base_id, base_tab


def append_trade_metric(payload: Dict, logger=None) -> bool:
    """
    Append one closed-trade metrics row to Google Sheets.
    Returns True on success; False on any non-fatal failure.
    """
    enabled = _env_clean("GOOGLE_SHEETS_METRICS_ENABLED", "true").lower() in ("1", "true", "yes", "y")
    if not enabled:
        return False

    spreadsheet_id, sheet_name = _target_for_engine(str(payload.get("engine") or ""))
    creds_file = _env_clean("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", "store-492411-d5287987a514.json")
    if not spreadsheet_id or not creds_file:
        return False

    if not os.path.isabs(creds_file):
        creds_file = os.path.join(os.getcwd(), creds_file)
    if not os.path.isfile(creds_file):
        if logger:
            logger.warning(f"Google Sheets credentials file missing: {creds_file}")
        return False

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except Exception as e:
        if logger:
            logger.warning(f"Google Sheets dependencies missing: {e}")
        return False

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        body = {"values": [_build_values(payload)]}
        target_range = f"{sheet_name}!A:I"
        try:
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=target_range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()
            return True
        except Exception as e:
            fallback_enabled = _env_clean("GOOGLE_SHEETS_FALLBACK_TO_BASE_TAB", "false").lower() in (
                "1",
                "true",
                "yes",
                "y",
            )
            # Optional fallback to base tab (disabled by default for strict per-engine tabs).
            fallback_tab = _env_clean("GOOGLE_SHEETS_TAB_NAME", "Sheet1")
            if fallback_enabled and fallback_tab and fallback_tab != sheet_name and "Unable to parse range" in str(e):
                if logger:
                    logger.warning(
                        f"Sheet tab '{sheet_name}' not found; falling back to '{fallback_tab}'."
                    )
                service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=f"{fallback_tab}!A:I",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=body,
                ).execute()
                return True
            raise
    except Exception as e:
        if logger:
            logger.warning(f"Google Sheets append failed: {e}")
        return False

