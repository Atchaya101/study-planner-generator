# ============================================================
# app.py — StudyPlan Advanced Edition
# 6 Features: AI Suggestions, iCal Export, Push Notifications,
#             Notes/Attachments, Pomodoro Timer, Analytics
# ============================================================

from flask import (Flask, render_template, request, redirect,
    url_for, session, jsonify, send_file, make_response)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, io, uuid, json
from datetime import datetime, date, timedelta
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "studyplan_advanced_secret_2024"

DB_PATH    = os.path.join(os.path.dirname(__file__), "planner.db")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXT = {"pdf","png","jpg","jpeg","gif","txt","docx"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── DATABASE ──────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        created TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS subjects(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        name TEXT NOT NULL, hours_per_day REAL NOT NULL DEFAULT 1.0,
        priority TEXT NOT NULL DEFAULT 'Medium', deadline TEXT,
        color TEXT DEFAULT '#6366f1', created TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS notes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL, content TEXT NOT NULL,
        created TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS attachments(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL, filename TEXT NOT NULL, orig_name TEXT NOT NULL,
        created TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS study_sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        subject_id INTEGER, duration INTEGER NOT NULL DEFAULT 0,
        session_date TEXT DEFAULT (date('now')), note TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS push_subscriptions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE,
        subscription TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    conn.commit(); conn.close()

# ── HELPERS ───────────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session: return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

def fmt_time(hour_float):
    h=int(hour_float); m=int(round((hour_float-h)*60))
    if m==60: h+=1; m=0
    return f"{h:02d}:{m:02d}"

# ── AUTH ──────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    error=None
    if request.method=="POST":
        u=request.form.get("username","").strip()
        p=request.form.get("password","").strip()
        c=request.form.get("confirm","").strip()
        if not u or not p: error="Username and password required."
        elif len(p)<6: error="Password must be at least 6 characters."
        elif p!=c: error="Passwords do not match."
        else:
            conn=get_db()
            try:
                conn.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,generate_password_hash(p)))
                conn.commit(); return redirect(url_for("login",success=1))
            except sqlite3.IntegrityError: error="Username already taken."
            finally: conn.close()
    return render_template("register.html",error=error)

@app.route("/login", methods=["GET","POST"])
def login():
    error=None; success=request.args.get("success")
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password","").strip()
        conn=get_db(); user=conn.execute("SELECT * FROM users WHERE username=?",(u,)).fetchone(); conn.close()
        if user and check_password_hash(user["password"],p):
            session["user_id"]=user["id"]; session["username"]=user["username"]
            return redirect(url_for("dashboard"))
        error="Invalid username or password."
    return render_template("login.html",error=error,success=success)

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

# ── DASHBOARD ─────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    conn=get_db()
    subjects=conn.execute("SELECT * FROM subjects WHERE user_id=? ORDER BY priority DESC,name",(session["user_id"],)).fetchall()
    conn.close()
    po={"High":0,"Medium":1,"Low":2}
    sl=sorted([dict(s) for s in subjects],key=lambda x:po.get(x["priority"],1))
    return render_template("dashboard.html",username=session["username"],subjects=sl)

# ── SUBJECTS CRUD ─────────────────────────────────────────────
@app.route("/add_subject", methods=["POST"])
@login_required
def add_subject():
    name=request.form.get("name","").strip(); h=float(request.form.get("hours_per_day",1))
    p=request.form.get("priority","Medium"); dl=request.form.get("deadline","") or None
    col=request.form.get("color","#6366f1")
    if not name or h<=0 or h>12: return redirect(url_for("dashboard"))
    conn=get_db()
    conn.execute("INSERT INTO subjects(user_id,name,hours_per_day,priority,deadline,color) VALUES(?,?,?,?,?,?)",
                 (session["user_id"],name,h,p,dl,col))
    conn.commit(); conn.close(); return redirect(url_for("dashboard"))

@app.route("/edit_subject/<int:sid>", methods=["POST"])
@login_required
def edit_subject(sid):
    name=request.form.get("name","").strip(); h=float(request.form.get("hours_per_day",1))
    p=request.form.get("priority","Medium"); dl=request.form.get("deadline","") or None
    col=request.form.get("color","#6366f1")
    conn=get_db()
    conn.execute("UPDATE subjects SET name=?,hours_per_day=?,priority=?,deadline=?,color=? WHERE id=? AND user_id=?",
                 (name,h,p,dl,col,sid,session["user_id"]))
    conn.commit(); conn.close(); return redirect(url_for("dashboard"))

@app.route("/delete_subject/<int:sid>", methods=["POST"])
@login_required
def delete_subject(sid):
    conn=get_db()
    for tbl,col in [("notes","subject_id"),("attachments","subject_id"),("study_sessions","subject_id"),("subjects","id")]:
        conn.execute(f"DELETE FROM {tbl} WHERE {col}=? AND user_id=?",(sid,session["user_id"]))
    conn.commit(); conn.close(); return redirect(url_for("dashboard"))

# ── TIMETABLE ─────────────────────────────────────────────────
def generate_timetable(subjects, available_hours, start_hour=8):
    DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    pw={"High":3,"Medium":2,"Low":1}
    def sort_key(s):
        p=pw.get(s["priority"],2)
        dl=999
        if s["deadline"]:
            try: dl=(datetime.strptime(s["deadline"],"%Y-%m-%d").date()-date.today()).days
            except: pass
        return(-p,dl)
    sorted_s=sorted(subjects,key=sort_key); sched={d:[] for d in DAYS}
    for day in DAYS:
        curr=start_hour; rem=available_hours
        for sub in sorted_s:
            if rem<=0: break
            alloc=min(sub["hours_per_day"],rem)
            if alloc<0.25: continue
            sched[day].append({"subject":sub["name"],"subject_id":sub["id"],
                "start":fmt_time(curr),"end":fmt_time(curr+alloc),
                "priority":sub["priority"],"color":sub.get("color","#6366f1"),
                "deadline":sub.get("deadline","")})
            curr+=alloc; rem-=alloc
    return sched

@app.route("/timetable")
@login_required
def timetable_view():
    conn=get_db()
    subjects=conn.execute("SELECT * FROM subjects WHERE user_id=?",(session["user_id"],)).fetchall()
    conn.close()
    sl=[dict(s) for s in subjects]; hours=float(request.args.get("hours",6))
    return render_template("timetable.html",username=session["username"],
        schedule=generate_timetable(sl,hours) if sl else {},
        available_hours=hours,subjects=sl)

@app.route("/api/timetable")
@login_required
def api_timetable():
    conn=get_db(); subjects=conn.execute("SELECT * FROM subjects WHERE user_id=?",(session["user_id"],)).fetchall(); conn.close()
    return jsonify(generate_timetable([dict(s) for s in subjects],float(request.args.get("hours",6))))

# ── PDF EXPORT ────────────────────────────────────────────────
@app.route("/download_pdf")
@login_required
def download_pdf():
    conn=get_db(); subjects=conn.execute("SELECT * FROM subjects WHERE user_id=?",(session["user_id"],)).fetchall(); conn.close()
    sl=[dict(s) for s in subjects]; hours=float(request.args.get("hours",6)); sched=generate_timetable(sl,hours)
    pdf=FPDF(); pdf.set_auto_page_break(auto=True,margin=15); pdf.add_page()
    pdf.set_font("Helvetica","B",18); pdf.set_fill_color(99,102,241); pdf.set_text_color(255,255,255)
    pdf.cell(0,12,"Weekly Study Timetable",ln=True,fill=True,align="C"); pdf.ln(4)
    pdf.set_font("Helvetica","",10); pdf.set_text_color(80,80,80)
    pdf.cell(0,6,f"User: {session['username']}  |  Generated: {date.today().strftime('%d %B %Y')}  |  {hours}h/day",ln=True); pdf.ln(6)
    DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    pcol={"High":(239,68,68),"Medium":(245,158,11),"Low":(34,197,94)}
    for day in DAYS:
        slots=sched.get(day,[])
        pdf.set_font("Helvetica","B",12); pdf.set_fill_color(79,70,229); pdf.set_text_color(255,255,255)
        pdf.cell(0,8,f"  {day}",ln=True,fill=True); pdf.ln(1)
        if slots:
            pdf.set_font("Helvetica","B",9); pdf.set_fill_color(230,230,250); pdf.set_text_color(40,40,40)
            pdf.cell(35,7,"Time",border=1,fill=True); pdf.cell(90,7,"Subject",border=1,fill=True)
            pdf.cell(35,7,"Priority",border=1,fill=True,ln=True); pdf.set_font("Helvetica","",9)
            for s in slots:
                r,g,b=pcol.get(s["priority"],(150,150,150))
                pdf.set_text_color(40,40,40); pdf.cell(35,7,f"{s['start']} – {s['end']}",border=1)
                pdf.cell(90,7,s["subject"],border=1); pdf.set_text_color(r,g,b)
                pdf.cell(35,7,s["priority"],border=1,ln=True); pdf.set_text_color(40,40,40)
        else:
            pdf.set_font("Helvetica","I",9); pdf.set_text_color(160,160,160)
            pdf.cell(0,7,"  Free day",ln=True)
        pdf.ln(3)
    buf=io.BytesIO(); pdf.output(buf); buf.seek(0)
    return send_file(buf,mimetype="application/pdf",as_attachment=True,
        download_name=f"timetable_{session['username']}_{date.today()}.pdf")

# ── FEATURE 1: AI STUDY SUGGESTIONS ──────────────────────────
def build_suggestions(subjects, sessions_last7):
    """Rule-based engine: analyses subjects + session history → actionable tips."""
    suggestions=[]; today=date.today()
    studied_map={}
    for s in sessions_last7:
        k=s["subject_id"]; studied_map[k]=studied_map.get(k,0)+s["duration"]

    for subj in subjects:
        sid=subj["id"]; studied_min=studied_map.get(sid,0)
        target_min=subj["hours_per_day"]*7*60
        ratio=studied_min/target_min if target_min>0 else 0

        # Rule 1 — Neglected high-priority
        if subj["priority"]=="High" and ratio<0.3:
            suggestions.append({"type":"warning","icon":"bi-exclamation-triangle-fill",
                "subject":subj["name"],"title":f"⚠️ {subj['name']} needs attention",
                "body":f"High-priority subject with only {round(studied_min)}m studied this week "
                       f"(target {round(target_min)}m). Schedule a session today.","action":"Add to plan"})

        # Rule 2 — Deadline approaching
        if subj["deadline"]:
            try:
                dl=datetime.strptime(subj["deadline"],"%Y-%m-%d").date(); days_left=(dl-today).days
                if 0<=days_left<=5:
                    suggestions.append({"type":"danger","icon":"bi-calendar-x-fill",
                        "subject":subj["name"],"title":f"🚨 Deadline in {days_left} day{'s' if days_left!=1 else ''}",
                        "body":f"{subj['name']} due {subj['deadline']}. Increase daily hours to at least {subj['hours_per_day']+0.5:.1f}h.",
                        "action":"Review schedule"})
                elif days_left<0:
                    suggestions.append({"type":"secondary","icon":"bi-calendar-check",
                        "subject":subj["name"],"title":f"Deadline passed: {subj['name']}",
                        "body":f"Deadline was {abs(days_left)} day(s) ago. Update or remove it.","action":"Edit subject"})
            except ValueError: pass

        # Rule 3 — On track / exceeding
        if ratio>=1.1:
            suggestions.append({"type":"success","icon":"bi-trophy-fill",
                "subject":subj["name"],"title":f"🏆 Great work on {subj['name']}!",
                "body":f"Studied {round(studied_min)}m this week — {round((ratio-1)*100)}% above target!","action":None})

        # Rule 4 — Low priority but very high hours
        if subj["priority"]=="Low" and subj["hours_per_day"]>2:
            suggestions.append({"type":"info","icon":"bi-lightbulb-fill",
                "subject":subj["name"],"title":f"💡 Balance check: {subj['name']}",
                "body":f"Low-priority subject allocated {subj['hours_per_day']}h/day. Consider reducing to free up time.",
                "action":"Edit subject"})

    # Rule 5 — No sessions this week
    if not sessions_last7 and subjects:
        suggestions.append({"type":"warning","icon":"bi-alarm-fill","subject":None,
            "title":"No study sessions logged this week",
            "body":"Start the Pomodoro timer to log your first session and begin a streak!",
            "action":"Start Pomodoro"})

    # Rule 6 — Many subjects → suggest Pomodoro
    if len(subjects)>=5:
        suggestions.append({"type":"info","icon":"bi-pie-chart-fill","subject":None,
            "title":f"📊 {len(subjects)} subjects detected",
            "body":"With many subjects, short focused sessions (25–45 min) work best. Try Pomodoro!",
            "action":"Open Pomodoro"})

    order={"danger":0,"warning":1,"info":2,"success":3,"secondary":4}
    suggestions.sort(key=lambda x:order.get(x["type"],5))
    return suggestions[:8]

@app.route("/suggestions")
@login_required
def suggestions_page():
    conn=get_db()
    subjects=conn.execute("SELECT * FROM subjects WHERE user_id=?",(session["user_id"],)).fetchall()
    since=(date.today()-timedelta(days=7)).isoformat()
    sessions=conn.execute("SELECT * FROM study_sessions WHERE user_id=? AND session_date>=?",(session["user_id"],since)).fetchall()
    conn.close()
    tips=build_suggestions([dict(s) for s in subjects],[dict(s) for s in sessions])
    return render_template("suggestions.html",username=session["username"],
        suggestions=tips,subjects=[dict(s) for s in subjects])

@app.route("/api/suggestions")
@login_required
def api_suggestions():
    conn=get_db()
    subjects=conn.execute("SELECT * FROM subjects WHERE user_id=?",(session["user_id"],)).fetchall()
    since=(date.today()-timedelta(days=7)).isoformat()
    sessions=conn.execute("SELECT * FROM study_sessions WHERE user_id=? AND session_date>=?",(session["user_id"],since)).fetchall()
    conn.close()
    return jsonify(build_suggestions([dict(s) for s in subjects],[dict(s) for s in sessions]))

# ── FEATURE 2: iCAL EXPORT ────────────────────────────────────
@app.route("/export/ical")
@login_required
def export_ical():
    """Generate .ics file — next 8 weeks of the timetable as recurring events."""
    conn=get_db(); subjects=conn.execute("SELECT * FROM subjects WHERE user_id=?",(session["user_id"],)).fetchall(); conn.close()
    sl=[dict(s) for s in subjects]; hours=float(request.args.get("hours",6)); sched=generate_timetable(sl,hours)
    DAY_MAP={"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
    today=date.today()
    lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//StudyPlan//EN",
           "CALSCALE:GREGORIAN","METHOD:PUBLISH",
           f"X-WR-CALNAME:StudyPlan – {session['username']}","X-WR-TIMEZONE:UTC"]
    uid_base=datetime.utcnow().strftime("%Y%m%d%H%M%S")
    for day_name,slots in sched.items():
        target_dow=DAY_MAP[day_name]; days_ahead=(target_dow-today.weekday())%7
        event_date=today+timedelta(days=days_ahead)
        for i,slot in enumerate(slots):
            sh,sm=map(int,slot["start"].split(":")); eh,em=map(int,slot["end"].split(":"))
            dtstart=datetime(event_date.year,event_date.month,event_date.day,sh,sm).strftime("%Y%m%dT%H%M%S")
            dtend=datetime(event_date.year,event_date.month,event_date.day,eh,em).strftime("%Y%m%dT%H%M%S")
            uid=f"{uid_base}-{day_name}-{i}@studyplan"
            dl_note=f"\\nDeadline: {slot['deadline']}" if slot.get("deadline") else ""
            lines+=["BEGIN:VEVENT",f"UID:{uid}",f"DTSTART:{dtstart}",f"DTEND:{dtend}",
                    "RRULE:FREQ=WEEKLY;COUNT=8",
                    f"SUMMARY:[{slot['priority']}] {slot['subject']}",
                    f"DESCRIPTION:Priority: {slot['priority']}{dl_note}","END:VEVENT"]
    lines.append("END:VCALENDAR")
    resp=make_response("\r\n".join(lines))
    resp.headers["Content-Type"]="text/calendar; charset=utf-8"
    resp.headers["Content-Disposition"]=f"attachment; filename=studyplan_{session['username']}.ics"
    return resp

# ── FEATURE 3: PUSH NOTIFICATIONS ────────────────────────────
@app.route("/api/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    data=request.get_json()
    if not data: return jsonify({"error":"No data"}),400
    conn=get_db()
    conn.execute("INSERT INTO push_subscriptions(user_id,subscription) VALUES(?,?) "
                 "ON CONFLICT(user_id) DO UPDATE SET subscription=excluded.subscription",
                 (session["user_id"],json.dumps(data)))
    conn.commit(); conn.close(); return jsonify({"status":"subscribed"})

@app.route("/api/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    conn=get_db(); conn.execute("DELETE FROM push_subscriptions WHERE user_id=?",(session["user_id"],))
    conn.commit(); conn.close(); return jsonify({"status":"unsubscribed"})

@app.route("/api/push/status")
@login_required
def push_status():
    conn=get_db(); sub=conn.execute("SELECT id FROM push_subscriptions WHERE user_id=?",(session["user_id"],)).fetchone(); conn.close()
    return jsonify({"subscribed":sub is not None})

@app.route("/sw.js")
def service_worker():
    return send_file(os.path.join(app.static_folder,"js","sw.js"),mimetype="application/javascript")

# ── FEATURE 4: NOTES & ATTACHMENTS ───────────────────────────
@app.route("/subject/<int:sid>/notes")
@login_required
def subject_notes(sid):
    conn=get_db()
    subject=conn.execute("SELECT * FROM subjects WHERE id=? AND user_id=?",(sid,session["user_id"])).fetchone()
    if not subject: conn.close(); return redirect(url_for("dashboard"))
    notes=conn.execute("SELECT * FROM notes WHERE subject_id=? AND user_id=? ORDER BY created DESC",(sid,session["user_id"])).fetchall()
    atts=conn.execute("SELECT * FROM attachments WHERE subject_id=? AND user_id=? ORDER BY created DESC",(sid,session["user_id"])).fetchall()
    conn.close()
    return render_template("notes.html",username=session["username"],subject=dict(subject),
        notes=[dict(n) for n in notes],attachments=[dict(a) for a in atts])

@app.route("/subject/<int:sid>/notes/add", methods=["POST"])
@login_required
def add_note(sid):
    content=request.form.get("content","").strip()
    if content:
        conn=get_db(); conn.execute("INSERT INTO notes(user_id,subject_id,content) VALUES(?,?,?)",(session["user_id"],sid,content))
        conn.commit(); conn.close()
    return redirect(url_for("subject_notes",sid=sid))

@app.route("/notes/<int:nid>/delete", methods=["POST"])
@login_required
def delete_note(nid):
    conn=get_db(); note=conn.execute("SELECT * FROM notes WHERE id=? AND user_id=?",(nid,session["user_id"])).fetchone()
    sid=note["subject_id"] if note else None
    conn.execute("DELETE FROM notes WHERE id=? AND user_id=?",(nid,session["user_id"])); conn.commit(); conn.close()
    return redirect(url_for("subject_notes",sid=sid) if sid else url_for("dashboard"))

@app.route("/subject/<int:sid>/attach", methods=["POST"])
@login_required
def upload_attachment(sid):
    file=request.files.get("file")
    if file and file.filename and allowed_file(file.filename):
        orig=secure_filename(file.filename); ext=orig.rsplit(".",1)[1].lower()
        stored=f"{uuid.uuid4().hex}.{ext}"; file.save(os.path.join(UPLOAD_DIR,stored))
        conn=get_db(); conn.execute("INSERT INTO attachments(user_id,subject_id,filename,orig_name) VALUES(?,?,?,?)",
            (session["user_id"],sid,stored,orig)); conn.commit(); conn.close()
    return redirect(url_for("subject_notes",sid=sid))

@app.route("/attachments/<int:aid>/delete", methods=["POST"])
@login_required
def delete_attachment(aid):
    conn=get_db(); att=conn.execute("SELECT * FROM attachments WHERE id=? AND user_id=?",(aid,session["user_id"])).fetchone()
    sid=None
    if att:
        try: os.remove(os.path.join(UPLOAD_DIR,att["filename"]))
        except: pass
        conn.execute("DELETE FROM attachments WHERE id=?",(aid,)); conn.commit(); sid=att["subject_id"]
    conn.close(); return redirect(url_for("subject_notes",sid=sid) if sid else url_for("dashboard"))

@app.route("/attachments/<int:aid>/download")
@login_required
def download_attachment(aid):
    conn=get_db(); att=conn.execute("SELECT * FROM attachments WHERE id=? AND user_id=?",(aid,session["user_id"])).fetchone(); conn.close()
    if not att: return "Not found",404
    return send_file(os.path.join(UPLOAD_DIR,att["filename"]),as_attachment=True,download_name=att["orig_name"])

# ── FEATURE 5: POMODORO TIMER ─────────────────────────────────
@app.route("/pomodoro")
@login_required
def pomodoro():
    conn=get_db()
    subjects=conn.execute("SELECT * FROM subjects WHERE user_id=? ORDER BY name",(session["user_id"],)).fetchall()
    today_sessions=conn.execute(
        "SELECT ss.*,s.name AS subject_name FROM study_sessions ss "
        "LEFT JOIN subjects s ON ss.subject_id=s.id "
        "WHERE ss.user_id=? AND ss.session_date=? ORDER BY ss.id DESC",
        (session["user_id"],date.today().isoformat())).fetchall()
    conn.close(); total=sum(s["duration"] for s in today_sessions)
    return render_template("pomodoro.html",username=session["username"],
        subjects=[dict(s) for s in subjects],today_sessions=[dict(s) for s in today_sessions],total_today=total)

@app.route("/api/pomodoro/log", methods=["POST"])
@login_required
def log_pomodoro():
    data=request.get_json(); sid=data.get("subject_id") or None
    dur=int(data.get("duration",25)); note=(data.get("note") or "")[:200]
    conn=get_db(); conn.execute("INSERT INTO study_sessions(user_id,subject_id,duration,note) VALUES(?,?,?,?)",
        (session["user_id"],sid,dur,note)); conn.commit(); conn.close()
    return jsonify({"status":"logged","duration":dur})

@app.route("/api/pomodoro/today")
@login_required
def pomodoro_today():
    conn=get_db()
    sessions=conn.execute(
        "SELECT ss.*,s.name AS subject_name FROM study_sessions ss "
        "LEFT JOIN subjects s ON ss.subject_id=s.id "
        "WHERE ss.user_id=? AND ss.session_date=?",
        (session["user_id"],date.today().isoformat())).fetchall()
    conn.close(); sl=[dict(s) for s in sessions]
    return jsonify({"sessions":sl,"total_minutes":sum(s["duration"] for s in sl)})

# ── FEATURE 6: ANALYTICS DASHBOARD ───────────────────────────
@app.route("/analytics")
@login_required
def analytics():
    conn=get_db()
    subjects=conn.execute("SELECT * FROM subjects WHERE user_id=?",(session["user_id"],)).fetchall()
    since=(date.today()-timedelta(days=13)).isoformat()
    sessions=conn.execute(
        "SELECT ss.*,s.name AS subject_name,s.color FROM study_sessions ss "
        "LEFT JOIN subjects s ON ss.subject_id=s.id "
        "WHERE ss.user_id=? AND ss.session_date>=? ORDER BY ss.session_date",
        (session["user_id"],since)).fetchall()
    conn.close()
    sl=[dict(s) for s in sessions]; subj_l=[dict(s) for s in subjects]

    # Streak
    active_dates=sorted({s["session_date"] for s in sl},reverse=True)
    streak=0; check=date.today()
    for d in active_dates:
        if d==check.isoformat(): streak+=1; check-=timedelta(days=1)
        else: break

    ws=(date.today()-timedelta(days=date.today().weekday())).isoformat()
    week_mins=sum(s["duration"] for s in sl if s["session_date"]>=ws)

    subject_mins={}
    for s in sl:
        k=s["subject_name"] or "General"
        if k not in subject_mins: subject_mins[k]={"minutes":0,"color":s.get("color") or "#6366f1"}
        subject_mins[k]["minutes"]+=s["duration"]

    daily={}
    for i in range(13,-1,-1):
        d=(date.today()-timedelta(days=i)).isoformat(); daily[d]=0
    for s in sl:
        if s["session_date"] in daily: daily[s["session_date"]]=round(daily[s["session_date"]]+s["duration"]/60,2)

    last7={(date.today()-timedelta(days=i)).isoformat() for i in range(7)}
    active_7=last7&{s["session_date"] for s in sl}
    comp_pct=round(len(active_7)/7*100)

    weekly_hours={}
    for i in range(3,-1,-1):
        ws2=(date.today()-timedelta(weeks=i,days=date.today().weekday())).isoformat()
        we2=(date.fromisoformat(ws2)+timedelta(days=6)).isoformat()
        label=f"W-{i}" if i>0 else "This week"
        weekly_hours[label]=round(sum(s["duration"] for s in sl if ws2<=s["session_date"]<=we2)/60,2)

    data={"streak":streak,"week_hours":round(week_mins/60,1),"total_sessions":len(sl),
          "completion_pct":comp_pct,"subject_mins":subject_mins,"daily_hours":daily,
          "active_days":sorted(active_7),"weekly_trend":weekly_hours}
    return render_template("analytics.html",username=session["username"],data=data,subjects=subj_l,sessions=sl)

# ── ENTRY POINT ───────────────────────────────────────────────
# ── JINJA FILTER ──────────────────────────────────────────────
@app.template_global()
def today_offset(weekday_index):
    """Return ISO date string for the given weekday index (0=Mon) of the current week."""
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    return (monday + timedelta(days=weekday_index)).isoformat()

@app.template_global()
def now_weekday():
    """Return today's weekday index (0=Mon…6=Sun)."""
    return date.today().weekday()

if __name__ == "__main__":
    init_db()
    print("✅  Database ready.")
    print("🚀  Running at http://127.0.0.1:5000")
    app.run(debug=True)
