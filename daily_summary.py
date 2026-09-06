#!/usr/bin/env python3
"""Daily 4:00 AM Pooja & Aarti Schedule Digest Script.

Runs via GitHub Actions cron or system cron at 4:00 AM IST.
Queries Google Sheets for today's bookings and dispatches a consolidated
schedule message to the Admin WhatsApp Number.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from services.config import (
    FESTIVAL_SLOTS,
    IST,
    get_admin_whatsapp_number,
    is_mock_mode,
)
from services.sheets_service import SheetsService
from services.whatsapp_service import WhatsAppService

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def generate_and_send_daily_digest(
    target_date_str: str,
    dry_run: bool = False,
    override_admin_phone: str = "",
) -> bool:
    """Compile daily schedule from Google Sheets and dispatch via WhatsApp."""
    logger.info("Initializing Daily Digest for date: %s", target_date_str)
    if is_mock_mode():
        logger.info("Running in Mock Mode (no external GCP credentials detected).")

    sheets_service = SheetsService()
    whatsapp_service = WhatsAppService()

    # Fetch all active bookings for target date
    active_bookings = sheets_service.get_bookings_for_date(target_date_str)
    logger.info(
        "Found %d active booking(s) for %s", len(active_bookings), target_date_str
    )

    # Map bookings by slot time
    slot_booking_map = {b.get("Slot_Time"): b for b in active_bookings}

    # Build schedule list for all standard slots
    schedule_items = []
    for slot in FESTIVAL_SLOTS:
        slot_time = slot["time"]
        slot_name = slot["name"]
        booking = slot_booking_map.get(slot_time)
        schedule_items.append(
            {
                "time": slot_time,
                "name": slot_name,
                "icon": slot["icon"],
                "booking": booking,
            }
        )

    admin_phone = override_admin_phone or get_admin_whatsapp_number()
    logger.info("Target Admin Phone: %s", admin_phone or "NOT_CONFIGURED")

    if dry_run:
        logger.info("DRY RUN ENABLED - Message preview below:")
        lines = [
            "🚩 *॥ गणपति बाप्पा मोरया • मंगल मूर्ती मोरया ॥* 🚩",
            f"🌺 *Passiflora Ganesh Festival 2026 - Daily Aarti Schedule ({target_date_str})*:",
            "",
        ]
        booked_count = 0
        for item in schedule_items:
            t = item["time"]
            n = item["name"]
            b = item["booking"]
            if b:
                booked_count += 1
                lines.append(
                    f"• {item['icon']} *{t}* ({n}): Flat {b.get('Flat_No')} - {b.get('Resident_Name')} ({b.get('Mobile_No')})"
                )
            else:
                lines.append(f"• {item['icon']} *{t}* ({n}): _Available_")
        lines.append("")
        lines.append(f"📊 Total Booked: {booked_count}/{len(schedule_items)} Aarti slots.")
        print("\n" + "\n".join(lines) + "\n")
        return True

    success, msg = whatsapp_service.send_daily_digest(
        date_str=target_date_str,
        schedule_items=schedule_items,
        admin_phone=admin_phone,
    )

    if success:
        logger.info("Daily digest dispatched successfully! Result: %s", msg)
        return True
    else:
        logger.error("Failed to dispatch daily digest: %s", msg)
        return False


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Dispatch daily Pooja & Aarti WhatsApp summary to community admin."
    )
    parser.add_argument(
        "--date",
        type=str,
        default="",
        help="Target date in YYYY-MM-DD format (defaults to current date in IST).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview schedule without sending WhatsApp message.",
    )
    parser.add_argument(
        "--admin-phone",
        type=str,
        default="",
        help="Override admin phone number for testing.",
    )

    args = parser.parse_args()

    if args.date:
        target_date = args.date.strip()
    else:
        target_date = datetime.now(IST).strftime("%Y-%m-%d")

    ok = generate_and_send_daily_digest(
        target_date_str=target_date,
        dry_run=args.dry_run,
        override_admin_phone=args.admin_phone,
    )

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
