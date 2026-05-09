# Canvas Grade Tracker — Council Rock

Automated grade scraper for councilrock.instructure.com.
Logs into each student account, pulls grades, stores history, and generates a trend report.

---

## One-time Setup

```bash
# 1. Install Python dependencies
pip install playwright

# 2. Install the browser (only needed once)
playwright install chromium

# 3. Fill in your kids' credentials
#    Edit students.json with their Canvas usernames and passwords
```

---

## Usage

```bash
# Normal run — browser animates on screen so you can watch
python canvas_grades.py

# Silent / background mode
python canvas_grades.py --headless

# Regenerate the HTML report without scraping (uses saved data)
python3 canvas_grades.py --report-only
```

---

## Files

| File | Purpose |
|------|---------|
| `students.json` | Student credentials — keep this private! |
| `grades_data.json` | Historical grade snapshots (auto-created) |
| `grades_report.html` | Opens automatically after each run |

---

## Automating with Windows Task Scheduler or macOS cron

**macOS/Linux** — run every day at 4 PM:
```
0 16 * * * cd /path/to/folder && python canvas_grades.py --headless
```

**Windows Task Scheduler:**
- Action: `python canvas_grades.py --headless`
- Start in: folder where the script lives
- Trigger: Daily at preferred time

---

## Trend Tracking

Grades are stored as daily snapshots. The HTML report shows:
- 📈 Line chart per student showing grade trends over time
- ▲/▼ arrows showing change since last snapshot
- Color-coded scores (green A, blue B, yellow C, orange D, red F)

More snapshots = better trend data. Run it weekly for best results.

---

## Privacy Note

`students.json` contains passwords — keep it on your local machine only.
Add it to `.gitignore` if you put this in a git repo.
