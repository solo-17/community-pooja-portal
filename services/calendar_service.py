"""Google Calendar service for scheduling and cancelling Pooja & Aarti events.

Uses the official Google Calendar API v3 to create and delete events on the
community admin calendar in Asia/Kolkata (IST) timezone.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from services.config import (
    FESTIVAL_SLOTS,
    TIMEZONE_STR,
    get_google_calendar_id,
    get_service_account_credentials,
    is_mock_mode,
)

logger = logging.getLogger(__name__)


def parse_slot_datetimes(
    date_str: str, slot_time: str
) -> Tuple[datetime, datetime]:
    """Calculate start and end datetime in IST for a given date and slot."""
    tz = ZoneInfo(TIMEZONE_STR)
    target_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()

    # Find matching slot configuration
    matched_slot = None
    for s in FESTIVAL_SLOTS:
        if s["time"].strip().lower() == slot_time.strip().lower():
            matched_slot = s
            break

    if matched_slot:
        start_hour, start_min = map(
            int, matched_slot["start_time_24"].split(":")
        )
        end_hour, end_min = map(int, matched_slot["end_time_24"].split(":"))
        start_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            start_hour,
            start_min,
            tzinfo=tz,
        )
        end_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            end_hour,
            end_min,
            tzinfo=tz,
        )
    else:
        # Fallback: parse 12-hour format or default 45 mins
        try:
            parsed_time = datetime.strptime(slot_time.strip(), "%I:%M %p").time()
            start_dt = datetime.combine(target_date, parsed_time, tzinfo=tz)
            end_dt = start_dt + timedelta(minutes=45)
        except Exception:
            start_dt = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                7,
                0,
                tzinfo=tz,
            )
            end_dt = start_dt + timedelta(minutes=45)

    return start_dt, end_dt


class CalendarService:
    """Manages Google Calendar event operations."""

    def __init__(self) -> None:
        self._service = None
        self._calendar_id = get_google_calendar_id()
        self._mock_mode = is_mock_mode()

        if not self._mock_mode:
            try:
                self._init_calendar_client()
            except Exception as e:
                logger.warning(
                    "Failed to initialize Google Calendar client (%s). Using mock calendar.",
                    e,
                )
                self._mock_mode = True

    def _init_calendar_client(self) -> None:
        """Initialize Google Calendar API client."""
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds_dict = get_service_account_credentials()
        if not creds_dict:
            raise ValueError("No Service Account credentials available.")

        scopes = ["https://www.googleapis.com/auth/calendar"]
        credentials = Credentials.from_service_account_info(
            creds_dict, scopes=scopes
        )
        self._service = build("calendar", "v3", credentials=credentials)

    def create_event(
        self,
        date_str: str,
        slot_time: str,
        flat_no: str,
        resident_name: str,
        mobile_no: str,
    ) -> Optional[str]:
        """Create an event on Google Calendar.

        Returns the created GCal event ID or None on failure.
        """
        start_dt, end_dt = parse_slot_datetimes(date_str, slot_time)
        summary = f"[Flat {flat_no}] - {resident_name} ({slot_time})"
        description = (
            f"Resident: {resident_name}\n"
            f"Flat: {flat_no}\n"
            f"WhatsApp: {mobile_no}\n"
            f"Slot: {slot_time}\n"
            f"Date: {date_str}"
        )

        if self._mock_mode:
            mock_event_id = f"mock_gcal_{uuid.uuid4().hex[:12]}"
            logger.info(
                "[MOCK GCAL] Created event: ID=%s, Summary='%s', Start=%s, End=%s",
                mock_event_id,
                summary,
                start_dt.isoformat(),
                end_dt.isoformat(),
            )
            return mock_event_id

        try:
            event_body = {
                "summary": summary,
                "description": description,
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": TIMEZONE_STR,
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": TIMEZONE_STR,
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 30},
                    ],
                },
            }

            event = (
                self._service.events()
                .insert(calendarId=self._calendar_id, body=event_body)
                .execute()
            )
            created_id = event.get("id")
            logger.info("Created Google Calendar event: %s", created_id)
            return created_id
        except Exception as e:
            logger.error("Failed to create Google Calendar event: %s", e)
            return None

    def delete_event(self, gcal_event_id: str) -> bool:
        """Delete an event from Google Calendar using its Event ID."""
        if not gcal_event_id:
            return True

        if self._mock_mode:
            logger.info("[MOCK GCAL] Deleted event ID: %s", gcal_event_id)
            return True

        try:
            self._service.events().delete(
                calendarId=self._calendar_id, eventId=gcal_event_id
            ).execute()
            logger.info("Deleted Google Calendar event: %s", gcal_event_id)
            return True
        except Exception as e:
            # 404 or 410 means already deleted
            if "notFound" in str(e) or "404" in str(e) or "410" in str(e):
                logger.info("Event %s already removed from calendar.", gcal_event_id)
                return True
            logger.error("Failed to delete Google Calendar event (%s): %s", gcal_event_id, e)
            return False
