"""Community Pooja & Aarti Booking Portal.

A full-stack Streamlit application for booking ritual slots during a 10-day community festival.
Persistent datastore: Google Sheets.
Calendar sync: Google Calendar.
Notifications: Meta WhatsApp Cloud API.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from services.calendar_service import CalendarService
from services.config import (
    FESTIVAL_SLOTS,
    TIMEZONE_STR,
    get_admin_whatsapp_number,
    get_festival_dates,
    is_mock_mode,
)
from services.sheets_service import SheetsService
from services.whatsapp_service import WhatsAppService, get_recent_notifications

# Page Configuration
st.set_page_config(
    page_title="Community Pooja & Aarti Portal",
    page_icon="🪔",
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
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 4px 15px rgba(216, 67, 21, 0.2);
    }
    .festival-header h1 {
        color: white !important;
        font-size: 2.2rem;
        margin-bottom: 6px;
        font-weight: 700;
    }
    .festival-header p {
        font-size: 1.05rem;
        color: #FFF3E0;
        margin-bottom: 0px;
    }
    .slot-card {
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 16px;
        background: #FFFFFF;
        border-left: 6px solid #D84315;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
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
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-booked {
        background-color: #C62828;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    .metric-card {
        background: white;
        border: 1px solid #FFE0B2;
        padding: 14px;
        border-radius: 8px;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_services() -> tuple[SheetsService, CalendarService, WhatsAppService]:
    """Cache service instances to reuse across reruns."""
    sheets = SheetsService()
    calendar = CalendarService()
    whatsapp = WhatsAppService()
    return sheets, calendar, whatsapp


def validate_mobile(number: str) -> bool:
    """Validate 10-digit mobile number."""
    digits = re.sub(r"\D", "", number)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return len(digits) == 10 and digits[0] in "6789"


def main() -> None:
    sheets_service, calendar_service, whatsapp_service = get_services()
    festival_dates = get_festival_dates()

    # Sidebar
    with st.sidebar:
        st.markdown("### 🪔 Festival Information")
        st.markdown(
            f"**Celebration Period:**\n{festival_dates[0]['date_str']} to {festival_dates[-1]['date_str']}"
        )
        st.markdown(f"**Total Days:** {len(festival_dates)} Days")
        st.markdown(f"**Daily Slots:** {len(FESTIVAL_SLOTS)} Daily Rituals")
        st.markdown("---")

        # Mode Indicator
        if is_mock_mode():
            st.warning("⚠️ **Running in Mock Mode**\nExternal API keys are unconfigured. Using simulated local storage, calendar, and WhatsApp logger.")
        else:
            st.success("✅ **Live Cloud Connected**\nGoogle Sheets, Google Calendar, and WhatsApp Cloud API active.")

        st.markdown("---")
        st.markdown("### 📋 Daily Slot Schedule")
        for s in FESTIVAL_SLOTS:
            st.markdown(f"- **{s['time']}**: {s['icon']} {s['name']} ({s['duration_minutes']} min)")

        st.markdown("---")
        st.caption("Community Festival Committee • Developed for Seamless Devotee Experience")

    # Banner Header
    st.markdown(
        """
        <div class="festival-header">
            <h1>🪔 Community Pooja & Aarti Booking Portal 🪔</h1>
            <p>Reserve your auspicious slots for the Grand 10-Day Community Festival</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Navigation Tabs
    tab_book, tab_cancel, tab_overview, tab_admin = st.tabs([
        "📅 Book a Pooja Slot",
        "🔍 My Bookings & Cancellation",
        "📊 10-Day Festival Matrix",
        "⚙️ Admin & Daily Digest",
    ])

    # =========================================================================
    # TAB 1: SLOT CATALOG & BOOKING FLOW
    # =========================================================================
    with tab_book:
        st.markdown("#### Step 1: Select Festival Day")

        # Date selector
        date_options = {d["date_str"]: d["display_label"] for d in festival_dates}
        selected_date_str = st.selectbox(
            "Choose Festival Date:",
            options=list(date_options.keys()),
            format_func=lambda x: date_options[x],
            index=0,
            key="book_selected_date",
        )

        selected_day_info = next(d for d in festival_dates if d["date_str"] == selected_date_str)

        # Get active bookings for this date
        day_bookings = sheets_service.get_bookings_for_date(selected_date_str)
        booked_slot_map = {b.get("Slot_Time"): b for b in day_bookings}

        # Day Stats Bar
        total_slots = len(FESTIVAL_SLOTS)
        booked_count = len(day_bookings)
        avail_count = total_slots - booked_count

        stat_c1, stat_c2, stat_c3 = st.columns(3)
        stat_c1.metric("Date", selected_day_info["short_label"])
        stat_c2.metric("Available Slots", f"{avail_count} / {total_slots}", delta=f"{avail_count} free")
        stat_c3.metric("Booked Slots", f"{booked_count} / {total_slots}")

        st.markdown("---")
        st.markdown("#### Step 2: Slot Availability & Reservation")

        # Render 3 Slot Cards
        cols = st.columns(3)
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
                    st.markdown(
                        f"""
                        <div class="slot-card slot-card-booked">
                            <span class="badge-booked">🔴 BOOKED</span>
                            <h3 style="margin-top: 10px; margin-bottom: 4px;">{slot_icon} {slot_name}</h3>
                            <p style="font-size: 1.1rem; font-weight: 600; color: #555; margin-bottom: 8px;">⏰ {slot_time} ({duration} mins)</p>
                            <div style="background: white; padding: 10px; border-radius: 6px; border: 1px solid #FFCDD2;">
                                <strong>Reserved by:</strong><br>
                                🏢 Flat {flat_num}<br>
                                👤 {resident}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.button(
                        f"🔒 Unavailable ({slot_time})",
                        key=f"btn_disabled_{idx}_{selected_date_str}",
                        disabled=True,
                        use_container_width=True,
                    )
                else:
                    st.markdown(
                        f"""
                        <div class="slot-card slot-card-available">
                            <span class="badge-available">🟢 AVAILABLE</span>
                            <h3 style="margin-top: 10px; margin-bottom: 4px;">{slot_icon} {slot_name}</h3>
                            <p style="font-size: 1.1rem; font-weight: 600; color: #2E7D32; margin-bottom: 8px;">⏰ {slot_time} ({duration} mins)</p>
                            <p style="color: #4CAF50; font-weight: 500; font-size: 0.9rem;">✨ Open for devotee reservation</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

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

                                            st.balloons()
                                            st.success(f"🎉 **Booking Confirmed!** Flat {flat_no_in} is registered for {slot_name} ({slot_time}) on {selected_date_str}.")
                                            if wa_ok:
                                                st.info(f"📱 WhatsApp confirmation dispatched to {mobile_in}.")
                                            else:
                                                st.warning(f"Booking saved, but WhatsApp notification had notice: {wa_msg}")
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

                    with st.container():
                        st.markdown(
                            f"""
                            <div style="background: white; border: 1px solid #FFCCBC; border-radius: 8px; padding: 18px; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                    <h4 style="margin: 0; color: #D84315;">🪔 {c_slot} on {c_date}</h4>
                                    <span class="badge-booked">Active Booking</span>
                                </div>
                                <p style="margin-bottom: 6px; font-size: 1rem;">
                                    🏢 <strong>Flat:</strong> {c_flat} &nbsp;|&nbsp; 
                                    👤 <strong>Resident:</strong> {c_name} &nbsp;|&nbsp; 
                                    📱 <strong>WhatsApp:</strong> {c_phone}
                                </p>
                                <p style="font-size: 0.85rem; color: #757575; margin-bottom: 0;">
                                    🗓️ <strong>Calendar Event:</strong> {c_gcal or 'Pending Sync'} &nbsp;|&nbsp; 
                                    🕒 <strong>Booked at:</strong> {c_created}
                                </p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        cancel_col1, cancel_col2 = st.columns([3, 1])
                        with cancel_col2:
                            confirm_cancel = st.button(
                                f"❌ Cancel",
                                key=f"cancel_btn_{b_idx}_{c_date}_{c_slot}",
                                type="secondary",
                                use_container_width=True,
                                help=f"Cancel booking for {c_slot} on {c_date}",
                            )

                        if confirm_cancel:
                            with st.spinner("Processing cancellation (Sheets, Google Calendar, WhatsApp)..."):
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
                                    wa_ok, wa_msg = whatsapp_service.send_cancellation_notification(
                                        to_phone=c_phone,
                                        resident_name=c_name,
                                        flat_no=c_flat,
                                        date_str=c_date,
                                        slot_time=c_slot,
                                    )

                                    st.success(
                                        f"✅ **Booking Cancelled Successfully!**\n"
                                        f"- Status marked as **Cancelled** in Google Sheets\n"
                                        f"- Calendar Event ID removed and event deleted from Google Calendar\n"
                                        f"- WhatsApp cancellation notification sent to `{c_phone}`"
                                    )
                                    st.rerun()
                                else:
                                    st.error(f"Failed to cancel booking: {msg}")

    # =========================================================================
    # TAB 3: 10-DAY FESTIVAL GRID & STATS
    # =========================================================================
    with tab_overview:
        st.markdown("#### 📊 10-Day Festival Slot Matrix")
        all_bookings = sheets_service.get_all_bookings()
        active_bookings = [b for b in all_bookings if str(b.get("Status", "")).strip().lower() == "booked"]

        # High-level Metrics
        total_possible_slots = len(festival_dates) * len(FESTIVAL_SLOTS)
        total_active_booked = len(active_bookings)
        total_remaining = total_possible_slots - total_active_booked
        fill_rate = (total_active_booked / total_possible_slots) * 100 if total_possible_slots else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Festival Slots", total_possible_slots)
        m2.metric("Slots Booked", total_active_booked)
        m3.metric("Slots Available", total_remaining)
        m4.metric("Occupancy Rate", f"{fill_rate:.1f}%")

        st.markdown("---")

        # Build comprehensive table view
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
            }

            for s in FESTIVAL_SLOTS:
                s_time = s["time"]
                b = d_bookings.get(s_time)
                if b:
                    row_dict[s_time] = f"🔴 Flat {b.get('Flat_No')} ({b.get('Resident_Name')})"
                else:
                    row_dict[s_time] = "🟢 Available"

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
            st.caption("No notifications sent yet in this session.")


if __name__ == "__main__":
    main()
