"""Google Sheets service for persistent storage of Pooja & Aarti bookings.

Handles reading, atomic availability checking, appending new bookings,
and updating cancellation status using `gspread`.
Includes local JSON persistence fallback for mock/development mode.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.config import (
    IST,
    get_google_sheet_key,
    get_service_account_credentials,
    is_mock_mode,
)

logger = logging.getLogger(__name__)

# Standard columns as defined in specifications
SHEET_HEADERS = [
    "Date",
    "Slot_Time",
    "Flat_No",
    "Resident_Name",
    "Mobile_No",
    "Status",
    "GCal_Event_ID",
    "Created_At",
]

MOCK_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "mock_bookings.json",
)


class SheetsService:
    """Manages Google Sheets operations for festival bookings."""

    def __init__(self) -> None:
        self._client = None
        self._sheet = None
        self._worksheet = None
        self._mock_mode = is_mock_mode()

        if not self._mock_mode:
            try:
                self._init_gspread()
            except Exception as e:
                logger.warning(
                    "Failed to connect to Google Sheets (%s). Falling back to mock mode.",
                    e,
                )
                self._mock_mode = True

        if self._mock_mode:
            self._init_mock_storage()

    def _init_gspread(self) -> None:
        """Initialize gspread client and ensure headers exist."""
        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = get_service_account_credentials()
        if not creds_dict:
            raise ValueError("No Google Service Account credentials found.")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(
            creds_dict, scopes=scopes
        )
        self._client = gspread.authorize(credentials)

        sheet_key = get_google_sheet_key()
        if not sheet_key:
            raise ValueError("GOOGLE_SHEET_KEY is empty.")

        # Open by key or URL or title
        if sheet_key.startswith("https://"):
            self._sheet = self._client.open_by_url(sheet_key)
        elif len(sheet_key) >= 30 and "/" not in sheet_key:
            self._sheet = self._client.open_by_key(sheet_key)
        else:
            self._sheet = self._client.open(sheet_key)

        try:
            self._worksheet = self._sheet.worksheet("Bookings")
        except Exception:
            # If 'Bookings' worksheet doesn't exist, use the first sheet or create it
            try:
                self._worksheet = self._sheet.sheet1
                # Rename to Bookings if desired or keep sheet1
            except Exception:
                self._worksheet = self._sheet.add_worksheet(
                    title="Bookings", rows="500", cols="10"
                )

        # Verify or set headers
        existing_values = self._worksheet.get_all_values()
        if not existing_values or len(existing_values) == 0:
            self._worksheet.append_row(SHEET_HEADERS)
        elif existing_values[0] != SHEET_HEADERS:
            # Check if headers match or need update
            if len(existing_values[0]) < len(SHEET_HEADERS):
                self._worksheet.insert_row(SHEET_HEADERS, 1)

    def _init_mock_storage(self) -> None:
        """Initialize mock JSON storage file."""
        os.makedirs(os.path.dirname(MOCK_DB_PATH), exist_ok=True)
        if not os.path.exists(MOCK_DB_PATH):
            with open(MOCK_DB_PATH, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def _read_mock_data(self) -> List[Dict[str, Any]]:
        """Read mock bookings from local file."""
        if not os.path.exists(MOCK_DB_PATH):
            return []
        try:
            with open(MOCK_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _write_mock_data(self, data: List[Dict[str, Any]]) -> None:
        """Write mock bookings to local file."""
        os.makedirs(os.path.dirname(MOCK_DB_PATH), exist_ok=True)
        with open(MOCK_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_all_bookings(self) -> List[Dict[str, Any]]:
        """Fetch all bookings from Google Sheets or mock storage."""
        if self._mock_mode:
            return self._read_mock_data()

        try:
            records = self._worksheet.get_all_records()
            return records
        except Exception as e:
            logger.error("Error fetching bookings from Google Sheets: %s", e)
            return []

    def get_bookings_for_date(self, date_str: str) -> List[Dict[str, Any]]:
        """Get all active (Booked) bookings for a specific date (YYYY-MM-DD)."""
        all_bookings = self.get_all_bookings()
        return [
            b
            for b in all_bookings
            if str(b.get("Date", "")).strip() == date_str.strip()
            and str(b.get("Status", "")).strip().lower() == "booked"
        ]

    def is_slot_available(self, date_str: str, slot_time: str) -> bool:
        """Check if a specific date and slot_time is currently available."""
        all_bookings = self.get_all_bookings()
        for b in all_bookings:
            if (
                str(b.get("Date", "")).strip() == date_str.strip()
                and str(b.get("Slot_Time", "")).strip() == slot_time.strip()
                and str(b.get("Status", "")).strip().lower() == "booked"
            ):
                return False
        return True

    def get_slot_booking_details(
        self, date_str: str, slot_time: str
    ) -> Optional[Dict[str, Any]]:
        """Return the booking dict if slot is booked, else None."""
        all_bookings = self.get_all_bookings()
        for b in all_bookings:
            if (
                str(b.get("Date", "")).strip() == date_str.strip()
                and str(b.get("Slot_Time", "")).strip() == slot_time.strip()
                and str(b.get("Status", "")).strip().lower() == "booked"
            ):
                return b
        return None

    def create_booking(
        self,
        date_str: str,
        slot_time: str,
        flat_no: str,
        resident_name: str,
        mobile_no: str,
        gcal_event_id: str = "",
    ) -> Tuple[bool, str]:
        """Atomically check and create a booking.

        Returns (success: bool, message: str).
        """
        clean_date = date_str.strip()
        clean_slot = slot_time.strip()
        clean_flat = flat_no.strip()
        clean_name = resident_name.strip()
        clean_mobile = mobile_no.strip()
        now_ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

        # Concurrency safety check
        if not self.is_slot_available(clean_date, clean_slot):
            return (
                False,
                f"Slot '{clean_slot}' on {clean_date} has already been booked by another resident.",
            )

        if self._mock_mode:
            data = self._read_mock_data()
            new_record = {
                "Date": clean_date,
                "Slot_Time": clean_slot,
                "Flat_No": clean_flat,
                "Resident_Name": clean_name,
                "Mobile_No": clean_mobile,
                "Status": "Booked",
                "GCal_Event_ID": gcal_event_id,
                "Created_At": now_ts,
            }
            data.append(new_record)
            self._write_mock_data(data)
            return True, "Booking confirmed successfully!"

        try:
            row_data = [
                clean_date,
                clean_slot,
                clean_flat,
                clean_name,
                clean_mobile,
                "Booked",
                gcal_event_id,
                now_ts,
            ]
            self._worksheet.append_row(row_data)
            return True, "Booking confirmed successfully in Google Sheets!"
        except Exception as e:
            logger.error("Failed to append row to Google Sheets: %s", e)
            return False, f"Failed to record booking: {str(e)}"

    def find_active_bookings(self, query: str) -> List[Dict[str, Any]]:
        """Search active bookings matching Mobile Number or Flat Number."""
        clean_query = query.strip().lower()
        if not clean_query:
            return []

        # Normalize digits if mobile
        query_digits = "".join(filter(str.isdigit, clean_query))

        all_bookings = self.get_all_bookings()
        results = []
        for idx, b in enumerate(all_bookings):
            status = str(b.get("Status", "")).strip().lower()
            if status != "booked":
                continue

            flat = str(b.get("Flat_No", "")).strip().lower()
            mobile = str(b.get("Mobile_No", "")).strip()
            mobile_digits = "".join(filter(str.isdigit, mobile))

            matched = False
            # Flat match (exact or substring)
            if clean_query == flat or clean_query in flat:
                matched = True
            # Mobile match
            elif query_digits and (
                query_digits in mobile_digits
                or mobile_digits.endswith(query_digits)
            ):
                matched = True

            if matched:
                item = dict(b)
                # Store index (+2 because 1-indexed and header row is row 1)
                item["_row_index"] = idx + 2
                results.append(item)

        return results

    def cancel_booking(
        self, date_str: str, slot_time: str, flat_or_mobile: str
    ) -> Tuple[bool, str, Optional[str]]:
        """Cancel an active booking.

        Returns (success: bool, message: str, gcal_event_id: Optional[str]).
        """
        clean_date = date_str.strip()
        clean_slot = slot_time.strip()
        clean_target = flat_or_mobile.strip().lower()
        target_digits = "".join(filter(str.isdigit, clean_target))

        if self._mock_mode:
            data = self._read_mock_data()
            for item in data:
                if (
                    item.get("Date") == clean_date
                    and item.get("Slot_Time") == clean_slot
                    and item.get("Status") == "Booked"
                ):
                    flat = str(item.get("Flat_No", "")).strip().lower()
                    mobile = str(item.get("Mobile_No", "")).strip()
                    mobile_digits = "".join(filter(str.isdigit, mobile))

                    if (
                        clean_target in flat
                        or (target_digits and target_digits in mobile_digits)
                        or clean_target == ""
                    ):
                        item["Status"] = "Cancelled"
                        self._write_mock_data(data)
                        return (
                            True,
                            "Booking successfully cancelled.",
                            item.get("GCal_Event_ID"),
                        )
            return (
                False,
                "Active booking not found for cancellation.",
                None,
            )

        try:
            # In live Google Sheets, find the row
            all_values = self._worksheet.get_all_values()
            status_col_idx = SHEET_HEADERS.index("Status") + 1
            gcal_col_idx = SHEET_HEADERS.index("GCal_Event_ID") + 1

            for row_idx, row in enumerate(all_values[1:], start=2):
                if len(row) < len(SHEET_HEADERS):
                    continue
                row_date = row[0].strip()
                row_slot = row[1].strip()
                row_flat = row[2].strip().lower()
                row_mobile = row[4].strip()
                row_status = row[5].strip()
                gcal_id = row[6].strip() if len(row) > 6 else ""

                if (
                    row_date == clean_date
                    and row_slot == clean_slot
                    and row_status.lower() == "booked"
                ):
                    mobile_digits = "".join(filter(str.isdigit, row_mobile))
                    if (
                        clean_target in row_flat
                        or (target_digits and target_digits in mobile_digits)
                        or clean_target == ""
                    ):
                        # Update status cell to 'Cancelled'
                        self._worksheet.update_cell(
                            row_idx, status_col_idx, "Cancelled"
                        )
                        return (
                            True,
                            "Booking successfully marked as Cancelled in Google Sheets.",
                            gcal_id,
                        )

            return (
                False,
                "Active booking not found matching criteria in Google Sheets.",
                None,
            )
        except Exception as e:
            logger.error("Error cancelling booking in Google Sheets: %s", e)
            return False, f"Failed to cancel booking: {str(e)}", None

    def update_gcal_id(
        self, date_str: str, slot_time: str, gcal_event_id: str
    ) -> bool:
        """Update GCal_Event_ID for a given date and slot."""
        if self._mock_mode:
            data = self._read_mock_data()
            for item in data:
                if (
                    item.get("Date") == date_str
                    and item.get("Slot_Time") == slot_time
                    and item.get("Status") == "Booked"
                ):
                    item["GCal_Event_ID"] = gcal_event_id
                    self._write_mock_data(data)
                    return True
            return False

        try:
            all_values = self._worksheet.get_all_values()
            gcal_col_idx = SHEET_HEADERS.index("GCal_Event_ID") + 1
            for row_idx, row in enumerate(all_values[1:], start=2):
                if (
                    row[0].strip() == date_str.strip()
                    and row[1].strip() == slot_time.strip()
                    and row[5].strip().lower() == "booked"
                ):
                    self._worksheet.update_cell(
                        row_idx, gcal_col_idx, gcal_event_id
                    )
                    return True
            return False
        except Exception as e:
            logger.error("Failed to update GCal Event ID: %s", e)
            return False
