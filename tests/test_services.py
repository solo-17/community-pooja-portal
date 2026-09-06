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
    """Verify that festival dates generate 12 consecutive days from 14th Sep to 25th Sep 2026 with Vedic Tithi."""
    dates = get_festival_dates()
    assert len(dates) == 12
    assert dates[0]["day_number"] == 1
    assert dates[0]["date_str"] == "2026-09-14"
    assert "Chaturthi" in dates[0]["tithi"]
    assert dates[10]["date_str"] == "2026-09-24"
    assert dates[10]["tithi"] == "Bhadrapada Shukla Chaturdashi"
    assert dates[11]["day_number"] == 12
    assert dates[11]["date_str"] == "2026-09-25"
    assert dates[11]["tithi"] == "Bhadrapada Shukla Chaturdashi (Anant Chaturdashi / Visarjan)"
    assert "date_str" in dates[0]
    assert "display_label" in dates[0]
    assert "weekday" in dates[0]
    assert "tithi" in dates[0]


def test_phone_normalization():
    """Verify WhatsApp phone normalization for various input styles."""
    assert normalize_phone_number("9876543210") == "919876543210"
    assert normalize_phone_number("+91 98765-43210") == "919876543210"
    assert normalize_phone_number("09876543210") == "919876543210"
    assert normalize_phone_number("919876543210") == "919876543210"


def test_calendar_slot_datetimes():
    """Verify start and end datetime parsing in IST timezone for Morning & Evening Aartis."""
    assert len(FESTIVAL_SLOTS) == 2

    # Morning Aarti: 10:00 AM - 10:45 AM
    start_dt, end_dt = parse_slot_datetimes("2026-09-14", "10:00 AM")
    assert str(start_dt.tzinfo) == TIMEZONE_STR
    assert start_dt.hour == 10
    assert start_dt.minute == 0
    assert end_dt.hour == 10
    assert end_dt.minute == 45

    # Evening Aarti: 08:00 PM - 08:45 PM
    start_dt2, end_dt2 = parse_slot_datetimes("2026-09-14", "08:00 PM")
    assert start_dt2.hour == 20
    assert start_dt2.minute == 0
    assert end_dt2.hour == 20
    assert end_dt2.minute == 45


def test_sheets_service_lifecycle():
    """Test full booking lifecycle: check availability, book, duplicate prevent, search, and cancel."""
    service = SheetsService()
    test_date = "2026-09-14"
    test_slot = "10:00 AM"

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
        date_str="2026-09-14",
        slot_time="10:00 AM",
    )
    assert ok2 is True

    ok3, msg3 = service.send_cancellation_otp(
        to_phone="9876543210",
        otp="4821",
        resident_name="Sunita Rao",
        flat_no="C-501",
        date_str="2026-09-14",
        slot_time="10:00 AM",
    )
    assert ok3 is True


def test_daily_digest_dry_run():
    """Test 4:00 AM daily summary generation in dry-run mode."""
    service = SheetsService()
    service.create_booking(
        date_str="2026-09-14",
        slot_time="08:00 PM",
        flat_no="D-204",
        resident_name="Vikram Verma",
        mobile_no="9899001122",
    )

    success = generate_and_send_daily_digest(
        target_date_str="2026-09-14",
        dry_run=True,
    )
    assert success is True


def test_poster_pdf_generation():
    """Verify that PosterService generates a valid A4 PDF with Ganesha artwork and family roster."""
    from services.poster_service import PosterService

    test_bookings = [
        {
            "Date": "2026-09-14",
            "Slot_Time": "10:00 AM",
            "Flat_No": "A-302",
            "Resident_Name": "Ramesh Sharma",
            "Status": "Booked",
        },
        {
            "Date": "2026-09-14",
            "Slot_Time": "08:00 PM",
            "Flat_No": "B-504",
            "Resident_Name": "Suresh Patil",
            "Status": "Booked",
        },
    ]

    pdf_bytes = PosterService.generate_poster_pdf("2026-09-14", test_bookings)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 50000
    assert pdf_bytes.startswith(b"%PDF")

    # Test saving to temporary file
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_file = PosterService.save_poster_pdf("2026-09-14", test_bookings, output_dir=tmp_dir)
        assert os.path.exists(saved_file)
        assert os.path.getsize(saved_file) == len(pdf_bytes)


def test_email_service_dispatch():
    """Verify that EmailService generates email payload with attached PDF and audits dispatch."""
    from services.config import get_poster_notification_email, get_poster_notification_emails
    from services.email_service import EmailService, get_recent_email_notifications
    from services.poster_service import PosterService

    default_emails = get_poster_notification_emails()
    assert "avw2951981@gmail.com" in default_emails
    assert "free.rohit@gmail.com" in default_emails

    default_email_str = get_poster_notification_email()
    assert "avw2951981@gmail.com" in default_email_str
    assert "free.rohit@gmail.com" in default_email_str

    service = EmailService()
    pdf_bytes = PosterService.generate_poster_pdf("2026-09-14", [])

    # Test default multi-recipient dispatch
    ok, msg = service.send_poster_email(
        date_str="2026-09-14",
        pdf_bytes=pdf_bytes,
        tithi_str="Bhadrapada Shukla Chaturthi",
        bookings_summary=[
            {"slot_time": "10:00 AM", "slot_name": "Morning Aarti", "flat": "A-302", "family": "Ramesh Sharma & Family"},
            {"slot_time": "08:00 PM", "slot_name": "Evening Aarti", "flat": "B-504", "family": "Suresh Patil & Family"},
        ],
    )

    assert ok is True
    assert "avw2951981@gmail.com" in msg
    assert "free.rohit@gmail.com" in msg

    recent_emails = get_recent_email_notifications()
    assert len(recent_emails) > 0
    latest = recent_emails[0]
    assert "avw2951981@gmail.com" in latest["to"]
    assert "free.rohit@gmail.com" in latest["to"]
    assert latest["recipients"] == ["avw2951981@gmail.com", "free.rohit@gmail.com"]
    assert "Passiflora_Ganesh_Poster_2026-09-14.pdf" in latest["filename"]

