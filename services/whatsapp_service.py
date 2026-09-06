"""Meta WhatsApp Cloud API integration service for notifications.

Dispatches booking confirmations, cancellation alerts, and the 4:00 AM
daily schedule digest using Meta's Cloud API endpoint.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from services.config import (
    get_admin_whatsapp_number,
    get_whatsapp_phone_number_id,
    get_whatsapp_token,
)

logger = logging.getLogger(__name__)

# Recent in-memory message logs for UI display / audit
RECENT_NOTIFICATIONS: List[Dict[str, Any]] = []


def normalize_phone_number(raw_number: str) -> str:
    """Normalize phone number to international format without + or spaces.

    E.g. "9876543210" -> "919876543210"
    "+91 98765-43210" -> "919876543210"
    "09876543210" -> "919876543210"
    """
    digits = re.sub(r"\D", "", raw_number)

    # Strip leading 0 if present
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    # Default to India (+91) if 10 digits
    if len(digits) == 10:
        digits = f"91{digits}"

    return digits


class WhatsAppService:
    """Client for sending WhatsApp messages via Meta Cloud API."""

    def __init__(self) -> None:
        self.token = get_whatsapp_token()
        self.phone_number_id = get_whatsapp_phone_number_id()
        self.api_version = "v18.0"

    @property
    def is_configured(self) -> bool:
        """Check if WhatsApp API credentials are configured."""
        return bool(self.token and self.phone_number_id)

    def send_text_message(
        self, to_phone: str, message_body: str
    ) -> Tuple[bool, str]:
        """Send a standard text message to a recipient.

        Returns (success: bool, response_or_error: str).
        """
        formatted_recipient = normalize_phone_number(to_phone)

        log_entry = {
            "to": formatted_recipient,
            "raw_to": to_phone,
            "message": message_body,
            "status": "pending",
        }

        if not self.is_configured:
            logger.info(
                "[MOCK WHATSAPP] To: %s | Message:\n%s",
                formatted_recipient,
                message_body,
            )
            log_entry["status"] = "mock_delivered"
            RECENT_NOTIFICATIONS.append(log_entry)
            return (
                True,
                "Simulated WhatsApp message sent (running in mock mode).",
            )

        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": formatted_recipient,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message_body,
            },
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=12
            )
            resp_data = response.json()

            if response.status_code in (200, 201):
                msg_id = (
                    resp_data.get("messages", [{}])[0].get("id", "unknown")
                )
                logger.info(
                    "WhatsApp message sent to %s (ID: %s)",
                    formatted_recipient,
                    msg_id,
                )
                log_entry["status"] = "delivered"
                log_entry["id"] = msg_id
                RECENT_NOTIFICATIONS.append(log_entry)
                return True, f"WhatsApp sent successfully (ID: {msg_id})"
            else:
                err_msg = resp_data.get("error", {}).get(
                    "message", response.text
                )
                logger.error("WhatsApp API error (%d): %s", response.status_code, err_msg)
                log_entry["status"] = f"failed: {err_msg}"
                RECENT_NOTIFICATIONS.append(log_entry)
                return False, f"WhatsApp delivery error: {err_msg}"
        except Exception as e:
            logger.error("WhatsApp network exception: %s", e)
            log_entry["status"] = f"exception: {str(e)}"
            RECENT_NOTIFICATIONS.append(log_entry)
            return False, f"Failed to reach WhatsApp Cloud API: {str(e)}"

    def send_booking_confirmation(
        self,
        to_phone: str,
        resident_name: str,
        flat_no: str,
        date_str: str,
        slot_time: str,
    ) -> Tuple[bool, str]:
        """Send instant booking confirmation message to resident."""
        body = (
            "🙏 *Festival Pooja & Aarti Booking Confirmed!* 🙏\n\n"
            f"Dear *{resident_name}*,\n"
            f"Your booking for *{slot_time}* on *{date_str}* has been successfully confirmed.\n\n"
            "📍 *Booking Details:*\n"
            f"• *Flat No:* {flat_no}\n"
            f"• *Resident:* {resident_name}\n"
            f"• *Date:* {date_str}\n"
            f"• *Slot:* {slot_time}\n\n"
            "⏰ *Please arrive 10 minutes prior to the scheduled slot.*\n"
            "May the Divine bless you and your family!\n\n"
            "_Community Festival Organizing Committee_"
        )
        return self.send_text_message(to_phone, body)

    def send_cancellation_notification(
        self,
        to_phone: str,
        resident_name: str,
        flat_no: str,
        date_str: str,
        slot_time: str,
    ) -> Tuple[bool, str]:
        """Send cancellation alert to resident."""
        body = (
            "⚠️ *Pooja & Aarti Booking Cancelled*\n\n"
            f"Dear *{resident_name}*,\n"
            f"Your booking for *{slot_time}* on *{date_str}* (Flat {flat_no}) has been successfully cancelled.\n\n"
            "📍 *Cancellation Summary:*\n"
            f"• *Flat No:* {flat_no}\n"
            f"• *Date:* {date_str}\n"
            f"• *Slot:* {slot_time}\n"
            "• *Status:* Cancelled in Google Sheets ❌\n"
            "• *Calendar:* Event removed from Community Calendar 🗑️\n"
            "• *Slot Availability:* Reopened for other devotees 🟢\n\n"
            "Thank you for notifying the community.\n\n"
            "_Community Festival Organizing Committee_"
        )
        return self.send_text_message(to_phone, body)

    def send_daily_digest(
        self,
        date_str: str,
        schedule_items: List[Dict[str, Any]],
        admin_phone: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Dispatch daily 4:00 AM summary to Admin WhatsApp number."""
        target_phone = admin_phone or get_admin_whatsapp_number()
        if not target_phone:
            return (
                False,
                "ADMIN_WHATSAPP_NUMBER is not configured in settings or environment.",
            )

        lines = [f"🙏 *Pooja & Aarti Schedule for {date_str}*:", ""]

        booked_count = 0
        for item in schedule_items:
            time_label = item.get("time", "")
            name_label = item.get("name", "")
            booking = item.get("booking")

            if booking:
                booked_count += 1
                flat = booking.get("Flat_No", "")
                resident = booking.get("Resident_Name", "")
                mobile = booking.get("Mobile_No", "")
                lines.append(
                    f"• *{time_label}* ({name_label}): Flat {flat} - {resident} ({mobile})"
                )
            else:
                lines.append(f"• *{time_label}* ({name_label}): _Available_")

        lines.append("")
        lines.append(
            f"📊 *Summary:* {booked_count}/{len(schedule_items)} slots booked."
        )
        lines.append("_Automated Community Pooja Digest_")

        message_body = "\n".join(lines)
        return self.send_text_message(target_phone, message_body)


def get_recent_notifications() -> List[Dict[str, Any]]:
    """Return in-memory log of recent notifications."""
    return list(reversed(RECENT_NOTIFICATIONS[-20:]))
