"""Email notification service for dispatching daily Aarti posters.

Supports standard SMTP (e.g. Gmail SMTP) with TLS and automatic mock mode
when SMTP credentials are not configured.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple, Union

from services.config import (
    DEFAULT_POSTER_EMAIL,
    DEFAULT_POSTER_EMAILS,
    FESTIVAL_NAME,
    get_poster_notification_email,
    get_poster_notification_emails,
    get_smtp_settings,
)

logger = logging.getLogger(__name__)

# Recent in-memory email audit logs
RECENT_EMAIL_NOTIFICATIONS: List[Dict[str, Any]] = []


class EmailService:
    """Service to send festival email notifications with PDF poster attachments."""

    def __init__(self) -> None:
        self.smtp_settings = get_smtp_settings()

    @property
    def is_configured(self) -> bool:
        """Check if SMTP credentials are provided in settings."""
        return bool(self.smtp_settings.get("user") and self.smtp_settings.get("password"))

    def send_poster_email(
        self,
        date_str: str,
        pdf_bytes: bytes,
        to_email: Optional[Union[str, List[str]]] = None,
        tithi_str: str = "",
        bookings_summary: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[bool, str]:
        """Dispatch daily Aarti PDF poster to committee recipient(s).

        Supports single email string, comma-separated emails, or list of emails.
        Returns (success: bool, status_message: str).
        """
        recipients: List[str] = []
        if isinstance(to_email, list):
            recipients = [e.strip() for e in to_email if e and e.strip()]
        elif isinstance(to_email, str) and to_email.strip():
            recipients = [e.strip() for e in re.split(r"[,;]+", to_email) if e.strip()]

        if not recipients:
            recipients = get_poster_notification_emails()

        recipient_str = ", ".join(recipients)
        filename = f"Passiflora_Ganesh_Poster_{date_str}.pdf"

        # Construct Email Subject & Body
        subject = f"🌺 {FESTIVAL_NAME} - Aarti Booking Poster: {date_str}"
        if tithi_str:
            subject += f" ({tithi_str})"

        summary_lines = []
        if bookings_summary:
            for item in bookings_summary:
                slot_time = item.get("slot_time", "")
                slot_name = item.get("slot_name", "")
                family = item.get("family", "Available")
                flat = item.get("flat", "")
                if flat:
                    summary_lines.append(f"• {slot_name} ({slot_time}): Flat {flat} - {family}")
                else:
                    summary_lines.append(f"• {slot_name} ({slot_time}): {family}")

        summary_text = "\n".join(summary_lines) if summary_lines else "No bookings recorded yet."

        body_text = (
            f"🚩 ॥ गणपति बाप्पा मोरया • मंगलमूर्ती मोरया ॥ 🚩\n"
            f"Ganpati Bappa Morya! Mangalmurti Morya!\n\n"
            f"Dear Passiflora Ganesh Festival Committee,\n\n"
            f"Aarti slot bookings for {date_str} have been updated.\n"
            f"Vedic Tithi: {tithi_str or 'Auspicious Festival Day'}\n\n"
            f"📍 Daily Aarti Seva & Devotee Roster:\n"
            f"{summary_text}\n\n"
            f"Attached is the official high-resolution print-ready A4 PDF Poster for this festival date.\n"
            f"You may print this poster for the pandal notice board or broadcast it to society groups.\n\n"
            f"May Lord Ganesha bestow joy, peace, and auspicious blessings upon our entire community!\n\n"
            f"— Passiflora Ganesh Festival Committee 2026\n"
            f"Community Pooja & Aarti Portal"
        )

        log_entry = {
            "to": recipient_str,
            "recipients": recipients,
            "subject": subject,
            "filename": filename,
            "size_bytes": len(pdf_bytes),
            "status": "pending",
        }

        # Mock Mode handling
        if not self.is_configured:
            logger.info(
                "[MOCK EMAIL] To: %s | Subject: %s | Attached: %s (%d bytes)",
                recipient_str,
                subject,
                filename,
                len(pdf_bytes),
            )
            log_entry["status"] = "mock_delivered"
            RECENT_EMAIL_NOTIFICATIONS.append(log_entry)
            return (
                True,
                f"Simulated email with PDF poster dispatched to {recipient_str} (mock mode).",
            )

        # Real SMTP Delivery
        try:
            host = self.smtp_settings["host"]
            port = self.smtp_settings["port"]
            user = self.smtp_settings["user"]
            password = self.smtp_settings["password"]
            sender_name = self.smtp_settings.get("sender_name", "Passiflora Ganesh Festival Committee")
            from_email = self.smtp_settings.get("from_email") or user

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{from_email}>"
            msg["To"] = recipient_str

            # Attach Text Body
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

            # Attach PDF Poster
            attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename,
            )
            msg.attach(attachment)

            # Send via SMTP with TLS
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, password)
                server.send_message(msg, to_addrs=recipients)

            logger.info("Email with PDF poster successfully sent to %s", recipient_str)
            log_entry["status"] = "delivered"
            RECENT_EMAIL_NOTIFICATIONS.append(log_entry)
            return (
                True,
                f"Aarti PDF poster successfully emailed to {recipient_str}.",
            )

        except Exception as e:
            err_msg = str(e)
            logger.error("Failed to send email to %s: %s", recipient_str, err_msg)
            log_entry["status"] = f"failed: {err_msg}"
            RECENT_EMAIL_NOTIFICATIONS.append(log_entry)
            return (
                False,
                f"Failed to email PDF poster: {err_msg}",
            )


def get_recent_email_notifications() -> List[Dict[str, Any]]:
    """Return recent in-memory email notification logs."""
    return list(reversed(RECENT_EMAIL_NOTIFICATIONS[-20:]))
