"""Community Pooja & Aarti Booking Portal.

A full-stack Streamlit application for booking ritual slots during a 10-day community festival.
Persistent datastore: Google Sheets.
Calendar sync: Google Calendar.
Notifications: Meta WhatsApp Cloud API.
"""

from __future__ import annotations

import base64
from pathlib import Path
import re
import secrets
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from services.calendar_service import CalendarService
from services.config import (
    DEFAULT_POSTER_EMAIL,
    FESTIVAL_CHANT,
    FESTIVAL_NAME,
    FESTIVAL_SLOGAN,
    FESTIVAL_SLOTS,
    TIMEZONE_STR,
    get_admin_whatsapp_number,
    get_festival_dates,
    get_poster_notification_email,
    get_smtp_settings,
    is_mock_mode,
)
from services.email_service import EmailService, get_recent_email_notifications
from services.poster_service import PosterService
from services.sheets_service import SheetsService
from services.whatsapp_service import WhatsAppService, get_recent_notifications

# Page Configuration
st.set_page_config(
    page_title="Passiflora Ganesh Festival 2026 - Ganpati Bappa Morya",
    page_icon="🌺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    /* Festive Theme Styling */
    .festival-header {
        background: linear-gradient(135deg, #D84315 0%, #FF6F00 50%, #FFA000 100%);
        padding: 24px;
        border-radius: 14px;
        color: white;
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 4px 18px rgba(216, 67, 21, 0.25);
    }
    .festival-header h1 {
        color: white !important;
        font-size: 2.2rem;
        margin-bottom: 6px;
        font-weight: 800;
        letter-spacing: 0.5px;
    }
    .festival-header p {
        font-size: 1.1rem;
        color: #FFF3E0;
        margin-bottom: 0px;
    }
    .bappa-badge {
        display: inline-block;
        background: rgba(255, 255, 255, 0.2);
        border: 1.5px solid rgba(255, 248, 225, 0.7);
        padding: 5px 16px;
        border-radius: 22px;
        font-size: 1.2rem;
        font-weight: 800;
        color: #FFF8E1;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
        text-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .slot-card {
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 16px;
        background: #FFFFFF;
        border-left: 6px solid #D84315;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    }
    .slot-card-available {
        border-left-color: #2E7D32 !important;
        background: #F1F8E9;
    }
    .slot-card-booked {
        border-left-color: #C62828 !important;
        background: #FFEBEE;
    }
    .badge-available {
        background-color: #2E7D32;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-booked {
        background-color: #C62828;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    .tithi-card {
        background: #FFF8E1;
        border: 1px solid #FFE082;
        border-left: 6px solid #FF8F00;
        padding: 14px 18px;
        border-radius: 8px;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_services() -> tuple[SheetsService, CalendarService, WhatsAppService, EmailService]:
    """Cache service instances to reuse across reruns."""
    sheets = SheetsService()
    calendar = CalendarService()
    whatsapp = WhatsAppService()
    email = EmailService()
    return sheets, calendar, whatsapp, email


@st.cache_data
def get_bappa_image_base64() -> str:
    """Encode Ganpati Bappa image as base64 string for embedding in header."""
    img_path = Path("assets/ganpati_bappa.jpg")
    if img_path.exists():
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""


def validate_mobile(number: str) -> bool:
    """Validate 10-digit mobile number."""
    digits = re.sub(r"\D", "", number)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return len(digits) == 10 and digits[0] in "6789"


def main() -> None:
    sheets_service, calendar_service, whatsapp_service, email_service = get_services()
    festival_dates = get_festival_dates()

    # Sidebar
    with st.sidebar:
        # Divine Ganpati Bappa Image in Sidebar
        img_path = Path("assets/ganpati_bappa.jpg")
        if img_path.exists():
            st.image(str(img_path), caption="🙏 गणपति बाप्पा मोरया • मंगलमूर्ती मोरया 🙏")

        st.markdown("### 🌺 Festival Information")
        st.markdown(
            f"**Passiflora Ganesh Festival 2026**\n\n"
            f"🚩 **Ganpati Bappa Morya!**\n\n"
            f"📅 **Celebration Dates:**\n14th Sep to 25th Sep 2026\n\n"
            f"🪔 **Duration:** {len(festival_dates)} Auspicious Days\n\n"
            f"⏰ **Daily Rituals:** 2 Aartis Daily"
        )
        st.markdown("---")

        # Mode Indicator
        if is_mock_mode():
            st.warning("⚠️ **Running in Mock Mode**\nExternal API keys are unconfigured. Using simulated local storage, calendar, and WhatsApp logger.")
        else:
            st.success("✅ **Live Cloud Connected**\nGoogle Sheets, Google Calendar, and WhatsApp Cloud API active.")

        st.markdown("---")
        st.markdown("### 📋 Daily Aarti Schedule")
        for s in FESTIVAL_SLOTS:
            st.markdown(f"- **{s['time']}**: {s['icon']} {s['name']} ({s['duration_minutes']} min)")

        st.markdown("---")
        st.caption("Passiflora Ganesh Festival Committee • Developed for Devotee Booking")

    # Banner Header with Divine Ganpati Bappa Image & Chant
    bappa_b64 = get_bappa_image_base64()
    bappa_img_tag = ""
    if bappa_b64:
        bappa_img_tag = (
            '<div style="flex-shrink: 0;">'
            f'<img src="data:image/jpeg;base64,{bappa_b64}" '
            'style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 4px solid #FFE082; box-shadow: 0 4px 16px rgba(0,0,0,0.35);" '
            'alt="Ganpati Bappa Morya" />'
            '</div>'
        )

    header_html = (
        '<div class="festival-header">'
        '<div style="display: flex; align-items: center; justify-content: center; gap: 22px; flex-wrap: wrap; text-align: center;">'
        f'{bappa_img_tag}'
        '<div style="text-align: center;">'
        '<div class="bappa-badge">🚩 ॥ गणपति बाप्पा मोरया • मंगलमूर्ती मोरया ॥ 🚩</div>'
        '<h1 style="color: white !important; font-size: 2.2rem; margin: 0 0 6px 0; font-weight: 800;">🌺 Passiflora Ganesh Festival 2026 🪔</h1>'
        '<p style="margin: 0; font-size: 1.1rem; color: #FFF3E0; font-weight: 500;">Community Daily Morning & Evening Aarti Booking Portal • 14th Sep to 25th Sep 2026</p>'
        '<div style="margin-top: 8px; font-size: 1.15rem; color: #FFE082; font-weight: 800; letter-spacing: 0.5px;">🙏 Ganpati Bappa Morya! Mangal Murti Morya! 🙏</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # Navigation Tabs
    tab_book, tab_cancel, tab_overview, tab_admin = st.tabs([
        "📅 Book an Aarti Slot",
        "🔍 My Bookings & Cancellation",
        "📊 12-Day Festival Matrix",
        "⚙️ Admin & Daily Digest",
    ])

    # =========================================================================
    # TAB 1: SLOT CATALOG & BOOKING FLOW
    # =========================================================================
    with tab_book:
        # Check if booking just completed and show celebratory confirmation + poster download
        if "just_booked_poster" in st.session_state:
            post_info = st.session_state.pop("just_booked_poster")
            st.balloons()
            st.success(
                f"🎉 **Ganpati Bappa Morya! Booking Confirmed!**\n\n"
                f"**Flat {post_info['flat_no']}** ({post_info['resident_name']}) is successfully registered for **{post_info['slot_name']} ({post_info['slot_time']})** on **{post_info['date_str']}**."
            )
            if post_info.get("email_ok"):
                st.info(f"📧 **Aarti PDF Poster Generated & Auto-Emailed** to `{post_info['email_target']}`.")
            else:
                st.warning(f"⚠️ Email dispatch notice: {post_info.get('email_msg')}")

            st.download_button(
                label=f"📄 Download Aarti Poster for {post_info['date_str']} (PDF)",
                data=post_info["pdf_bytes"],
                file_name=f"Passiflora_Ganesh_Poster_{post_info['date_str']}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="btn_download_just_booked_poster",
            )
            st.markdown("---")

        st.markdown("#### Step 1: Select Festival Date (14th Sep – 25th Sep 2026)")

        # Date selector
        date_options = {d["date_str"]: d["display_label"] for d in festival_dates}
        selected_date_str = st.selectbox(
            "Choose Festival Date & Hindu Vedic Tithi:",
            options=list(date_options.keys()),
            format_func=lambda x: date_options[x],
            index=0,
            key="book_selected_date",
        )

        selected_day_info = next(d for d in festival_dates if d["date_str"] == selected_date_str)

        # Prominent Vedic Tithi Highlight Box
        tithi_html = (
            '<div class="tithi-card">'
            '<div style="display: flex; justify-content: space-between; align-items: center;">'
            f'<span style="font-size: 1.15rem; font-weight: 700; color: #D84315;">🪔 Vedic Tithi: {selected_day_info["tithi"]}</span>'
            f'<span style="background: #FFE082; color: #5D4037; font-weight: 700; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem;">Day {selected_day_info["day_number"]} of {len(festival_dates)}</span>'
            '</div>'
            f'<p style="margin-top: 6px; margin-bottom: 0; color: #6D4C41; font-size: 0.95rem;">'
            f'📅 <strong>{selected_day_info["weekday"]}, {selected_day_info["date"].strftime("%d %B %Y")}</strong> • Passiflora Community Ganesh Pandal'
            '</p>'
            '</div>'
        )
        st.markdown(tithi_html, unsafe_allow_html=True)

        # Get active bookings for this date
        day_bookings = sheets_service.get_bookings_for_date(selected_date_str)
        booked_slot_map = {b.get("Slot_Time"): b for b in day_bookings}

        # Day Stats Bar
        total_slots = len(FESTIVAL_SLOTS)
        booked_count = len(day_bookings)
        avail_count = total_slots - booked_count

        stat_c1, stat_c2, stat_c3 = st.columns(3)
        stat_c1.metric("Selected Date", f"{selected_day_info['short_label']}")
        stat_c2.metric("Available Aartis", f"{avail_count} / {total_slots}", delta=f"{avail_count} free")
        stat_c3.metric("Booked Aartis", f"{booked_count} / {total_slots}")

        # Daily Aarti Poster Preview & Download Option
        with st.expander(f"📄 View & Download Aarti Poster for {selected_day_info['short_label']} (PDF)", expanded=False):
            st.write(
                f"Generate the official celebration poster for **{selected_day_info['display_label']}** "
                f"featuring Lord Ganesha, Vedic Tithi, and the resident families offering Aarti Seva."
            )
            p_col1, p_col2 = st.columns([1, 1])
            with p_col1:
                day_poster_bytes = PosterService.generate_poster_pdf(selected_date_str, day_bookings)
                st.download_button(
                    label="📥 Download A4 Poster (PDF)",
                    data=day_poster_bytes,
                    file_name=f"Passiflora_Ganesh_Poster_{selected_date_str}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"dl_poster_btn_{selected_date_str}",
                )
            with p_col2:
                poster_target_input = st.text_input(
                    "Send poster to email:",
                    value=get_poster_notification_email(),
                    key=f"email_target_in_{selected_date_str}",
                )
                if st.button("✉️ Email Poster", key=f"send_poster_btn_{selected_date_str}", use_container_width=True):
                    with st.spinner("Dispatching poster email..."):
                        p_summary = []
                        for s in FESTIVAL_SLOTS:
                            b_m = booked_slot_map.get(s["time"])
                            if b_m:
                                p_summary.append({
                                    "slot_time": s["time"],
                                    "slot_name": s["name"],
                                    "flat": b_m.get("Flat_No", ""),
                                    "family": f"{b_m.get('Resident_Name')} & Family",
                                })
                            else:
                                p_summary.append({
                                    "slot_time": s["time"],
                                    "slot_name": s["name"],
                                    "flat": "",
                                    "family": "Available for Devotee Reservation",
                                })

                        em_ok, em_msg = email_service.send_poster_email(
                            date_str=selected_date_str,
                            pdf_bytes=day_poster_bytes,
                            to_email=poster_target_input.strip(),
                            tithi_str=selected_day_info["tithi"],
                            bookings_summary=p_summary,
                        )
                        if em_ok:
                            st.success(f"✅ Aarti poster emailed to {poster_target_input.strip()}!")
                        else:
                            st.error(f"Failed to email poster: {em_msg}")

        st.markdown("---")
        st.markdown("#### Step 2: Daily Aarti Availability & Reservation (Morning & Evening)")

        # Render 2 Slot Cards (Morning Aarti & Evening Aarti)
        cols = st.columns(len(FESTIVAL_SLOTS))
        for idx, slot_def in enumerate(FESTIVAL_SLOTS):
            slot_time = slot_def["time"]
            slot_name = slot_def["name"]
            slot_icon = slot_def["icon"]
            duration = slot_def["duration_minutes"]

            booking = booked_slot_map.get(slot_time)
            is_booked = booking is not None

            with cols[idx]:
                if is_booked:
                    flat_num = booking.get("Flat_No", "")
                    resident = booking.get("Resident_Name", "")
                    card_html = (
                        '<div class="slot-card slot-card-booked">'
                        '<span class="badge-booked">🔴 BOOKED</span>'
                        f'<h3 style="margin-top: 10px; margin-bottom: 4px;">{slot_icon} {slot_name}</h3>'
                        f'<p style="font-size: 1.1rem; font-weight: 600; color: #555; margin-bottom: 8px;">⏰ {slot_time} ({duration} mins)</p>'
                        '<div style="background: white; padding: 10px; border-radius: 6px; border: 1px solid #FFCDD2;">'
                        '<strong>Reserved by:</strong><br>'
                        f'🏢 Flat {flat_num}<br>'
                        f'👤 {resident}'
                        '</div>'
                        '</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
                    st.button(
                        f"🔒 Unavailable ({slot_time})",
                        key=f"btn_disabled_{idx}_{selected_date_str}",
                        disabled=True,
                        use_container_width=True,
                    )
                else:
                    card_html = (
                        '<div class="slot-card slot-card-available">'
                        '<span class="badge-available">🟢 AVAILABLE</span>'
                        f'<h3 style="margin-top: 10px; margin-bottom: 4px;">{slot_icon} {slot_name}</h3>'
                        f'<p style="font-size: 1.1rem; font-weight: 600; color: #2E7D32; margin-bottom: 8px;">⏰ {slot_time} ({duration} mins)</p>'
                        '<p style="color: #4CAF50; font-weight: 500; font-size: 0.9rem;">✨ Open for devotee reservation</p>'
                        '</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)

                    with st.expander(f"👉 Reserve {slot_name} ({slot_time})", expanded=False):
                        with st.form(key=f"form_booking_{idx}_{selected_date_str}"):
                            st.markdown(f"##### Reserve for {slot_name} on {selected_date_str}")
                            flat_no_in = st.text_input(
                                "Flat Number (e.g., A-402, 301):",
                                placeholder="e.g. 402",
                                key=f"flat_{idx}_{selected_date_str}",
                            )
                            resident_name_in = st.text_input(
                                "Resident Full Name:",
                                placeholder="e.g. Ramesh Kumar",
                                key=f"name_{idx}_{selected_date_str}",
                            )
                            mobile_in = st.text_input(
                                "WhatsApp Mobile Number (10 digits):",
                                placeholder="e.g. 9876543210",
                                max_chars=13,
                                key=f"mobile_{idx}_{selected_date_str}",
                            )
                            agree_check = st.checkbox(
                                "I confirm my family will arrive 10 minutes prior to the ritual.",
                                key=f"agree_{idx}_{selected_date_str}",
                            )

                            submit_book = st.form_submit_button(
                                "🙏 Confirm Booking",
                                type="primary",
                                use_container_width=True,
                            )

                            if submit_book:
                                # Validation
                                if not flat_no_in.strip():
                                    st.error("Please provide your Flat Number.")
                                elif not resident_name_in.strip():
                                    st.error("Please provide your Resident Name.")
                                elif not validate_mobile(mobile_in):
                                    st.error("Please provide a valid 10-digit Indian Mobile Number (e.g. 9876543210).")
                                elif not agree_check:
                                    st.warning("Please acknowledge the arrival timing condition.")
                                else:
                                    with st.spinner("Confirming reservation with Google Sheets & Calendar..."):
                                        # 1. Google Calendar Event Creation
                                        gcal_event_id = calendar_service.create_event(
                                            date_str=selected_date_str,
                                            slot_time=slot_time,
                                            flat_no=flat_no_in,
                                            resident_name=resident_name_in,
                                            mobile_no=mobile_in,
                                        ) or ""

                                        # 2. Atomic Google Sheets Booking
                                        success, msg = sheets_service.create_booking(
                                            date_str=selected_date_str,
                                            slot_time=slot_time,
                                            flat_no=flat_no_in,
                                            resident_name=resident_name_in,
                                            mobile_no=mobile_in,
                                            gcal_event_id=gcal_event_id,
                                        )

                                        if success:
                                            # 3. WhatsApp Notification
                                            wa_ok, wa_msg = whatsapp_service.send_booking_confirmation(
                                                to_phone=mobile_in,
                                                resident_name=resident_name_in,
                                                flat_no=flat_no_in,
                                                date_str=selected_date_str,
                                                slot_time=slot_time,
                                            )

                                            # 4. Generate Daily Aarti PDF Poster & Auto-Email
                                            fresh_day_bookings = sheets_service.get_bookings_for_date(selected_date_str)
                                            poster_pdf_bytes = PosterService.generate_poster_pdf(
                                                date_str=selected_date_str,
                                                bookings=fresh_day_bookings,
                                            )

                                            # Prepare Summary for Email Body
                                            email_summary = []
                                            for s in FESTIVAL_SLOTS:
                                                b_match = next((b for b in fresh_day_bookings if b.get("Slot_Time") == s["time"] and b.get("Status", "").lower() != "cancelled"), None)
                                                if b_match:
                                                    email_summary.append({
                                                        "slot_time": s["time"],
                                                        "slot_name": s["name"],
                                                        "flat": b_match.get("Flat_No", ""),
                                                        "family": f"{b_match.get('Resident_Name')} & Family",
                                                    })
                                                else:
                                                    email_summary.append({
                                                        "slot_time": s["time"],
                                                        "slot_name": s["name"],
                                                        "flat": "",
                                                        "family": "Available for Devotee Reservation",
                                                    })

                                            target_email = get_poster_notification_email()
                                            email_ok, email_msg = email_service.send_poster_email(
                                                date_str=selected_date_str,
                                                pdf_bytes=poster_pdf_bytes,
                                                to_email=target_email,
                                                tithi_str=selected_day_info["tithi"],
                                                bookings_summary=email_summary,
                                            )

                                            st.session_state["just_booked_poster"] = {
                                                "date_str": selected_date_str,
                                                "slot_name": slot_name,
                                                "slot_time": slot_time,
                                                "flat_no": flat_no_in,
                                                "resident_name": resident_name_in,
                                                "mobile_no": mobile_in,
                                                "pdf_bytes": poster_pdf_bytes,
                                                "email_target": target_email,
                                                "email_ok": email_ok,
                                                "email_msg": email_msg,
                                            }

                                            st.rerun()
                                        else:
                                            # Rollback GCal event if sheet booking collided
                                            if gcal_event_id:
                                                calendar_service.delete_event(gcal_event_id)
                                            st.error(f"❌ Could not complete booking: {msg}")

    # =========================================================================
    # TAB 2: CANCELLATION FLOW
    # =========================================================================
    with tab_cancel:
        st.markdown("#### 🔍 Find Your Active Bookings")
        st.write("Enter your **Flat Number** or **10-digit WhatsApp Mobile Number** to locate and manage your bookings.")

        search_col, btn_col = st.columns([4, 1])
        with search_col:
            search_query = st.text_input(
                "Search query:",
                placeholder="Enter Flat Number (e.g. 402, A-402) or 10-digit WhatsApp Mobile...",
                key="cancel_search_query",
                label_visibility="collapsed",
            )
        with btn_col:
            do_search = st.button("🔍 Search", type="primary", use_container_width=True)

        if search_query.strip():
            active_results = sheets_service.find_active_bookings(search_query.strip())

            if not active_results:
                st.warning(f"No active bookings found for '{search_query.strip()}'. Please check your flat or mobile number.")
            else:
                st.success(f"Found {len(active_results)} active booking(s):")

                for b_idx, b in enumerate(active_results):
                    c_date = b.get("Date", "")
                    c_slot = b.get("Slot_Time", "")
                    c_flat = b.get("Flat_No", "")
                    c_name = b.get("Resident_Name", "")
                    c_phone = b.get("Mobile_No", "")
                    c_gcal = b.get("GCal_Event_ID", "")
                    c_created = b.get("Created_At", "")
                    booking_key = f"{c_date}_{c_slot}_{c_flat}"
                    masked_phone = f"******{c_phone[-4:]}" if len(c_phone) >= 4 else c_phone

                    with st.container():
                        booking_card_html = (
                            '<div style="background: white; border: 1px solid #FFCCBC; border-radius: 8px; padding: 18px; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);">'
                            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
                            f'<h4 style="margin: 0; color: #D84315;">🪔 {c_slot} on {c_date}</h4>'
                            '<span class="badge-booked">Active Booking</span>'
                            '</div>'
                            f'<p style="margin-bottom: 6px; font-size: 1rem;">'
                            f'🏢 <strong>Flat:</strong> {c_flat} &nbsp;|&nbsp; '
                            f'👤 <strong>Resident:</strong> {c_name} &nbsp;|&nbsp; '
                            f'📱 <strong>WhatsApp:</strong> {masked_phone}'
                            '</p>'
                            f'<p style="font-size: 0.85rem; color: #757575; margin-bottom: 0;">'
                            f'🗓️ <strong>Calendar Event:</strong> {c_gcal or "Pending Sync"} &nbsp;|&nbsp; '
                            f'🕒 <strong>Booked at:</strong> {c_created}'
                            '</p>'
                            '</div>'
                        )
                        st.markdown(booking_card_html, unsafe_allow_html=True)

                        active_otp = st.session_state.get("cancellation_otp")
                        is_otp_for_this_booking = active_otp and active_otp.get("booking_key") == booking_key

                        if not is_otp_for_this_booking:
                            _, cancel_col2 = st.columns([2, 2])
                            with cancel_col2:
                                req_otp = st.button(
                                    f"🔐 Request WhatsApp OTP to Cancel",
                                    key=f"otp_req_btn_{b_idx}_{booking_key}",
                                    type="secondary",
                                    use_container_width=True,
                                    help=f"Sends a 4-digit verification code to WhatsApp number {masked_phone} to verify identity.",
                                )

                            if req_otp:
                                otp_code = f"{secrets.randbelow(9000) + 1000}"
                                st.session_state["cancellation_otp"] = {
                                    "booking_key": booking_key,
                                    "otp": otp_code,
                                    "expires_at": time.time() + 300,
                                    "phone": c_phone,
                                    "name": c_name,
                                    "flat": c_flat,
                                    "date": c_date,
                                    "slot": c_slot,
                                    "gcal_id": c_gcal,
                                }
                                with st.spinner(f"Dispatching 4-digit verification OTP to WhatsApp {masked_phone}..."):
                                    whatsapp_service.send_cancellation_otp(
                                        to_phone=c_phone,
                                        otp=otp_code,
                                        resident_name=c_name,
                                        flat_no=c_flat,
                                        date_str=c_date,
                                        slot_time=c_slot,
                                    )
                                st.success(f"📲 4-digit verification OTP sent to WhatsApp `{masked_phone}`! Please enter it below.")
                                st.rerun()
                        else:
                            # OTP Verification Form
                            st.info(f"📲 **Security Verification:** Enter the 4-digit OTP sent to WhatsApp `{masked_phone}` to confirm cancellation.")
                            if is_mock_mode():
                                st.warning(f"🧪 **Mock Mode Hint:** Your verification OTP is **{active_otp['otp']}**")

                            with st.form(key=f"verify_otp_form_{b_idx}_{booking_key}"):
                                otp_input = st.text_input(
                                    "Enter 4-Digit WhatsApp OTP:",
                                    max_chars=4,
                                    placeholder="e.g. 5821",
                                    key=f"otp_input_{b_idx}_{booking_key}",
                                )
                                v_col1, v_col2 = st.columns(2)
                                with v_col1:
                                    verify_btn = st.form_submit_button(
                                        "✅ Verify & Cancel Booking",
                                        type="primary",
                                        use_container_width=True,
                                    )
                                with v_col2:
                                    dismiss_btn = st.form_submit_button(
                                        "❌ Dismiss",
                                        use_container_width=True,
                                    )

                                if dismiss_btn:
                                    del st.session_state["cancellation_otp"]
                                    st.rerun()

                                if verify_btn:
                                    if time.time() > active_otp.get("expires_at", 0):
                                        st.error("⏳ This OTP has expired. Please request a new OTP.")
                                    elif otp_input.strip() != active_otp.get("otp"):
                                        st.error("❌ Invalid OTP! Please check the 4-digit code sent to your WhatsApp number.")
                                    else:
                                        with st.spinner("Verifying OTP and executing cancellation across Sheets, Calendar & WhatsApp..."):
                                            # 1. Mark Cancelled & delete Calendar Event ID from Google Sheets
                                            success, msg, gcal_id = sheets_service.cancel_booking(
                                                date_str=c_date,
                                                slot_time=c_slot,
                                                flat_or_mobile=c_phone or c_flat,
                                            )

                                            if success:
                                                # 2. Delete Event from Google Calendar
                                                del_id = gcal_id or c_gcal
                                                if del_id:
                                                    calendar_service.delete_event(del_id)

                                                # 3. Dispatch WhatsApp cancellation alert
                                                whatsapp_service.send_cancellation_notification(
                                                    to_phone=c_phone,
                                                    resident_name=c_name,
                                                    flat_no=c_flat,
                                                    date_str=c_date,
                                                    slot_time=c_slot,
                                                )

                                                # Clear session OTP state
                                                del st.session_state["cancellation_otp"]

                                                st.success(
                                                    f"✅ **Booking Verified & Cancelled Successfully!**\n"
                                                    f"- Status marked as **Cancelled** in Google Sheets\n"
                                                    f"- Calendar Event removed\n"
                                                    f"- Cancellation confirmation sent to `{c_phone}`"
                                                )
                                                st.rerun()
                                            else:
                                                st.error(f"Failed to cancel booking: {msg}")

    # =========================================================================
    # TAB 3: 12-DAY FESTIVAL GRID & STATS
    # =========================================================================
    with tab_overview:
        st.markdown("#### 📊 Passiflora Ganesh Festival 2026 - 12-Day Aarti Matrix")
        all_bookings = sheets_service.get_all_bookings()
        active_bookings = [b for b in all_bookings if str(b.get("Status", "")).strip().lower() == "booked"]

        # High-level Metrics
        total_possible_slots = len(festival_dates) * len(FESTIVAL_SLOTS)
        total_active_booked = len(active_bookings)
        total_remaining = total_possible_slots - total_active_booked
        fill_rate = (total_active_booked / total_possible_slots) * 100 if total_possible_slots else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Aarti Slots", total_possible_slots)
        m2.metric("Aartis Reserved", total_active_booked)
        m3.metric("Aartis Available", total_remaining)
        m4.metric("Occupancy Rate", f"{fill_rate:.1f}%")

        st.markdown("---")

        # Build comprehensive table view with Hindu Vedic Tithi
        matrix_rows = []
        for d in festival_dates:
            d_str = d["date_str"]
            d_bookings = {
                b.get("Slot_Time"): b
                for b in active_bookings
                if str(b.get("Date", "")).strip() == d_str
            }

            row_dict = {
                "Festival Day": f"Day {d['day_number']} ({d['weekday']})",
                "Date": d_str,
                "Hindu Vedic Tithi": d["tithi"],
            }

            for s in FESTIVAL_SLOTS:
                s_label = f"{s['icon']} {s['name']} ({s['time']})"
                b = d_bookings.get(s["time"])
                if b:
                    row_dict[s_label] = f"🔴 Flat {b.get('Flat_No')} ({b.get('Resident_Name')})"
                else:
                    row_dict[s_label] = "🟢 Available"

            matrix_rows.append(row_dict)

        st.dataframe(
            matrix_rows,
            use_container_width=True,
            hide_index=True,
        )

    # =========================================================================
    # TAB 4: ADMIN & 4:00 AM DAILY DIGEST TRIGGER
    # =========================================================================
    with tab_admin:
        st.markdown("#### ⚙️ Admin Tools & 4:00 AM Daily Summary Dispatcher")
        st.write("The 4:00 AM daily summary script runs automatically via GitHub Actions / cron. Use this panel to test the digest or inspect recent system notifications.")

        admin_phone = get_admin_whatsapp_number()
        st.info(f"📲 **Configured Admin WhatsApp:** `{admin_phone or 'Not configured (set ADMIN_WHATSAPP_NUMBER)'}`")

        test_col1, test_col2 = st.columns(2)
        with test_col1:
            target_digest_date = st.date_input(
                "Select Date for Summary Preview:",
                value=datetime.strptime(festival_dates[0]["date_str"], "%Y-%m-%d").date(),
                key="admin_digest_date",
            )
        with test_col2:
            st.write("")
            st.write("")
            send_test_digest = st.button("📤 Send Daily Digest Now", type="primary", use_container_width=True)

        target_date_str = target_digest_date.strftime("%Y-%m-%d")

        # Compile preview
        day_bookings = sheets_service.get_bookings_for_date(target_date_str)
        slot_map = {b.get("Slot_Time"): b for b in day_bookings}
        schedule_items = []
        for s in FESTIVAL_SLOTS:
            schedule_items.append({
                "time": s["time"],
                "name": s["name"],
                "booking": slot_map.get(s["time"]),
            })

        if send_test_digest:
            with st.spinner(f"Dispatching summary for {target_date_str} to admin WhatsApp..."):
                ok, res_msg = whatsapp_service.send_daily_digest(
                    date_str=target_date_str,
                    schedule_items=schedule_items,
                    admin_phone=admin_phone,
                )
                if ok:
                    st.success(f"✅ Daily digest message dispatched! {res_msg}")
                else:
                    st.error(f"Failed to send daily digest: {res_msg}")

        # Live WhatsApp Notification Log
        st.markdown("---")
        st.markdown("##### 📜 Recent WhatsApp Notifications (Audit Log)")
        recent_notifs = get_recent_notifications()
        if recent_notifs:
            for notif in recent_notifs:
                with st.expander(f"To: {notif.get('to')} | Status: {notif.get('status')}"):
                    st.code(notif.get("message", ""), language="text")
        else:
            st.caption("No WhatsApp notifications sent yet in this session.")

        # Poster Generator Section
        st.markdown("---")
        st.markdown("##### 📄 Daily Aarti Poster Generator & Committee Email Dispatch")
        st.write("Generate and download print-ready A4 PDF posters for any festival date or dispatch via email to committee members.")

        p_col1, p_col2 = st.columns(2)
        with p_col1:
            admin_poster_date = st.date_input(
                "Select Date for Aarti Poster:",
                value=datetime.strptime(festival_dates[0]["date_str"], "%Y-%m-%d").date(),
                key="admin_poster_date_input",
            )
        with p_col2:
            admin_target_email = st.text_input(
                "Target Email Address:",
                value=get_poster_notification_email(),
                key="admin_poster_email_input",
            )

        admin_poster_date_str = admin_poster_date.strftime("%Y-%m-%d")
        admin_day_bookings = sheets_service.get_bookings_for_date(admin_poster_date_str)
        admin_pdf_bytes = PosterService.generate_poster_pdf(admin_poster_date_str, admin_day_bookings)

        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            st.download_button(
                label=f"📥 Download A4 Poster ({admin_poster_date_str})",
                data=admin_pdf_bytes,
                file_name=f"Passiflora_Ganesh_Poster_{admin_poster_date_str}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"admin_dl_poster_{admin_poster_date_str}",
            )
        with btn_c2:
            if st.button("✉️ Dispatch Poster Email", use_container_width=True, key="admin_send_poster_email_btn"):
                with st.spinner("Dispatching Aarti poster email..."):
                    day_tithi = HINDU_VEDIC_TITHIS.get(admin_poster_date_str, "Auspicious Festival Day")
                    em_ok, em_msg = email_service.send_poster_email(
                        date_str=admin_poster_date_str,
                        pdf_bytes=admin_pdf_bytes,
                        to_email=admin_target_email.strip(),
                        tithi_str=day_tithi,
                    )
                    if em_ok:
                        st.success(f"✅ Aarti poster successfully emailed to {admin_target_email.strip()}!")
                    else:
                        st.error(f"Failed to email poster: {em_msg}")

        # Live Email Notification Log
        st.markdown("---")
        st.markdown("##### 📬 Recent Poster Email Dispatches (Audit Log)")
        recent_emails = get_recent_email_notifications()
        if recent_emails:
            for em in recent_emails:
                st.caption(f"📧 **To:** `{em.get('to')}` | **Subject:** `{em.get('subject')}` | **Attachment:** `{em.get('filename')}` ({em.get('size_bytes', 0) // 1024} KB) | **Status:** `{em.get('status')}`")
        else:
            st.caption(f"No emails dispatched yet in this session. Default auto-dispatch target: `{get_poster_notification_email()}`.")


if __name__ == "__main__":
    main()
