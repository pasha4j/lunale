"""
Canvas Grade Tracker
Council Rock School District — councilrock.instructure.com

Run:  python canvas_grades.py
First time: pip install playwright && playwright install chromium
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Config ────────────────────────────────────────────────────────────────────
CANVAS_URL   = "https://councilrock.instructure.com"
DATA_FILE    = Path("grades_data.json")
REPORT_FILE  = Path("grades_report.html")
HEADLESS     = False   # Set True to run silently in the background
SLOW_MO      = 600     # ms between actions (makes it "animated"); set 0 for speed

# ── Load students from config ─────────────────────────────────────────────────
CONFIG_FILE = Path("students.json")

def load_students():
    if not CONFIG_FILE.exists():
        sample = [
            {"name": "Student 1", "username": "student1@crsd.org", "password": "password1"},
            {"name": "Student 2", "username": "student2@crsd.org", "password": "password2"},
            {"name": "Student 3", "username": "student3@crsd.org", "password": "password3"},
        ]
        CONFIG_FILE.write_text(json.dumps(sample, indent=2))
        print(f"✏️  Created {CONFIG_FILE} — fill in real credentials and re-run.")
        sys.exit(0)
    return json.loads(CONFIG_FILE.read_text())


# ── Data helpers ──────────────────────────────────────────────────────────────
def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))

def today():
    return datetime.now().strftime("%Y-%m-%d")

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ── Scraper ───────────────────────────────────────────────────────────────────
def scrape_student(page, student):
    name = student["name"]
    print(f"\n{'─'*50}")
    print(f"  👤 {name}")
    print(f"{'─'*50}")

    # Login
    print("  → Navigating to login page…")
    page.goto(f"{CANVAS_URL}/login/canvas", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    # Take a diagnostic screenshot on first student to see what we're dealing with
    screenshot_path = f"login_page_{name.replace(' ','_')}.png"
    page.screenshot(path=screenshot_path)
    print(f"  📸 Screenshot saved → {screenshot_path}")
    print(f"  📍 Current URL: {page.url}")

    # Check if this is a Google SSO page
    google_btn = page.query_selector("a[href*='google'], button[data-auth-provider*='google'], .ic-SSOButton--Google, [class*='google']")
    if google_btn:
        print("  → Detected Google SSO — clicking Google login…")
        google_btn.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"google_login_{name.replace(' ','_')}.png")
        print(f"  📍 After Google click URL: {page.url}")

        # Fill Google email
        email_field = page.query_selector("input[type=email], input[name=identifier]")
        if email_field:
            email_field.fill(student["username"])
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)

            # Fill Google password
            pw_field = page.query_selector("input[type=password], input[name=password]")
            if pw_field:
                pw_field.fill(student["password"])
                page.keyboard.press("Enter")
            else:
                print("  ✗  Could not find Google password field")
                return None
        else:
            print("  ✗  Could not find Google email field")
            return None

    else:
        # Standard Canvas username/password form
        print("  → Using Canvas username/password form…")
        username_field = page.query_selector("#pseudonym_session_unique_id, input[name='pseudonym_session[unique_id]']")
        password_field = page.query_selector("#pseudonym_session_password, input[name='pseudonym_session[password]']")

        if not username_field or not password_field:
            print(f"  ✗  Could not find login fields — check screenshot: {screenshot_path}")
            return None

        username_field.fill(student["username"])
        password_field.fill(student["password"])
        print("  → Submitting…")
        # Submit via Enter on the password field
        password_field.press("Enter")

    # Wait for successful navigation away from login
    try:
        page.wait_for_function(
            "() => !window.location.href.includes('/login')",
            timeout=20000
        )
    except PWTimeout:
        page.screenshot(path=f"login_failed_{name.replace(' ','_')}.png")
        print(f"  ✗  Login failed for {name} — see login_failed_{name.replace(' ','_')}.png")
        return None

    if "login" in page.url and "login_success" not in page.url:
        print(f"  ✗  Still on login page — possible wrong credentials or MFA for {name}")
        return None

    print(f"  ✓  Logged in as {name}")

    # Go to grades overview
    print("  → Loading grades…")
    page.goto(f"{CANVAS_URL}/grades", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    # Try to find grade rows — Canvas renders a table with course + score
    grades = {}

    # Method 1: consolidated /grades page (shows all courses)
    rows = page.query_selector_all("tr.student_assignment, tr[class*='course']")

    # Method 2: course cards on dashboard → follow each to grades
    if not rows:
        grades = scrape_via_courses(page, name)
    else:
        for row in rows:
            try:
                course_el = row.query_selector(".course_name, .course-title, td:first-child")
                score_el  = row.query_selector(".final_grade, .score, td:last-child")
                if course_el and score_el:
                    course = course_el.inner_text().strip()
                    score  = score_el.inner_text().strip()
                    if course and score:
                        grades[course] = score
            except Exception:
                pass

    if not grades:
        print("  ↪  Trying course-by-course method…")
        grades = scrape_via_courses(page, name)

    print(f"  ✓  Found {len(grades)} courses")
    for c, g in grades.items():
        print(f"     {c}: {g}")

    return grades


def scrape_via_courses(page, name):
    """Visit each course's /grades page individually."""
    grades = {}

    # Collect course links from dashboard or courses list
    page.goto(f"{CANVAS_URL}/courses", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    # Canvas courses page lists enrolled courses
    course_links = page.query_selector_all("a[href*='/courses/']")
    seen_ids = set()
    course_urls = []

    for link in course_links:
        href = link.get_attribute("href") or ""
        # Only top-level course URLs like /courses/12345
        parts = [p for p in href.split("/") if p]
        if len(parts) == 2 and parts[0] == "courses" and parts[1].isdigit():
            cid = parts[1]
            if cid not in seen_ids:
                seen_ids.add(cid)
                label = link.inner_text().strip() or f"Course {cid}"
                course_urls.append((label, f"{CANVAS_URL}/courses/{cid}/grades"))

    for label, url in course_urls:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            # Look for the final grade summary
            score = None
            selectors = [
                ".student_assignment.final_grade .grade",
                "#student_information .grade",
                ".final-grade .grade",
                "span.grade",
                "#grades_summary .grade",
            ]
            for sel in selectors:
                el = page.query_selector(sel)
                if el:
                    txt = el.inner_text().strip()
                    if txt and txt not in ("", "–", "N/A"):
                        score = txt
                        break

            # Fallback: grab percentage from page title or summary bar
            if not score:
                summary = page.query_selector(".grading_periods_selector, .course_grade")
                if summary:
                    score = summary.inner_text().strip()

            if not score:
                # Last resort: look for any element with a % sign near "Final Grade"
                content = page.content()
                import re
                m = re.search(r'Final Grade[^%\d]*?([\d.]+%|[A-F][+-]?)', content)
                if m:
                    score = m.group(1)

            if score:
                grades[label] = score
                print(f"     ✓ {label}: {score}")
            else:
                print(f"     – {label}: (no grade found)")

        except Exception as e:
            print(f"     ✗ {label}: error — {e}")

    return grades


# ── Report generator ──────────────────────────────────────────────────────────
def generate_report(all_data):
    """Generate a polished HTML report with Chart.js trend charts."""

    # Build per-student, per-course time series
    students_series = {}   # {student: {course: [(date, score), ...]}}

    for student, snapshots in all_data.items():
        students_series[student] = {}
        for snap in snapshots:
            date = snap["date"]
            for course, raw_score in snap["grades"].items():
                score = parse_score(raw_score)
                if score is None:
                    continue
                if course not in students_series[student]:
                    students_series[student][course] = []
                students_series[student][course].append((date, score))

    # Sort each series by date
    for student in students_series:
        for course in students_series[student]:
            students_series[student][course].sort(key=lambda x: x[0])

    # Build JS datasets
    chart_blocks = ""
    COLORS = [
        "#6EE7B7","#60A5FA","#F472B6","#FBBF24","#A78BFA",
        "#34D399","#F87171","#38BDF8","#FB923C","#C084FC"
    ]

    for student, courses in students_series.items():
        if not courses:
            continue

        all_dates = sorted({d for series in courses.values() for d, _ in series})
        datasets = []
        for i, (course, series) in enumerate(courses.items()):
            date_to_score = {d: s for d, s in series}
            data_points = [date_to_score.get(d) for d in all_dates]
            color = COLORS[i % len(COLORS)]
            datasets.append({
                "label": course,
                "data": data_points,
                "borderColor": color,
                "backgroundColor": color + "22",
                "tension": 0.3,
                "fill": False,
                "pointRadius": 5,
                "pointHoverRadius": 8,
                "spanGaps": True,
            })

        labels_js = json.dumps(all_dates)
        datasets_js = json.dumps(datasets)
        canvas_id = f"chart_{student.replace(' ','_')}"

        # Summary table for latest grades
        latest_rows = ""
        for course, series in courses.items():
            if series:
                last_date, last_score = series[-1]
                trend = ""
                if len(series) >= 2:
                    delta = last_score - series[-2][1]
                    if delta > 0:   trend = f'<span class="up">▲ {delta:.1f}</span>'
                    elif delta < 0: trend = f'<span class="dn">▼ {abs(delta):.1f}</span>'
                    else:           trend = '<span class="flat">→</span>'
                grade_class = grade_color_class(last_score)
                latest_rows += f"""
                <tr>
                  <td class="course-name">{course}</td>
                  <td class="score {grade_class}">{last_score:.1f}%</td>
                  <td class="trend">{trend}</td>
                  <td class="date">{last_date}</td>
                </tr>"""

        chart_blocks += f"""
        <section class="student-block">
          <h2 class="student-name">{student}</h2>
          <div class="grade-grid">
            <div class="chart-wrap">
              <canvas id="{canvas_id}"></canvas>
            </div>
            <div class="table-wrap">
              <table class="grade-table">
                <thead><tr><th>Course</th><th>Grade</th><th>Trend</th><th>As of</th></tr></thead>
                <tbody>{latest_rows}</tbody>
              </table>
            </div>
          </div>
        </section>
        <script>
        (function(){{
          var ctx = document.getElementById('{canvas_id}').getContext('2d');
          new Chart(ctx, {{
            type: 'line',
            data: {{ labels: {labels_js}, datasets: {datasets_js} }},
            options: {{
              responsive: true,
              interaction: {{ mode: 'index', intersect: false }},
              plugins: {{
                legend: {{ labels: {{ color: '#e2e8f0', font: {{ family: 'DM Sans' }} }} }},
                tooltip: {{ callbacks: {{ label: function(c) {{ return c.dataset.label + ': ' + (c.parsed.y !== null ? c.parsed.y.toFixed(1) + '%' : 'N/A'); }} }} }}
              }},
              scales: {{
                x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
                y: {{ min: 50, max: 100, ticks: {{ color: '#94a3b8', callback: function(v){{ return v+'%'; }} }}, grid: {{ color: '#1e293b' }} }}
              }}
            }}
          }});
        }})();
        </script>
        """

    updated = now_ts()
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Grade Tracker — Council Rock</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;600;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:      #0a0f1a;
    --surface: #111827;
    --border:  #1e293b;
    --text:    #e2e8f0;
    --muted:   #64748b;
    --accent:  #6EE7B7;
    --up:      #4ade80;
    --dn:      #f87171;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; padding: 2rem; }}

  header {{ border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; margin-bottom: 2.5rem; }}
  header h1 {{ font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; }}
  header h1 span {{ color: var(--accent); }}
  .subtitle {{ color: var(--muted); margin-top: 0.3rem; font-size: 0.9rem; font-family: 'DM Mono', monospace; }}

  .student-block {{ margin-bottom: 3.5rem; }}
  .student-name {{
    font-size: 1.4rem; font-weight: 700; margin-bottom: 1.25rem;
    padding-left: 1rem; border-left: 3px solid var(--accent);
  }}

  .grade-grid {{ display: grid; grid-template-columns: 1fr 380px; gap: 1.5rem; }}
  @media (max-width: 900px) {{ .grade-grid {{ grid-template-columns: 1fr; }} }}

  .chart-wrap {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.25rem;
  }}
  .table-wrap {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.25rem; overflow-x: auto;
  }}

  .grade-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  .grade-table th {{ color: var(--muted); font-weight: 600; text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  .grade-table td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border); }}
  .grade-table tr:last-child td {{ border-bottom: none; }}
  .course-name {{ font-weight: 500; }}
  .score {{ font-family: 'DM Mono', monospace; font-weight: 600; font-size: 0.95rem; }}
  .score.a {{ color: #4ade80; }}
  .score.b {{ color: #60a5fa; }}
  .score.c {{ color: #fbbf24; }}
  .score.d {{ color: #f97316; }}
  .score.f {{ color: #f87171; }}
  .trend .up {{ color: var(--up); font-size: 0.82rem; }}
  .trend .dn {{ color: var(--dn); font-size: 0.82rem; }}
  .trend .flat {{ color: var(--muted); font-size: 0.82rem; }}
  .date {{ color: var(--muted); font-size: 0.78rem; font-family: 'DM Mono', monospace; }}

  footer {{ color: var(--muted); font-size: 0.8rem; text-align: center; margin-top: 3rem; font-family: 'DM Mono', monospace; }}
</style>
</head>
<body>
<header>
  <h1>Grade <span>Tracker</span></h1>
  <p class="subtitle">Council Rock School District · Last updated {updated}</p>
</header>
{chart_blocks}
<footer>Generated by canvas_grades.py · Data stored in grades_data.json</footer>
</body>
</html>"""

    REPORT_FILE.write_text(html)
    print(f"\n✅  Report saved → {REPORT_FILE.resolve()}")


def parse_score(raw):
    """Convert grade string to float percentage."""
    import re
    if raw is None:
        return None
    raw = str(raw).strip()
    # Already a percentage number
    m = re.search(r'([\d.]+)\s*%', raw)
    if m:
        return float(m.group(1))
    # Letter grade fallback
    letter_map = {"A+":98,"A":95,"A-":92,"B+":88,"B":85,"B-":82,
                  "C+":78,"C":75,"C-":72,"D+":68,"D":65,"D-":62,"F":50}
    up = raw.upper().strip()
    if up in letter_map:
        return float(letter_map[up])
    # Plain number
    m2 = re.search(r'([\d.]+)', raw)
    if m2:
        v = float(m2.group(1))
        return v if v <= 100 else None
    return None


def grade_color_class(score):
    if score >= 90: return "a"
    if score >= 80: return "b"
    if score >= 70: return "c"
    if score >= 60: return "d"
    return "f"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Canvas grade scraper")
    parser.add_argument("--headless", action="store_true", help="Run browser in background")
    parser.add_argument("--report-only", action="store_true", help="Regenerate report without scraping")
    args = parser.parse_args()

    students = load_students()
    all_data = load_data()

    if not args.report_only:
        headless = HEADLESS or args.headless
        print(f"\n🎓 Canvas Grade Tracker — Council Rock")
        print(f"   Mode: {'headless' if headless else 'animated (you can watch!)'}")
        print(f"   Students: {len(students)}")
        print(f"   Run date: {now_ts()}\n")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless,
                slow_mo=SLOW_MO if not headless else 0,
            )
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            today_str = today()

            for student in students:
                sname = student["name"]
                grades = scrape_student(page, student)

                if grades:
                    if sname not in all_data:
                        all_data[sname] = []

                    # Replace today's snapshot if it exists, else append
                    existing = [s for s in all_data[sname] if s["date"] != today_str]
                    existing.append({"date": today_str, "timestamp": now_ts(), "grades": grades})
                    all_data[sname] = existing

                    save_data(all_data)
                    print(f"  💾  Saved {len(grades)} grades for {sname}")

                # Logout before next student
                try:
                    page.goto(f"{CANVAS_URL}/logout", wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            browser.close()

    print("\n📊 Generating HTML report…")
    generate_report(all_data)

    import webbrowser
    webbrowser.open(str(REPORT_FILE.resolve()))


if __name__ == "__main__":
    main()
