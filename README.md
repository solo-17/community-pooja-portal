# 🌺 Passiflora Ganesh Festival 2026 - Aarti Booking Portal 🪔
### 🚩 ॥ गणपति बाप्पा मोरया • मंगल मूर्ती मोरया ॥ 🚩
**Ganpati Bappa Morya! Mangal Murti Morya!**

A full-stack booking portal built with **Python** and **Streamlit** for the **Passiflora Ganesh Festival 2026** (14th Sep to 25th Sep 2026). Features divine Lord Ganesha imagery, festive branding, and requires no external relational database: the system uses **Google Sheets** as the persistent datastore, **Google Calendar** for automated calendar synchronization, **Meta WhatsApp Cloud API** for resident notifications and OTP verification, and **GitHub Actions** for an automated 4:00 AM daily schedule digest.

---

## 🌟 Key Features

1. **12-Day Festival Aarti Catalog (14th Sep – 25th Sep 2026)**:
   - Visual catalog across 12 celebration dates from Ganesh Chaturthi to Anant Chaturdashi / Purnima.
   - **Hindu Vedic Tithi for Each Day**: Displays the auspicious Tithi (e.g. *Bhadrapada Shukla Chaturthi / Sthapana*, *Rishi Panchami*, *Gauri Avahana*, *Anant Chaturdashi*).
   - **2 Daily Aarti Slots Only**:
     - 🌅 **Morning Aarti** (10:00 AM - 10:45 AM)
     - 🌙 **Evening Aarti** (08:00 PM - 08:45 PM)
   - Real-time visual availability indicators (🟢 Available vs 🔴 Booked by Flat X).

2. **Atomic Booking Flow**:
   - Devotees input Flat No, Resident Name, and 10-digit WhatsApp Mobile.
   - **Atomic Concurrency Check**: Re-queries Google Sheets before committing to prevent double booking.
   - Appends row to Google Sheet:
     `[Date, Slot_Time, Flat_No, Resident_Name, Mobile_No, Status="Booked", GCal_Event_ID, Created_At]`
   - Synchronizes event to Admin Google Calendar with rich details.
   - Dispatches instant WhatsApp confirmation message via Meta WhatsApp Cloud API.

3. **Secure WhatsApp OTP Cancellation Flow**:
   - Devotees lookup bookings using their Flat Number or WhatsApp Number.
   - Requires a **4-digit WhatsApp OTP** sent to the devotee's registered mobile number before cancellation can proceed.
   - Upon verification: marks Google Sheets status as `"Cancelled"`, deletes the Calendar Event ID from the sheet, deletes the event in Google Calendar, and dispatches a WhatsApp cancellation alert.

4. **12-Day Festival Matrix & Admin Panel**:
   - Comprehensive multi-day matrix showing all 24 Aarti slots across the 12 days alongside their Hindu Vedic Tithis.
   - High-level metrics (Total Aarti slots, Reserved count, Available count, Occupancy rate).
   - Instant preview & manual test trigger for the 4:00 AM WhatsApp digest.
   - Audit log of recent WhatsApp messages sent in the current session.

5. **4:00 AM Automated Daily Summary**:
   - Standalone CLI script `daily_summary.py` designed for cron / GitHub Actions.
   - Aggregates all bookings where `Date == today` and `Status == "Booked"`.
   - Sends formatted WhatsApp schedule digest to the Admin WhatsApp Number.
   - Configured via GitHub Actions workflow (`.github/workflows/daily_digest.yml`) scheduled for 4:00 AM IST (22:30 UTC).

6. **Resilient Local Mock Mode**:
   - If Google Cloud or WhatsApp credentials are not yet configured, the system automatically falls back to an interactive Mock Mode (local storage & simulated GCal/WhatsApp with live UI logs). The portal works immediately out of the box!

---

## 📁 Project Structure

```text
community-pooja-portal/
├── app.py                           # Streamlit main application & UI state machine
├── daily_summary.py                 # Standalone 4:00 AM cron summary CLI script
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Pytest configuration
├── .env.example                     # Environment variables template
├── .streamlit/
│   ├── config.toml                  # Festive theme styling & server configuration
│   └── secrets.toml.example         # Streamlit Cloud secrets template
├── .github/
│   └── workflows/
│       └── daily_digest.yml         # GitHub Actions 4:00 AM IST cron workflow
├── services/
│   ├── __init__.py
│   ├── config.py                    # Unified secrets, festival dates, and slot configurations
│   ├── sheets_service.py            # Google Sheets CRUD operations via gspread
│   ├── calendar_service.py          # Google Calendar API event creation & deletion
│   └── whatsapp_service.py          # Meta WhatsApp Cloud API HTTP client
└── tests/
    ├── test_services.py             # Unit & integration tests for services and CLI
    └── test_ui.py                   # Streamlit UI AppTest smoke tests
```

---

## 🚀 Quick Start (Local Development)

### 1. Clone & Set Up Virtual Environment

```bash
# Navigate to the repository
cd community-pooja-portal

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Portal (Mock Mode)

You can launch the portal right away! Without credentials, it runs in Mock Mode using local simulated storage:

```bash
streamlit run app.py
```

Visit `http://localhost:8501` in your browser.

### 3. Run Automated Tests

```bash
pytest tests/ -v
```

---

## 🔑 Production Setup & API Credentials

To connect live Google Cloud and Meta WhatsApp services, configure either `.env` or `.streamlit/secrets.toml`:

### 1. Google Cloud Service Account Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `community-pooja-portal`).
3. Enable the **Google Sheets API**, **Google Drive API**, and **Google Calendar API**.
4. Navigate to **IAM & Admin > Service Accounts** and create a service account (e.g. `festival-bot@...`).
5. Under the **Keys** tab, click **Add Key > Create New Key (JSON)** and save the JSON file.

### 2. Google Sheet Configuration
1. Create a new Google Spreadsheet (e.g., "Pooja & Aarti 2026 Bookings").
2. Click **Share** and add your Service Account email as an **Editor**.
3. Copy the Spreadsheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_KEY>/edit`
4. The application will automatically create the `Bookings` worksheet and initialize column headers on first run.

### 3. Google Calendar Configuration
1. Open [Google Calendar](https://calendar.google.com/).
2. Create or select your festival calendar.
3. Under **Settings and sharing**, share the calendar with your Service Account email with **"Make changes to events"** permissions.
4. Copy the **Calendar ID** (or use `primary` if using the main account calendar).

### 4. Meta WhatsApp Cloud API Setup
1. Go to the [Meta for Developers](https://developers.facebook.com/) portal.
2. Create a Business App and add the **WhatsApp** product.
3. Obtain:
   - `WHATSAPP_PHONE_NUMBER_ID` (from the WhatsApp dashboard)
   - `WHATSAPP_TOKEN` (Permanent System User Access Token)
   - `ADMIN_WHATSAPP_NUMBER` (e.g., `919876543210`)

### 5. Configuring Secrets

#### Option A: Local `.env` file
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in the values:
```env
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", "project_id": "...", ...}
GOOGLE_SHEET_KEY=1A2B3C4D5E6F...
GOOGLE_CALENDAR_ID=your_calendar_id@group.calendar.google.com
WHATSAPP_TOKEN=EAAB...
WHATSAPP_PHONE_NUMBER_ID=100012345678901
ADMIN_WHATSAPP_NUMBER=919876543210
FESTIVAL_START_DATE=2026-09-07
FESTIVAL_DAYS=10
```

#### Option B: Streamlit Cloud Secrets (`.streamlit/secrets.toml`)
If deploying to Streamlit Community Cloud:
1. In the Streamlit Cloud app settings, paste the keys into the **Secrets** section.
2. Format matching `.streamlit/secrets.toml.example`.

---

## ⏰ 4:00 AM Daily Summary Script & GitHub Actions

### Testing the Script Locally
Run the standalone CLI script directly:
```bash
# Preview today's schedule (dry run)
python daily_summary.py --dry-run

# Preview a specific date
python daily_summary.py --date 2026-09-08 --dry-run

# Dispatch live summary to Admin WhatsApp
python daily_summary.py
```

### GitHub Actions Cron Setup
The workflow is located at [`.github/workflows/daily_digest.yml`](file:///.github/workflows/daily_digest.yml).
- **Trigger**: Every day at 22:30 UTC = 04:00 AM IST (`cron: '30 22 * * *'`).
- **Repository Secrets**:
  Add the following secrets to your GitHub repository (**Settings > Secrets and variables > Actions**):
  - `GOOGLE_SERVICE_ACCOUNT_JSON`
  - `GOOGLE_SHEET_KEY`
  - `GOOGLE_CALENDAR_ID`
  - `WHATSAPP_TOKEN`
  - `WHATSAPP_PHONE_NUMBER_ID`
  - `ADMIN_WHATSAPP_NUMBER`
  - `FESTIVAL_START_DATE`

You can also trigger the workflow manually at any time via the **Run workflow** button under GitHub Actions.

---

## 🧪 Testing

Run the automated test suite anytime:
```bash
pytest tests/ -v
```
All 7 tests verify:
- Date calculation and duration handling for the 10 festival days.
- Phone number normalization logic for Indian mobiles.
- Google Calendar start/end datetime calculation in IST timezone.
- Atomic concurrency checks preventing duplicate bookings.
- Cancellation and slot release logic.
- WhatsApp message compilation and payload structure.
- Streamlit UI rendering without exceptions.
