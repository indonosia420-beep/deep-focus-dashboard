import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import time
import json
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "student_progress.db")
FOCUS_SECONDS = 50 * 60
BREAK_SECONDS = 10 * 60

st.set_page_config(page_title="Deep Focus | Student Dashboard", page_icon="🎓", layout="wide")

st.markdown("""
<style>
.stApp { background: #101827; color: #F8FAFC; }
[data-testid="stSidebar"] { background: #0B1220; border-right: 1px solid #263449; }
.block-container { padding-top: 1.5rem; max-width: 1400px; }
h1,h2,h3 { color: #F8FAFC !important; }
div[data-testid="stMetric"] { background: #1C2A3E; padding: 18px; border-radius: 14px; border: 1px solid #2B3B52; }
div[data-testid="stMetricLabel"] p { color: #B9C7D9 !important; }
div[data-testid="stMetricValue"] { color: #F8FAFC !important; }
div.stButton > button { border-radius: 10px; border: 1px solid #2B3B52; min-height: 2.5rem; }
div.stButton > button[kind="primary"] { background: #2DD4BF; color: #101827; border: none; font-weight: 700; }
div[data-testid="stProgressBar"] > div > div { background: #2DD4BF; }
.small-muted { color: #9BAEC7; font-size: .9rem; }
.focus-panel { background: linear-gradient(135deg,#1C2A3E,#15283A); padding: 22px; border-radius: 18px; border: 1px solid #2B3B52; }
</style>
""", unsafe_allow_html=True)

def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, subject TEXT DEFAULT '',
            priority TEXT DEFAULT 'Medium', due_date TEXT, estimated_minutes INTEGER DEFAULT 30,
            status TEXT DEFAULT 'Pending', created_at TEXT NOT NULL, completed_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT DEFAULT '', duration_minutes INTEGER NOT NULL,
            session_type TEXT NOT NULL, distractions INTEGER DEFAULT 0, notes TEXT DEFAULT '',
            started_at TEXT NOT NULL, completed_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
        c.commit()

def get_setting(key, default=None):
    with connect() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default

def set_setting(key, value):
    with connect() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, json.dumps(value)))
        c.commit()

def load_tasks():
    with connect() as c:
        return pd.read_sql_query("SELECT * FROM tasks ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, due_date", c)

def load_sessions():
    with connect() as c:
        return pd.read_sql_query("SELECT * FROM sessions ORDER BY completed_at DESC", c)

def add_task(title, subject, priority, due, estimate):
    with connect() as c:
        c.execute("INSERT INTO tasks(title,subject,priority,due_date,estimated_minutes,status,created_at) VALUES(?,?,?,?,?,'Pending',?)",
                  (title.strip(), subject.strip(), priority, due.isoformat() if due else None, int(estimate), datetime.now().isoformat(timespec="seconds")))
        c.commit()

def save_session(subject, duration, session_type, distractions, notes, started_at):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as c:
        c.execute("INSERT INTO sessions(subject,duration_minutes,session_type,distractions,notes,started_at,completed_at) VALUES(?,?,?,?,?,?,?)",
                  (subject, int(duration), session_type, int(distractions), notes.strip(), started_at, now))
        c.commit()

def fmt_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds//60:02d}:{seconds%60:02d}"

init_db()

# Timer state is persisted in SQLite so refreshes don't reset the session.
timer = get_setting("timer", None)
if "timer" not in st.session_state:
    st.session_state.timer = timer or {
        "mode": "Focus", "status": "Ready", "end_epoch": None,
        "remaining": FOCUS_SECONDS, "started_at": None, "subject": "",
        "distractions": 0, "notes": ""
    }
def save_timer():
    set_setting("timer", st.session_state.timer)

def timer_remaining():
    t = st.session_state.timer
    if t["status"] == "Running" and t["end_epoch"]:
        return max(0, int(t["end_epoch"] - time.time()))
    return int(t["remaining"])

def start_timer():
    t = st.session_state.timer
    rem = timer_remaining()
    t["remaining"] = rem
    t["end_epoch"] = time.time() + rem
    t["status"] = "Running"
    if t["mode"] == "Focus" and not t["started_at"]:
        t["started_at"] = datetime.now().isoformat(timespec="seconds")
    save_timer()

def pause_timer():
    t = st.session_state.timer
    t["remaining"] = timer_remaining()
    t["end_epoch"] = None
    t["status"] = "Paused"
    save_timer()

def reset_timer():
    t = st.session_state.timer
    t["status"] = "Ready"
    t["end_epoch"] = None
    t["remaining"] = FOCUS_SECONDS if t["mode"] == "Focus" else BREAK_SECONDS
    t["started_at"] = None
    t["distractions"] = 0
    t["notes"] = ""
    save_timer()

def switch_mode(mode):
    t = st.session_state.timer
    t["mode"] = mode
    t["status"] = "Ready"
    t["end_epoch"] = None
    t["remaining"] = FOCUS_SECONDS if mode == "Focus" else BREAK_SECONDS
    t["started_at"] = None
    t["distractions"] = 0
    t["notes"] = ""
    save_timer()

def complete_timer():
    t = st.session_state.timer
    if t["mode"] == "Focus":
        started = t["started_at"] or datetime.now().isoformat(timespec="seconds")
        save_session(t.get("subject", ""), 50, "Focus", t.get("distractions", 0), t.get("notes", ""), started)
        st.session_state.toast_message = "Focus session saved to your study history!"
        switch_mode("Break")
    else:
        st.session_state.toast_message = "Break complete — ready for another focus session."
        switch_mode("Focus")

# Auto-refresh while a timer is running; package is included in requirements.
try:
    from streamlit_autorefresh import st_autorefresh
    if st.session_state.timer["status"] == "Running":
        st_autorefresh(interval=1000, key="timer_refresh")
except Exception:
    pass

st.sidebar.markdown("## 🎓 Deep Focus")
st.sidebar.caption("Your personal study workspace")
page = st.sidebar.radio("Navigate", ["Dashboard", "Focus Timer", "Study Log", "Tasks", "Progress & Analytics", "Settings"])
st.sidebar.markdown("---")
st.sidebar.markdown("**Your data stays on this device**")
st.sidebar.caption("Saved in a local SQLite database beside the app.")

tasks = load_tasks()
sessions = load_sessions()
today = date.today()
today_sessions = sessions[sessions["completed_at"].astype(str).str[:10] == today.isoformat()] if not sessions.empty else sessions
today_minutes = int(today_sessions["duration_minutes"].sum()) if not today_sessions.empty else 0
done_tasks = int((tasks["status"] == "Completed").sum()) if not tasks.empty else 0
pending_tasks = int((tasks["status"] == "Pending").sum()) if not tasks.empty else 0
goal_minutes = int(get_setting("daily_goal_minutes", 240))
goal_pct = min(100, round(today_minutes / goal_minutes * 100)) if goal_minutes else 0
streak = 0
if not sessions.empty:
    dates = set(sessions["completed_at"].astype(str).str[:10])
    d = today
    while d.isoformat() in dates:
        streak += 1
        d -= timedelta(days=1)

if "toast_message" in st.session_state:
    st.toast(st.session_state.pop("toast_message"))

if page == "Dashboard":
    st.title("Good day. Let's make progress. 👋")
    st.caption(f"{today.strftime('%A, %d %B %Y')} · Small consistent sessions add up.")
    a,b,c,d = st.columns(4)
    a.metric("Study time today", f"{today_minutes//60}h {today_minutes%60:02d}m")
    b.metric("Pending tasks", pending_tasks)
    c.metric("Completed tasks", done_tasks)
    d.metric("Current study streak", f"{streak} day{'s' if streak != 1 else ''}")
    st.markdown("### Daily study target")
    st.progress(goal_pct / 100)
    st.caption(f"{today_minutes} of {goal_minutes} minutes · {goal_pct}% completed")
    left, right = st.columns([1.2,1])
    with left:
        st.markdown("### Today's checklist")
        if tasks.empty:
            st.info("No tasks yet. Add your first task in the Tasks page.")
        else:
            todays = tasks[(tasks["due_date"].isna()) | (tasks["due_date"] == today.isoformat()) | (tasks["status"] == "Pending")]
            if todays.empty:
                st.success("You're all caught up!")
            for _, task in todays.head(8).iterrows():
                label = f"{'✅' if task['status']=='Completed' else '⬜'} **{task['title']}**"
                st.markdown(label)
                st.caption(f"{task['subject'] or 'General'} · {task['priority']} priority" + (f" · Due {task['due_date']}" if task['due_date'] else ""))
    with right:
        st.markdown("### Quick focus")
        st.markdown('<div class="focus-panel"><p style="color:#9BAEC7;margin:0">DEFAULT SESSION</p><h1 style="font-size:2.8rem;margin:5px 0;color:#2DD4BF">50 / 10</h1><p style="color:#B9C7D9">50 minutes focused study · 10 minute break</p></div>', unsafe_allow_html=True)
        if st.button("Open Focus Timer", type="primary", use_container_width=True):
            st.session_state["requested_page"] = "Focus Timer"
            st.rerun()
        st.markdown("### Recent sessions")
        if sessions.empty:
            st.caption("Your completed focus sessions will appear here.")
        else:
            for _, s in sessions.head(4).iterrows():
                st.write(f"📘 {s['subject'] or 'General study'} · {s['duration_minutes']} min")
                st.caption(str(s["completed_at"])[:16].replace("T"," "))

elif page == "Focus Timer":
    st.title("Smart Focus Timer")
    st.caption("50 minutes of deep work, followed by a 10-minute recovery break.")
    t = st.session_state.timer
    if timer_remaining() <= 0 and t["status"] == "Running":
        complete_timer()
        st.rerun()
    t = st.session_state.timer
    top1, top2 = st.columns([1.1,1])
    with top1:
        mode = st.radio("Session", ["Focus", "Break"], horizontal=True, index=0 if t["mode"]=="Focus" else 1)
        if mode != t["mode"]:
            if t["status"] == "Running":
                st.warning("Pause the current timer before switching sessions.")
            else:
                switch_mode(mode)
                st.rerun()
        if t["mode"] == "Focus":
            subjects = sorted(set(tasks["subject"].dropna().astype(str).tolist())) if not tasks.empty else []
            subjects = [s for s in subjects if s.strip()]
            subjects = ["General study"] + subjects
            current = t.get("subject") or "General study"
            selected = st.selectbox("What are you studying?", subjects, index=subjects.index(current) if current in subjects else 0)
            t["subject"] = "" if selected == "General study" else selected
            save_timer()
        else:
            st.info("Break mode: step away from your desk, stretch, and rest your eyes.")
        remaining = timer_remaining()
        total = FOCUS_SECONDS if t["mode"] == "Focus" else BREAK_SECONDS
        st.markdown('<div class="focus-panel" style="text-align:center">', unsafe_allow_html=True)
        color = "#2DD4BF" if t["mode"] == "Focus" else "#FBBF24"
        st.markdown(f'<p style="color:#9BAEC7;letter-spacing:2px">{t["mode"].upper()} SESSION</p><div style="font-size:4.5rem;font-weight:700;color:{color};line-height:1.2">{fmt_time(remaining)}</div><p style="color:#B9C7D9">{remaining//60} minutes remaining</p></div>', unsafe_allow_html=True)
        st.progress(max(0, min(1, 1 - remaining / total)))
        x,y,z = st.columns(3)
        with x:
            if t["status"] != "Running":
                if st.button("▶ Start" if t["status"] == "Ready" else "▶ Resume", type="primary", use_container_width=True):
                    start_timer(); st.rerun()
            else:
                if st.button("Ⅱ Pause", use_container_width=True):
                    pause_timer(); st.rerun()
        with y:
            if st.button("↻ Reset", use_container_width=True):
                reset_timer(); st.rerun()
        with z:
            st.button("● " + t["status"], disabled=True, use_container_width=True)
    with top2:
        st.markdown("### Session notes")
        if t["mode"] == "Focus":
            distractions = st.number_input("Distractions during this session", min_value=0, max_value=100, value=int(t.get("distractions",0)), step=1, help="Increase this when you get distracted.")
            notes = st.text_area("What are you working on?", value=t.get("notes",""), placeholder="e.g. Revise Newton's laws and solve 10 problems")
            if distractions != t.get("distractions",0) or notes != t.get("notes",""):
                t["distractions"] = int(distractions); t["notes"] = notes; save_timer()
            st.caption("Your notes and distraction count are saved with the session when the 50-minute focus finishes.")
        st.markdown("### Timer rules")
        st.markdown("- **Focus:** 50 minutes\n- **Break:** 10 minutes\n- Completed focus sessions are saved automatically.\n- Keep this page open while the timer runs.")
        st.warning("Keep this app open while studying. Browser or server sleep may delay the on-screen alert; elapsed time is calculated from timestamps.")

elif page == "Tasks":
    st.title("Task Manager")
    st.caption("Turn your study plan into clear, manageable actions.")
    with st.expander("＋ Add a new task", expanded=tasks.empty):
        with st.form("new_task", clear_on_submit=True):
            title = st.text_input("Task name", placeholder="e.g. Complete physics chapter 3")
            subject = st.text_input("Subject", placeholder="Physics, Math, English…")
            col1,col2,col3 = st.columns(3)
            priority = col1.selectbox("Priority", ["High","Medium","Low"], index=1)
            due = col2.date_input("Due date", value=None)
            estimate = col3.number_input("Estimated minutes", min_value=5, max_value=600, value=30, step=5)
            submitted = st.form_submit_button("Add task", type="primary")
            if submitted:
                if not title.strip():
                    st.error("Please enter a task name.")
                else:
                    add_task(title, subject, priority, due, estimate)
                    st.success("Task added.")
                    st.rerun()
    tasks = load_tasks()
    if tasks.empty:
        st.info("Your task list is empty. Add a task above to get started.")
    else:
        filt = st.segmented_control("Show", ["All","Pending","Completed"], default="All")
        shown = tasks if filt == "All" else tasks[tasks["status"] == filt]
        for _, task in shown.iterrows():
            with st.container(border=True):
                col1,col2,col3 = st.columns([5,1.5,1.5])
                col1.markdown(f"**{task['title']}**")
                col1.caption(f"{task['subject'] or 'General'} · {task['priority']} priority · {int(task['estimated_minutes'])} min" + (f" · Due {task['due_date']}" if task["due_date"] else ""))
                if task["status"] == "Completed":
                    col2.success("Completed")
                else:
                    if col2.button("Complete", key=f"complete_{task['id']}"):
                        with connect() as c:
                            c.execute("UPDATE tasks SET status='Completed', completed_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), int(task["id"])))
                            c.commit()
                        st.rerun()
                if col3.button("Delete", key=f"delete_{task['id']}"):
                    with connect() as c:
                        c.execute("DELETE FROM tasks WHERE id=?", (int(task["id"]),))
                        c.commit()
                    st.rerun()

elif page == "Progress & Analytics":
    st.title("Progress & Analytics")
    st.caption("Understand your study habits with timer sessions and manually logged study time.")
    sessions = load_sessions()
    tasks = load_tasks()
    if sessions.empty:
        st.info("No completed focus sessions yet. Complete your first 50-minute focus session to start building your analytics.")
    else:
        sessions["completed_dt"] = pd.to_datetime(sessions["completed_at"], errors="coerce")
        sessions["day"] = sessions["completed_dt"].dt.date
        last7 = sessions[sessions["completed_dt"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]
        c1,c2,c3 = st.columns(3)
        c1.metric("Study time · last 7 days", f"{int(last7['duration_minutes'].sum())//60}h {int(last7['duration_minutes'].sum())%60:02d}m")
        c2.metric("Focus sessions · last 7 days", len(last7))
        c3.metric("Distractions logged", int(last7["distractions"].sum()))
        daily = sessions.groupby("day", as_index=False)["duration_minutes"].sum()
        daily = daily[daily["day"] >= date.today() - timedelta(days=29)]
        fig = px.bar(daily, x="day", y="duration_minutes", title="Daily study time", labels={"day":"Date","duration_minutes":"Minutes studied"})
        fig.update_layout(paper_bgcolor="#101827", plot_bgcolor="#101827", font_color="#F8FAFC", title_font_color="#F8FAFC")
        fig.update_traces(marker_color="#2DD4BF")
        st.plotly_chart(fig, use_container_width=True)
        by_subject = sessions.copy()
        by_subject["subject"] = by_subject["subject"].replace("", "General study").fillna("General study")
        subject_data = by_subject.groupby("subject", as_index=False)["duration_minutes"].sum()
        fig2 = px.pie(subject_data, names="subject", values="duration_minutes", hole=.55, title="Study time by subject")
        fig2.update_layout(paper_bgcolor="#101827", font_color="#F8FAFC", title_font_color="#F8FAFC")
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("### Session history")
        view = sessions[["completed_at","subject","duration_minutes","distractions","notes"]].copy()
        view.columns = ["Completed at","Subject","Minutes","Distractions","Notes"]
        st.dataframe(view, use_container_width=True, hide_index=True)
    if not tasks.empty:
        st.markdown("### Task completion")
        total = len(tasks); complete = int((tasks["status"]=="Completed").sum())
        st.progress(complete/total if total else 0)
        st.caption(f"{complete} of {total} tasks completed ({round(complete/total*100) if total else 0}%).")


elif page == "Study Log":
    st.title("Study Log")
    st.caption("Record study time by subject — even if you studied without using the focus timer.")
    st.markdown("### Add a study session")
    with st.form("manual_study_log", clear_on_submit=True):
        subject_name = st.text_input("Subject", placeholder="e.g. Mathematics")
        duration = st.number_input("Study duration (minutes)", min_value=1, max_value=1440, value=60, step=5)
        study_day = st.date_input("Date studied", value=date.today())
        notes = st.text_area("What did you study? (optional)", placeholder="e.g. Algebra exercises, chapter 4")
        save_log = st.form_submit_button("Save study time", type="primary")
        if save_log:
            if not subject_name.strip():
                st.error("Please enter a subject name.")
            else:
                # Keep the selected study date for meaningful daily/subject reporting.
                completed = datetime.combine(study_day, datetime.now().time()).isoformat(timespec="seconds")
                started = (datetime.combine(study_day, datetime.now().time()) - timedelta(minutes=int(duration))).isoformat(timespec="seconds")
                with connect() as c:
                    c.execute(
                        "INSERT INTO sessions(subject,duration_minutes,session_type,distractions,notes,started_at,completed_at) VALUES(?,?,?,?,?,?,?)",
                        (subject_name.strip(), int(duration), "Manual log", 0, notes.strip(), started, completed)
                    )
                    c.commit()
                st.success(f"Saved {int(duration)} minutes for {subject_name.strip()}.")
                st.rerun()

    st.markdown("### Time spent by subject")
    all_sessions = load_sessions()
    if all_sessions.empty:
        st.info("No study time recorded yet. Add a session above or complete a focus timer.")
    else:
        all_sessions["subject_display"] = all_sessions["subject"].replace("", "General study").fillna("General study")
        subject_totals = all_sessions.groupby("subject_display", as_index=False)["duration_minutes"].sum()
        subject_totals = subject_totals.sort_values("duration_minutes", ascending=False)
        subject_totals["Total time"] = subject_totals["duration_minutes"].apply(
            lambda m: f"{int(m)//60}h {int(m)%60:02d}m" if int(m) >= 60 else f"{int(m)} min"
        )
        chart = px.bar(subject_totals, x="subject_display", y="duration_minutes", title="Which subjects get most of your time?",
                       labels={"subject_display":"Subject", "duration_minutes":"Minutes studied"})
        chart.update_layout(paper_bgcolor="#101827", plot_bgcolor="#101827", font_color="#F8FAFC", title_font_color="#F8FAFC")
        chart.update_traces(marker_color="#2DD4BF")
        st.plotly_chart(chart, use_container_width=True)
        st.dataframe(subject_totals[["subject_display", "Total time"]].rename(columns={"subject_display":"Subject"}), use_container_width=True, hide_index=True)
        st.caption("The totals include completed focus sessions and study time you log manually.")
        st.markdown("### Recent study entries")
        recent = all_sessions[["completed_at","subject","duration_minutes","session_type","notes"]].copy()
        recent.columns = ["Date/time","Subject","Minutes","Entry type","Notes"]
        st.dataframe(recent.head(20), use_container_width=True, hide_index=True)


elif page == "Settings":
    st.title("Settings & Data")
    st.caption("Make the dashboard work for your study routine.")
    goal = st.number_input("Daily study goal (minutes)", min_value=30, max_value=900, value=int(get_setting("daily_goal_minutes",240)), step=15)
    if st.button("Save daily goal", type="primary"):
        set_setting("daily_goal_minutes", int(goal))
        st.success("Daily goal saved.")
        st.rerun()
    st.markdown("### Export your records")
    tasks = load_tasks()
    sessions = load_sessions()
    col1,col2 = st.columns(2)
    with col1:
        st.download_button("Download tasks CSV", tasks.to_csv(index=False).encode("utf-8"), file_name="study_tasks.csv", mime="text/csv", use_container_width=True)
    with col2:
        st.download_button("Download study sessions CSV", sessions.to_csv(index=False).encode("utf-8"), file_name="study_sessions.csv", mime="text/csv", use_container_width=True)
    st.markdown("### Data notes")
    st.info("Your tasks, completed focus sessions, timer state, and daily goal are stored in student_progress.db in the app folder. Back up this file periodically.")
    st.warning("Avoid deleting student_progress.db unless you have exported or backed up your records.")
