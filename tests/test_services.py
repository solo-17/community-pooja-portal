"""Unit and integration test suite for Community Pooja & Aarti Booking System."""

import os
import shutil
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from daily_summary import generate_and_send_daily_digest
from services.calendar_service import CalendarService, parse_slot_datetimes
from services.config import (
    FESTIVAL_SLOTS,
    TIMEZONE_STR,
    get_festival_dates,
)
from services.sheets_service import MOCK_DB_PATH, SheetsService
from services.whatsapp_service import WhatsAppService, normalize_phone_number


@pytest.fixture(autouse=True)
def clean_mock_storage():
    """Ensure clean mock database before each test."""
    if os.path.exists(MOCK_DB_PATH):
        os.remove(MOCK_DB_PATH)
    yield
    if os.path.exists(MOCK_DB_PATH):
        os.remove(MOCK_DB_PATH)


def test_festival_dates():
    """Verify that festival dates generate 10 consecutive celebration days."""
    dates = get_festival_dates()
    assert len(dates) == 10
    assert dates[0]["day_number"] == 1
    assert dates[9]["day_number"] == 10
    assert "date_str" in dates[0]
    assert "display_label" in dates[0]
    assert "weekday" in dates[0]


def test_phone_normalization():
    """Verify WhatsApp phone normalization for various input styles."""
    assert normalize_phone_number("9876543210") == "919876543210"
    assert normalize_phone_number("+91 98765-43210") == "919876543210"
    assert normalize_phone_number("09876543210") == "919876543210"
    assert normalize_phone_number("919876543210") == "919876543210"


def test_calendar_slot_datetimes():
    """Verify start and end datetime parsing in IST timezone."""
    start_dt, end_dt = parse_slot_datetimes("2026-09-07", "07:00 AM")
    assert str(start_dt.tzinfo) == TIMEZONE_STR
    assert start_dt.hour == 7
    assert start_dt.minute == 0
    assert end_dt.hour == 7
    assert end_dt.minute == 45

    # Afternoon Pooja: 11:00 AM to 12:30 PM (90 mins)
    start_dt2, end_dt2 = parse_slot_datetimes("2026-09-07", "11:00 AM")
    assert start_dt2.hour == 11
    assert start_dt2.minute == 0
    assert end_dt2.hour == 12
    assert end_dt2.minute == 30


def test_sheets_service_lifecycle():
    """Test full booking lifecycle: check availability, book, duplicate prevent, search, and cancel."""
    service = SheetsService()
    test_date = "2026-09-08"
    test_slot = "07:00 AM"

    # 1. Slot must be initially available
    assert service.is_slot_available(test_date, test_slot) is True

    # 2. Create booking
    ok, msg = service.create_booking(
        date_str=test_date,
        slot_time=test_slot,
        flat_no="A-302",
        resident_name="Ramesh Sharma",
        mobile_no="9876543210",
        gcal_event_id="evt_test_123",
    )
    assert ok is True
    assert service.is_slot_available(test_date, test_slot) is False

    # 3. Duplicate booking attempt must fail atomically
    dup_ok, dup_msg = service.create_booking(
        date_str=test_date,
        slot_time=test_slot,
        flat_no="B-101",
        resident_name="Another Resident",
        mobile_no="9811111111",
    )
    assert dup_ok is False
    assert "already been booked" in dup_msg

    # 4. Search by Flat Number
    found_by_flat = service.find_active_bookings("A-302")
    assert len(found_by_flat) == 1
    assert found_by_flat[0]["Resident_Name"] == "Ramesh Sharma"

    # Search by Mobile
    found_by_mobile = service.find_active_bookings("9876543210")
    assert len(found_by_mobile) == 1

    # 5. Cancellation
    cancel_ok, cancel_msg, gcal_id = service.cancel_booking(
        date_str=test_date,
        slot_time=test_slot,
        flat_or_mobile="A-302",
    )
    assert cancel_ok is True
    assert gcal_id == "evt_test_123"

    # 6. Verify GCal_Event_ID was cleared/deleted in Sheet
    all_recs = service.get_all_bookings()
    cancelled_rec = next(r for r in all_recs if r["Date"] == test_date and r["Slot_Time"] == test_slot)
    assert cancelled_rec["Status"] == "Cancelled"
    assert cancelled_rec["GCal_Event_ID"] == ""

    # 7. Slot should now be available again
    assert service.is_slot_available(test_date, test_slot) is True


def test_whatsapp_service_simulation():
    """Test WhatsApp notifications dispatch and message content generation."""
    service = WhatsAppService()

    ok, msg = service.send_booking_confirmation(
        to_phone="9876543210",
        resident_name="Sunita Rao",
        flat_no="C-501",
        date_str="2026-09-09",
        slot_time="11:00 AM",
    )
    assert ok is True

    ok2, msg2 = service.send_cancellation_notification(
        to_phone="9876543210",
        resident_name="Sunita Rao",
        flat_no="C-501",
        date_str="2026-09-09",
        slot_time="11:00 AM",
    )
    assert ok2 is True

    ok3, msg3 = service.send_cancellation_otp(
        to_phone="9876543210",
        otp="4821",
        resident_name="Sunita Rao",
        flat_no="C-501",
        date_str="2026-09-09",
        slot_time="11:00 AM",
    )
    assert ok3 is True


def test_daily_digest_dry_run():
    """Test 4:00 AM daily summary generation in dry-run mode."""
    service = SheetsService()
    service.create_booking(
        date_str="2026-09-10",
        slot_time="07:00 PM",
        flat_no="D-204",
        resident_name="Vikram Verma",
        mobile_no="9899001122",
    )

    success = generate_and_send_daily_digest(
        target_date_str="2026-09-10",
        dry_run=True,
    )
    assert success is True
