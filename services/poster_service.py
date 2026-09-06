"""Poster generation service for Passiflora Ganesh Festival 2026.

Generates high-resolution, print-ready A4 PDF posters for any festival day,
showcasing the date, Hindu Vedic Tithi, and the resident families who have
booked the Morning and Evening Aarti slots.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from services.config import (
    FESTIVAL_NAME,
    FESTIVAL_SLOTS,
    HINDU_VEDIC_TITHIS,
    get_festival_dates,
)

logger = logging.getLogger(__name__)

# Register Unicode TrueType font if available on host system
_UNICODE_FONT_REGISTERED = False
_UNICODE_FONT_NAME = "DevanagariFestive"

CANDIDATE_FONTS = [
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/DevanagariMT.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
]

for fp in CANDIDATE_FONTS:
    if os.path.exists(fp):
        try:
            pdfmetrics.registerFont(TTFont(_UNICODE_FONT_NAME, fp))
            _UNICODE_FONT_REGISTERED = True
            break
        except Exception as font_err:
            logger.debug("Could not register font %s: %s", fp, font_err)


class PosterService:
    """Service to generate daily Aarti festival poster PDFs."""

    @staticmethod
    def generate_poster_pdf(
        date_str: str,
        bookings: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        """Generate A4 PDF poster bytes for a given festival date and bookings."""
        if bookings is None:
            bookings = []

        # Find day info from festival schedule
        festival_dates = get_festival_dates()
        day_info = next((d for d in festival_dates if d["date_str"] == date_str), None)

        if not day_info:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                weekday = dt.strftime("%A")
                date_display = dt.strftime("%d %B %Y")
            except Exception:
                weekday = "Auspicious Day"
                date_display = date_str
            day_num = 1
            tithi = HINDU_VEDIC_TITHIS.get(date_str, "Shukla Paksha")
        else:
            weekday = day_info["weekday"]
            date_display = day_info["date"].strftime("%d %B %Y")
            day_num = day_info["day_number"]
            tithi = day_info["tithi"]

        # Map active bookings by slot time
        slot_map: Dict[str, Dict[str, Any]] = {}
        for b in bookings:
            # Only count active (non-cancelled) bookings
            if b.get("Status", "").lower() != "cancelled":
                slot_map[b.get("Slot_Time", "")] = b

        buf = io.BytesIO()
        width, height = A4
        c = canvas.Canvas(buf, pagesize=A4)

        # ---------------------------------------------------------------------
        # 1. Background Fill & Double Festive Border
        # ---------------------------------------------------------------------
        # Warm cream background tint
        c.setFillColor(colors.HexColor("#FFFDF8"))
        c.rect(0, 0, width, height, fill=1, stroke=0)

        # Outer Crimson Border
        c.setStrokeColor(colors.HexColor("#D84315"))
        c.setLineWidth(4)
        c.rect(16, 16, width - 32, height - 32, fill=0, stroke=1)

        # Inner Gold Border
        c.setStrokeColor(colors.HexColor("#FFB300"))
        c.setLineWidth(1.5)
        c.rect(22, 22, width - 44, height - 44, fill=0, stroke=1)

        # Decorative Corner Flairs
        c.setStrokeColor(colors.HexColor("#D84315"))
        c.setLineWidth(1)
        for cx, cy in [
            (22, 22),
            (width - 22, 22),
            (22, height - 22),
            (width - 22, height - 22),
        ]:
            c.circle(cx, cy, 3, fill=1, stroke=0)

        # ---------------------------------------------------------------------
        # 2. Top Header Banner
        # ---------------------------------------------------------------------
        banner_height = 96
        banner_y = height - 25 - banner_height
        c.setFillColor(colors.HexColor("#D84315"))
        c.rect(25, banner_y, width - 50, banner_height, fill=1, stroke=0)

        # Gold accent stripe below banner
        c.setFillColor(colors.HexColor("#FFA000"))
        c.rect(25, banner_y - 3, width - 50, 3, fill=1, stroke=0)

        # Top Auspicious Chant
        if _UNICODE_FONT_REGISTERED:
            c.setFont(_UNICODE_FONT_NAME, 13)
            chant_str = "॥ गणपति बाप्पा मोरया • मंगलमूर्ती मोरया ॥"
        else:
            c.setFont("Helvetica-Bold", 12)
            chant_str = "GANPATI BAPPA MORYA • MANGALMURTI MORYA"

        c.setFillColor(colors.HexColor("#FFF8E1"))
        c.drawCentredString(width / 2.0, height - 52, chant_str)

        # Festival Main Title
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(colors.white)
        c.drawCentredString(width / 2.0, height - 80, FESTIVAL_NAME)

        # Header Subtitle
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(colors.HexColor("#FFE082"))
        c.drawCentredString(
            width / 2.0,
            height - 103,
            "DAILY AARTI SEVA & DEVOTEE YAJMAN ROSTER",
        )

        # ---------------------------------------------------------------------
        # 3. Embedded Ganpati Bappa Image
        # ---------------------------------------------------------------------
        img_path = Path("assets/ganpati_bappa.jpg")
        img_w, img_h = 135, 135
        img_x = (width - img_w) / 2.0
        img_y = banner_y - img_h - 16

        if img_path.exists():
            c.drawImage(
                str(img_path),
                img_x,
                img_y,
                width=img_w,
                height=img_h,
                preserveAspectRatio=True,
            )
            # Golden Frame around image
            c.setStrokeColor(colors.HexColor("#FFA000"))
            c.setLineWidth(2.5)
            c.rect(img_x - 1, img_y - 1, img_w + 2, img_h + 2, stroke=1, fill=0)

        # ---------------------------------------------------------------------
        # 4. Auspicious Date & Hindu Vedic Tithi Card
        # ---------------------------------------------------------------------
        tithi_card_y = img_y - 75
        tithi_card_h = 64
        tithi_card_w = width - 70
        tithi_card_x = 35

        # Card Background
        c.setFillColor(colors.HexColor("#FFF8E1"))
        c.roundRect(
            tithi_card_x,
            tithi_card_y,
            tithi_card_w,
            tithi_card_h,
            6,
            fill=1,
            stroke=0,
        )
        c.setStrokeColor(colors.HexColor("#FFB300"))
        c.setLineWidth(1.5)
        c.roundRect(
            tithi_card_x,
            tithi_card_y,
            tithi_card_w,
            tithi_card_h,
            6,
            fill=0,
            stroke=1,
        )

        # Date & Day Label
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.HexColor("#D84315"))
        date_line = f"📅 {weekday}, {date_display}  •  Day {day_num} of {len(festival_dates)}"
        c.drawCentredString(width / 2.0, tithi_card_y + 39, date_line)

        # Vedic Tithi Line
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#4E342E"))
        tithi_line = f"Vedic Tithi: {tithi}"
        c.drawCentredString(width / 2.0, tithi_card_y + 16, tithi_line)

        # ---------------------------------------------------------------------
        # 5. Aarti Slots & Devotee Family Roster
        # ---------------------------------------------------------------------
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(colors.HexColor("#D84315"))
        c.drawCentredString(
            width / 2.0,
            tithi_card_y - 24,
            "🪔 TODAY'S SACRED AARTI SEVA SCHEDULE 🪔",
        )

        slot_start_y = tithi_card_y - 40
        slot_card_h = 105
        slot_card_w = width - 70
        slot_card_x = 35

        for idx, slot in enumerate(FESTIVAL_SLOTS):
            slot_time = slot["time"]
            slot_name = slot["name"]
            card_top = slot_start_y - (idx * (slot_card_h + 16))
            card_y = card_top - slot_card_h

            booking = slot_map.get(slot_time)

            if booking:
                # Reserved Slot Styling (Crimson/Marigold Accent)
                c.setFillColor(colors.HexColor("#FFFFFF"))
                c.roundRect(
                    slot_card_x,
                    card_y,
                    slot_card_w,
                    slot_card_h,
                    8,
                    fill=1,
                    stroke=0,
                )
                c.setStrokeColor(colors.HexColor("#D84315"))
                c.setLineWidth(2)
                c.roundRect(
                    slot_card_x,
                    card_y,
                    slot_card_w,
                    slot_card_h,
                    8,
                    fill=0,
                    stroke=1,
                )

                # Left Accent Bar
                c.setFillColor(colors.HexColor("#D84315"))
                c.roundRect(
                    slot_card_x,
                    card_y,
                    12,
                    slot_card_h,
                    4,
                    fill=1,
                    stroke=0,
                )

                # Slot Name & Timing Header
                c.setFont("Helvetica-Bold", 14)
                c.setFillColor(colors.HexColor("#D84315"))
                c.drawString(
                    slot_card_x + 24,
                    card_y + slot_card_h - 24,
                    f"{slot['icon']} {slot_name}  —  {slot_time} ({slot['duration_minutes']} mins)",
                )

                # Status Badge
                c.setFillColor(colors.HexColor("#C62828"))
                badge_w = 110
                c.roundRect(
                    slot_card_x + slot_card_w - badge_w - 14,
                    card_y + slot_card_h - 28,
                    badge_w,
                    20,
                    10,
                    fill=1,
                    stroke=0,
                )
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(colors.white)
                c.drawCentredString(
                    slot_card_x + slot_card_w - (badge_w / 2.0) - 14,
                    card_y + slot_card_h - 22,
                    "RESERVED SEVA",
                )

                # Devotee Family Details
                resident = booking.get("Resident_Name", "Devotee Family")
                flat = booking.get("Flat_No", "N/A")

                # Family Name
                c.setFont("Helvetica-Bold", 14)
                c.setFillColor(colors.HexColor("#1A237E"))
                family_display = f"Aarti Seva by: {resident} & Family"
                c.drawString(slot_card_x + 24, card_y + 48, family_display)

                # Flat Number & Arrival Callout
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(colors.HexColor("#424242"))
                flat_display = f"🏢 Residence: Flat {flat}"
                c.drawString(slot_card_x + 24, card_y + 26, flat_display)

                c.setFont("Helvetica", 9.5)
                c.setFillColor(colors.HexColor("#757575"))
                c.drawString(
                    slot_card_x + 240,
                    card_y + 26,
                    "• Please assemble at pandal 10 mins prior",
                )

            else:
                # Open / Available Slot Styling (Green Accent)
                c.setFillColor(colors.HexColor("#F9FBE7"))
                c.roundRect(
                    slot_card_x,
                    card_y,
                    slot_card_w,
                    slot_card_h,
                    8,
                    fill=1,
                    stroke=0,
                )
                c.setStrokeColor(colors.HexColor("#2E7D32"))
                c.setLineWidth(1.5)
                c.roundRect(
                    slot_card_x,
                    card_y,
                    slot_card_w,
                    slot_card_h,
                    8,
                    fill=0,
                    stroke=1,
                )

                # Left Accent Bar
                c.setFillColor(colors.HexColor("#2E7D32"))
                c.roundRect(
                    slot_card_x,
                    card_y,
                    12,
                    slot_card_h,
                    4,
                    fill=1,
                    stroke=0,
                )

                # Slot Name & Timing Header
                c.setFont("Helvetica-Bold", 14)
                c.setFillColor(colors.HexColor("#2E7D32"))
                c.drawString(
                    slot_card_x + 24,
                    card_y + slot_card_h - 24,
                    f"{slot['icon']} {slot_name}  —  {slot_time} ({slot['duration_minutes']} mins)",
                )

                # Available Badge
                c.setFillColor(colors.HexColor("#2E7D32"))
                badge_w = 110
                c.roundRect(
                    slot_card_x + slot_card_w - badge_w - 14,
                    card_y + slot_card_h - 28,
                    badge_w,
                    20,
                    10,
                    fill=1,
                    stroke=0,
                )
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(colors.white)
                c.drawCentredString(
                    slot_card_x + slot_card_w - (badge_w / 2.0) - 14,
                    card_y + slot_card_h - 22,
                    "SLOT AVAILABLE",
                )

                # Open Callout
                c.setFont("Helvetica-Bold", 13)
                c.setFillColor(colors.HexColor("#33691E"))
                c.drawString(
                    slot_card_x + 24,
                    card_y + 48,
                    "✨ Available for Devotee Family Reservation",
                )

                c.setFont("Helvetica-Oblique", 10)
                c.setFillColor(colors.HexColor("#558B2F"))
                c.drawString(
                    slot_card_x + 24,
                    card_y + 26,
                    "Reserve this sacred Aarti slot via the Community Pooja Portal.",
                )

        # ---------------------------------------------------------------------
        # 6. Pandal Venue & Community Invitation Footer
        # ---------------------------------------------------------------------
        footer_h = 72
        footer_y = 26
        c.setFillColor(colors.HexColor("#FFF3E0"))
        c.rect(25, footer_y, width - 50, footer_h, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#FFA000"))
        c.setLineWidth(1)
        c.rect(25, footer_y, width - 50, footer_h, fill=0, stroke=1)

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor("#D84315"))
        c.drawCentredString(
            width / 2.0,
            footer_y + 48,
            "🌺 PANDAL VENUE: Passiflora Community Ganesh Pandal 🌺",
        )

        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(colors.HexColor("#4E342E"))
        c.drawCentredString(
            width / 2.0,
            footer_y + 30,
            "All society members, families and children are cordially invited for the Divine Aarti & Prasad.",
        )

        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#757575"))
        gen_timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        c.drawCentredString(
            width / 2.0,
            footer_y + 12,
            f"Passiflora Ganesh Festival Committee 2026  •  Generated on {gen_timestamp}",
        )

        c.save()
        return buf.getvalue()

    @classmethod
    def save_poster_pdf(
        cls,
        date_str: str,
        bookings: Optional[List[Dict[str, Any]]] = None,
        output_dir: str = "generated_posters",
    ) -> str:
        """Generate and save the poster PDF to local filesystem, returning filepath."""
        os.makedirs(output_dir, exist_ok=True)
        pdf_bytes = cls.generate_poster_pdf(date_str, bookings)
        file_path = os.path.join(
            output_dir, f"Passiflora_Ganesh_Poster_{date_str}.pdf"
        )
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
        return file_path
