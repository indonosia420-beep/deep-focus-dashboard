# Deep Focus — Student Productivity Dashboard

A local-first Streamlit study dashboard with a **50-minute focus / 10-minute break** timer.

## Features
- 50/10 focus timer with start, pause, resume, and reset
- Focus sessions saved automatically when the full 50-minute timer completes
- Subject, notes, and distraction tracking
- Manual Study Log for any duration (e.g. 60 minutes Mathematics, 36 minutes Chemistry)
- Subject totals and chart to compare where your study time goes
- Task manager with priority, due date, estimates, completion, and deletion
- Daily study goal, streak, weekly study analytics, subject breakdown, session history
- CSV exports for tasks and study sessions
- SQLite database stored locally beside the app

## Run it
1. Install Python 3.10 or newer.
2. Extract this folder.
3. Open a terminal in this folder and run:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

4. The app will open in your browser. Keep it running while you study.

## Important notes
- The timer calculates remaining time from timestamps, so a page refresh does not simply restart the countdown.
- Keep the app/server running during a focus session. If your computer or hosting server sleeps, the visual update/alert may be delayed.
- Your data is saved in `student_progress.db`. Back up this file periodically.
- Completed focus sessions are saved only when a full 50-minute focus timer reaches zero; resetting or leaving early does not count as a completed session.
