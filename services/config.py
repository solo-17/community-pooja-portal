"""Configuration manager for the Community Pooja & Aarti Booking System.

Loads configuration from Streamlit secrets (`st.secrets`) or environment variables (.env).
Provides fallback handling and mock mode detection when external services are not configured.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from dotenv import find_dotenv, load_dotenv

# Load local .env file if present
load_dotenv(find_dotenv())

# Default Timezone for Community Festival
TIMEZONE_STR = "Asia/Kolkata"
IST = ZoneInfo(TIMEZONE_STR)

# Standard festival daily slots
FESTIVAL_SLOTS = [
    {
        "time": "07:00 AM",
        "name": "Morning Aarti",
        "icon": "🌅",
        "start_time_24": "07:00",
        "end_time_24": "07:45",
        "duration_minutes": 45,
    },
    {
        "time": "11:00 AM",
        "name": "Afternoon Pooja",
        "icon": "🪔",
        "start_time_24": "11:00",
        "end_time_24": "12:30",
        "duration_minutes": 90,
    },
    {
        "time": "07:00 PM",
        "name": "Evening Aarti",
        "icon": "🌙",
        "start_time_24": "19:00",
        "end_time_24": "19:45",
        "duration_minutes": 45,
    },
]


def get_secret(key: str, default: Optional[Any] = None) -> Any:
    """Retrieve secret from st.secrets if running in Streamlit, else os.environ."""
    # Try Streamlit secrets first
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # Try OS environment variables
    return os.environ.get(key, default)


def get_service_account_credentials() -> Optional[Dict[str, Any]]:
    """Parse Google Service Account credentials.

    Supports:
    - Dictionary directly from st.secrets['gcp_service_account'] or st.secrets['GOOGLE_SERVICE_ACCOUNT_JSON']
    - JSON string in env var GOOGLE_SERVICE_ACCOUNT_JSON
    - Path to credentials.json in env var GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS
    """
    raw = get_secret("GOOGLE_SERVICE_ACCOUNT_JSON") or get_secret(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )

    if not raw:
        # Check if st.secrets has gcp_service_account dict
        try:
            import streamlit as st

            if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
                return dict(st.secrets["gcp_service_account"])
        except Exception:
            pass
        return None

    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        raw_str = raw.strip()
        # Case 1: JSON formatted string
        if raw_str.startswith("{") and raw_str.endswith("}"):
            try:
                return json.loads(raw_str)
            except json.JSONDecodeError:
                pass

        # Case 2: File path on disk
        if os.path.exists(raw_str):
            try:
                with open(raw_str, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    return None


def get_google_sheet_key() -> str:
    """Return the Google Sheet Key / ID."""
    return (get_secret("GOOGLE_SHEET_KEY") or "").strip()


def get_google_calendar_id() -> str:
    """Return the Google Calendar ID."""
    return (get_secret("GOOGLE_CALENDAR_ID") or "primary").strip()


def get_whatsapp_token() -> str:
    """Return Meta WhatsApp Cloud API access token."""
    return (get_secret("WHATSAPP_TOKEN") or "").strip()


def get_whatsapp_phone_number_id() -> str:
    """Return Meta WhatsApp Phone Number ID."""
    return (get_secret("WHATSAPP_PHONE_NUMBER_ID") or "").strip()


def get_admin_whatsapp_number() -> str:
    """Return Admin WhatsApp phone number."""
    return (get_secret("ADMIN_WHATSAPP_NUMBER") or "").strip()


def get_festival_start_date() -> date:
    """Return the starting date of the 10-day festival.

    If not set in env, defaults to today's date in IST.
    """
    date_str = get_secret("FESTIVAL_START_DATE")
    if date_str:
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    # Default to current date in IST
    now_ist = datetime.now(IST)
    return now_ist.date()


def get_festival_days_count() -> int:
    """Return the number of festival days (default 10)."""
    try:
        val = get_secret("FESTIVAL_DAYS", 10)
        return int(val)
    except (ValueError, TypeError):
        return 10


def get_festival_dates() -> List[Dict[str, Any]]:
    """Return list of 10 festival dates with labels, day index, and formatted strings."""
    start_date = get_festival_start_date()
    days_count = get_festival_days_count()
    result = []

    for i in range(days_count):
        cur_date = start_date + timedelta(days=i)
        day_num = i + 1
        result.append(
            {
                "day_number": day_num,
                "date": cur_date,
                "date_str": cur_date.strftime("%Y-%m-%d"),
                "display_label": f"Day {day_num} • {cur_date.strftime('%a, %d %b %Y')}",
                "short_label": f"Day {day_num} ({cur_date.strftime('%d %b')})",
                "weekday": cur_date.strftime("%A"),
            }
        )
    return result


def is_mock_mode() -> bool:
    """Check if external APIs should run in mock/simulation mode.

    Returns True if service account or WhatsApp credentials are missing, or if
    explicitly enabled via MOCK_MODE=true.
    """
    explicit = str(get_secret("MOCK_MODE", "")).lower() in ("true", "1", "yes")
    if explicit:
        return True

    has_gcp = get_service_account_credentials() is not None
    has_sheet = bool(get_google_sheet_key())
    return not (has_gcp and has_sheet)
