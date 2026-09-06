"""Configuration manager for Passiflora Ganesh Festival 2026 Aarti Booking System.

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

# Festival Branding
FESTIVAL_NAME = "Passiflora Ganesh Festival 2026"
FESTIVAL_SLOGAN = "Ganpati Bappa Morya"
FESTIVAL_CHANT = "॥ गणपति बाप्पा मोरया • मंगलमूर्ती मोरया ॥"

# Default Timezone for Community Festival
TIMEZONE_STR = "Asia/Kolkata"
IST = ZoneInfo(TIMEZONE_STR)

# Daily Aarti Slots (2 times a day: Morning Aarti & Evening Aarti)
FESTIVAL_SLOTS = [
    {
        "time": "10:00 AM",
        "name": "Morning Aarti",
        "icon": "🌅",
        "start_time_24": "10:00",
        "end_time_24": "10:45",
        "duration_minutes": 45,
    },
    {
        "time": "08:00 PM",
        "name": "Evening Aarti",
        "icon": "🌙",
        "start_time_24": "20:00",
        "end_time_24": "20:45",
        "duration_minutes": 45,
    },
]

# Hindu Vedic Tithi Mapping for 14th Sep to 25th Sep 2026 (Bhadrapada Shukla Paksha)
HINDU_VEDIC_TITHIS: Dict[str, str] = {
    "2026-09-14": "Bhadrapada Shukla Chaturthi (Ganesh Chaturthi / Sthapana)",
    "2026-09-15": "Bhadrapada Shukla Panchami (Rishi Panchami)",
    "2026-09-16": "Bhadrapada Shukla Shashthi",
    "2026-09-17": "Bhadrapada Shukla Saptami (Gauri Avahana / Sthapana)",
    "2026-09-18": "Bhadrapada Shukla Ashtami (Gauri Puja / Mahalakshmi Vrat)",
    "2026-09-19": "Bhadrapada Shukla Navami (Gauri Visarjan)",
    "2026-09-20": "Bhadrapada Shukla Dashami (Satyanarayan Vrat / Mahaprasad)",
    "2026-09-21": "Bhadrapada Shukla Ekadashi (Parivartini / Padma Ekadashi)",
    "2026-09-22": "Bhadrapada Shukla Dvadashi (Vamana Jayanti)",
    "2026-09-23": "Bhadrapada Shukla Trayodashi (Bhauma / Pradosh Vrat)",
    "2026-09-24": "Bhadrapada Shukla Chaturdashi",
    "2026-09-25": "Bhadrapada Shukla Chaturdashi (Anant Chaturdashi / Visarjan)",
}


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
    """Return the starting date of Passiflora Ganesh Festival 2026 (14th Sep 2026)."""
    date_str = get_secret("FESTIVAL_START_DATE", "2026-09-14")
    if date_str:
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    return date(2026, 9, 14)


def get_festival_days_count() -> int:
    """Return the number of festival days (14th Sep to 25th Sep = 12 days)."""
    try:
        val = get_secret("FESTIVAL_DAYS", 12)
        return int(val)
    except (ValueError, TypeError):
        return 12


def get_festival_dates() -> List[Dict[str, Any]]:
    """Return list of festival dates with Vedic Tithi, day index, and labels."""
    start_date = get_festival_start_date()
    days_count = get_festival_days_count()
    result = []

    for i in range(days_count):
        cur_date = start_date + timedelta(days=i)
        day_num = i + 1
        d_str = cur_date.strftime("%Y-%m-%d")
        tithi = HINDU_VEDIC_TITHIS.get(d_str, "Shukla Paksha")

        result.append(
            {
                "day_number": day_num,
                "date": cur_date,
                "date_str": d_str,
                "tithi": tithi,
                "display_label": f"Day {day_num} • {cur_date.strftime('%d %b (%a)')} • 🪔 {tithi}",
                "short_label": f"Day {day_num} ({cur_date.strftime('%d %b')})",
                "weekday": cur_date.strftime("%A"),
            }
        )
    return result


def is_mock_mode() -> bool:
    """Check if external APIs should run in mock/simulation mode."""
    explicit = str(get_secret("MOCK_MODE", "")).lower() in ("true", "1", "yes")
    if explicit:
        return True

    has_gcp = get_service_account_credentials() is not None
    has_sheet = bool(get_google_sheet_key())
    return not (has_gcp and has_sheet)
