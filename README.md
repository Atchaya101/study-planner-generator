# 📅 StudyPlan — Advanced Automated Planner & Timetable Generator

A full-stack Python + Flask web app with **6 advanced features** on top of the core timetable generator.

---

## ✨ Features

### Core
| Feature | Details |
|---|---|
| User Auth | Register / login with hashed passwords |
| Subject Management | Add, edit, delete with priority, deadlines & colour |
| Auto Timetable | Priority + deadline-aware weekly schedule generator |
| PDF Export | Formatted weekly timetable as downloadable PDF |
| Dark Mode | Toggle saved in localStorage |
| Responsive UI | Desktop, tablet, mobile |

### Advanced (New)
| Feature | Details |
|---|---|
| 🤖 AI Suggestions | Rule-based engine: neglect alerts, deadline warnings, balance tips |
| 📆 iCal Export | Download `.ics` file → import into Google/Apple/Outlook Calendar |
| 🔔 Push Notifications | Browser push + local reminders 5 min before each study slot |
| 📝 Notes & Attachments | Per-subject notes editor + file upload (PDF, images, DOCX, TXT) |
| 🍅 Pomodoro Timer | Focus/break timer with session logging and daily stats |
| 📊 Analytics Dashboard | Streaks, completion %, subject breakdown charts, weekly trends |

---

## 🗂 Project Structure

```
planner/
├── app.py                    ← Main Flask app (all routes + features)
├── planner.db                ← SQLite database (auto-created)
├── requirements.txt
├── templates/
│   ├── base.html             ← Shared layout
│   ├── login.html / register.html
│   ├── dashboard.html        ← Subject management
│   ├── timetable.html        ← Weekly schedule + iCal export
│   ├── suggestions.html      ← AI study suggestions
│   ├── notes.html            ← Notes & file attachments
│   ├── pomodoro.html         ← Pomodoro timer
│   └── analytics.html        ← Charts & progress tracking
└── static/
    ├── css/style.css         ← Full design system
    ├── js/main.js            ← Dark mode, push notifications, reminders
    ├── js/sw.js              ← Service worker for push
    ├── img/icon-192.png      ← Notification icon
    └── uploads/              ← User file attachments (auto-created)
```

---

## 🚀 How to Run in VS Code

### Step 1 — Open folder
Open VS Code → **File → Open Folder** → select `planner/`

### Step 2 — Create virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Run
```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 🧭 Feature Guide

### 🤖 AI Suggestions  (`/suggestions`)
Click **Suggestions** in the navbar. The rule engine analyses:
- Study hours logged vs. weekly target per subject
- Deadline proximity (warns at ≤ 5 days)
- Over-allocated low-priority subjects
- Celebrates when you exceed targets

### 📆 iCal Export  (`/export/ical`)
On the **Timetable** or **Analytics** page click **Export iCal**.
Opens as a `.ics` download. Import into:
- Google Calendar → Settings → Import
- Apple Calendar → File → Import
- Outlook → File → Open & Export → Import/Export

### 🔔 Push Notifications
On the **Timetable** page, click the **Notifications** toggle button.
- Grants browser notification permission
- Shows a test notification 5 seconds after enabling
- Automatically schedules reminders **5 minutes before** each study slot

### 📝 Notes & Attachments  (`/subject/<id>/notes`)
From the **Dashboard**, click the 📓 (journal) icon next to any subject.
- Write and delete timestamped notes
- Drag & drop or click to upload files (PDF, images, DOCX, TXT)
- Download attachments any time

### 🍅 Pomodoro Timer  (`/pomodoro`)
- Choose Focus (25 min), Short Break (5 min), or Long Break (15 min)
- Select a subject to attribute the session to
- On completion, a popup lets you log the session with an optional note
- Today's log and total minutes are shown alongside the timer

### 📊 Analytics  (`/analytics`)
Displays four visualisations powered by **Chart.js**:
1. **Daily bar chart** — hours studied per day (last 14 days)
2. **Subject doughnut** — time breakdown per subject
3. **Weekly trend line** — total hours per week (last 4 weeks)
4. **7-day heatmap** — which days you studied this week

Plus KPI cards: current streak 🔥, this week's hours, session count, and completion %.

---

## 📦 Dependencies

```
Flask==3.0.0
Flask-Session==0.5.0
Werkzeug==3.0.1
fpdf2==2.7.6
```
Chart.js (v4.4) is loaded from CDN — no installation needed.

---

## 🔒 Security Notes (before deploying publicly)
- Change `app.secret_key` to a long random string
- Set `debug=False`
- Use environment variables for secrets (`python-dotenv`)
- Add VAPID keys to `main.js` for real web push delivery

## 👩‍💻 Author

**Atchaya Parthipan**  
- GitHub: https://github.com/Atchaya101
