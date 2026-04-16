"""
Multi-Source Internship Scraper
================================
Scrapes internship listings from:
  1. Unstop       (unstop.com)
  2. Internshala  (internshala.com)
  3. Naukri        (naukri.com/internship)
  4. AICTE        (internship.aicte-india.org)

All results are merged into a single CSV with a "source" column.

Eligibility fields (CGPA, branch, gender) are extracted ONLY when explicitly
stated on the listing — never guessed from job description text.
Female-specific programs are flagged in the "gender" column as "Girls Only".

Requirements:
    pip install selenium pandas beautifulsoup4 lxml

Usage:
    python internship_scraper.py                          # all sources, 2 pages each
    python internship_scraper.py --pages 3                # 3 pages per source
    python internship_scraper.py --sources unstop,internshala
    python internship_scraper.py --keyword "data science"
    python internship_scraper.py --no-headless            # see the browser (debug)
    python internship_scraper.py --no-details             # skip detail pages (fast)
"""

import re
import time
import argparse
import json
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ── Shared constants ───────────────────────────────────────────────────────────

BRANCH_KEYWORDS = [
    "computer science", "cse", "information technology", "it",
    "electronics", "ece", "eee", "electrical", "mechanical", "civil",
    "chemical", "biotechnology", "biotech", "data science",
    "mba", "bca", "mca", "mathematics", "statistics", "physics",
    "commerce", "management", "finance", "marketing",
]

# Female-specific program keywords — checked in title + eligibility block
FEMALE_PROGRAM_RE = re.compile(
    r"\b(women|woman|girls?|female|she\s*codes?|girls?\s*who\s*code|"
    r"pragati|saksham|anudip|nasscom\s*foundation|sheroes|"
    r"grace\s*hopper|pwd\s*women|women\s*in\s*tech|"
    r"girls?\s*only|female\s*only|women\s*only|only\s*(?:girls?|women|female)|"
    r"ascend|ingenium|unnati|springboard\s*women|"
    r"insight\s*program|women\s*possibilities|non.?binary)\b",
    re.I,
)


# ── Driver ─────────────────────────────────────────────────────────────────────

def make_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def get_html(driver, url: str, wait_css: str = None, scroll: bool = True,
             delay: float = 2.0) -> str:
    driver.get(url)
    if wait_css:
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
            )
        except Exception:
            pass
    if scroll:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(delay)
    return driver.page_source


# ── Shared eligibility parsers (eligibility block ONLY) ───────────────────────

def parse_cgpa(elig: str) -> str:
    if not elig.strip():
        return "Not mentioned"
    pats = [
        re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:cgpa|gpa|cpi|aggregate|pointer)", re.I),
        re.compile(r"(?:cgpa|gpa|cpi|aggregate|pointer)\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(?:/\s*10)?", re.I),
        re.compile(r"(?:minimum|min\.?|at\s*least|above|>=?|≥)\s*(\d+(?:\.\d+)?)\s*(?:cgpa|gpa|cpi|pointer|aggregate)", re.I),
    ]
    for p in pats:
        m = p.search(elig)
        if m:
            try:
                if 1.0 <= float(m.group(1)) <= 10.0:
                    return m.group(1)
            except ValueError:
                pass
    return "Not mentioned"


def parse_branches(elig: str) -> str:
    if not elig.strip():
        return "Not mentioned"
    tl = elig.lower()
    if re.search(r"\ball\s*(branches|engineering|streams|courses|students)\b", tl):
        return "All"
    if re.search(r"\b(open\s+to\s+all|all\s+are\s+eligible)\b", tl):
        return "All"
    found, seen = [], set()
    for kw in BRANCH_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", tl):
            if kw in ("cse", "computer science"):           c = "Computer Science"
            elif kw in ("it", "information technology"):    c = "Information Technology"
            elif kw in ("ece", "eee", "electronics"):       c = "Electronics"
            elif kw in ("biotech", "biotechnology"):        c = "Biotechnology"
            elif kw in ("all branches", "any branch"):      return "All"
            else:                                            c = kw.title()
            if c not in seen:
                seen.add(c); found.append(c)
    return ", ".join(found) if found else "Not mentioned"


def parse_gender(elig: str, title: str = "") -> str:
    """Check eligibility block AND program title for female-specific signals."""
    combined = (elig + " " + title).lower()
    if FEMALE_PROGRAM_RE.search(combined):
        return "Girls Only"
    if re.search(r"\b(boys?\s*only|male\s*only|open\s*(?:only\s*)?to\s*(?:boys?|men|male))\b", combined, re.I):
        return "Boys Only"
    return "All"



# ── Shared field extractors ────────────────────────────────────────────────

def extract_mode(text: str) -> str:
    """Extract internship mode: Work From Home / Remote / Hybrid / On-site."""
    tl = text.lower()
    if re.search(r"work\s*from\s*home|wfh", tl):
        return "Work From Home"
    if re.search(r"\bremote\b", tl):
        return "Remote"
    if re.search(r"\bhybrid\b", tl):
        return "Hybrid"
    if re.search(r"\bon.?site\b|\bin.?office\b|\bin.?person\b", tl):
        return "On-site"
    return "Not mentioned"


def extract_internship_type(text: str) -> str:
    """Extract internship type: Full Time / Part Time / Flexible."""
    tl = text.lower()
    if re.search(r"part.?time", tl):
        return "Part Time"
    if re.search(r"full.?time", tl):
        return "Full Time"
    if re.search(r"flex", tl):
        return "Flexible"
    return "Not mentioned"


def extract_stipend(text: str) -> str:
    """
    Extract stipend/salary from text.
    Returns the raw matched string, or 'Not disclosed' / 'Unpaid'.
    """
    tl = text.lower()
    if re.search(r"\bunpaid\b|\bno\s*stipend\b|\bvolunteer\b", tl):
        return "Unpaid"

    # ₹ / INR patterns first
    patterns = [
        # "₹10,000/month", "INR 15000 per month"
        re.compile(
            r"(?:₹|inr|rs\.?)\s*([\d,]+(?:\.\d+)?)\s*"
            r"(?:[-–/]?\s*([\d,]+(?:\.\d+)?))?\s*"
            r"(?:per|/|p\.?)\s*(?:month|mo|m)", re.I
        ),
        # "10000 per month"
        re.compile(
            r"([\d,]{4,})\s*(?:[-–/]\s*([\d,]{4,}))?\s*"
            r"(?:per|/|p\.?)\s*(?:month|mo)", re.I
        ),
        # "stipend: 10000", "salary: ₹15,000"
        re.compile(
            r"(?:stipend|salary)[:\s]+(?:₹|inr|rs\.?)?\s*([\d,]+)", re.I
        ),
        # Lakh/K shorthand "1.5 LPA", "20K/month"
        re.compile(
            r"([\d.]+)\s*(?:lpa|lakh|l|k)\s*(?:per\s*(?:month|annum|year))?",
            re.I
        ),
    ]

    for pat in patterns:
        m = pat.search(text)
        if m:
            raw = m.group(0).strip()
            # Clean up whitespace
            raw = re.sub(r"\s+", " ", raw)
            return raw

    # Generic: any number near stipend/salary keyword
    m = re.search(
        r"(?:stipend|salary|pay|compensation)[^\d]{0,20}([\d,₹]+)", text, re.I
    )
    if m:
        return m.group(1).strip()

    return "Not disclosed"


def extract_duration(text: str) -> str:
    """
    Extract internship duration from text.
    Returns e.g. '2 months', '6 weeks', '3-6 months', or 'Not mentioned'.
    Only returns a value when explicitly stated — never guesses.
    """
    patterns = [
        # "3-6 months", "2 to 4 months"
        re.compile(
            r"(\d+)\s*(?:to|[-–])\s*(\d+)\s*(months?|weeks?|days?|years?)", re.I
        ),
        # "6 months", "12 weeks", "45 days"
        re.compile(r"(\d+)\s*(months?|weeks?|days?|years?)", re.I),
        # "one month", "two weeks"
        re.compile(
            r"(one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s*"
            r"(months?|weeks?|days?)", re.I
        ),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(0).strip()
    return "Not mentioned"


def empty_record(source: str) -> dict:
    return {
        "source":           source,
        "title":            "N/A",
        "company":          "N/A",
        "location":         "N/A",
        # ── Key fields requested ──────────────────────────────────────────
        "stipend":          "Not disclosed",   # e.g. "INR 10,000/month", "Unpaid"
        "duration":         "Not mentioned",   # e.g. "2 months", "6 weeks"
        "mode":             "Not mentioned",   # Work From Home / On-site / Hybrid / Remote
        "internship_type":  "Not mentioned",   # Full Time / Part Time / Flexible
        # ── Eligibility ───────────────────────────────────────────────────
        "branch_required":  "Not mentioned",   # CSE / ECE / All / etc.
        "cgpa_required":    "Not mentioned",
        "gender":           "All",
        "eligibility_raw":  "Not mentioned",
        # ── Access / Navigation ────────────────────────────────────────────
        "apply_link":       "",
        "access_note":      "",                # Step-by-step guide if page blocked
        # ── Metadata ──────────────────────────────────────────────────────
        "priority":         None,              # 1 / 2 / 3
        "fame_score":       None,              # 1–10
        # ── Other ─────────────────────────────────────────────────────────
        "skills":           "N/A",
        "deadline":         "N/A",
        "applicants":       "N/A",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 1 — UNSTOP
# ══════════════════════════════════════════════════════════════════════════════

def scrape_unstop(driver, pages: int, keyword: str, fetch_details: bool,
                  delay: float) -> list[dict]:
    print("\n  ── Unstop ──────────────────────────────────────────")
    base = "https://unstop.com/internships"
    records = []
    seen_slugs = set()

    for page in range(1, pages + 1):
        url = base
        if keyword:
            url += f"?searchTerm={keyword.replace(' ', '%20')}"
        if page > 1:
            sep = "&" if keyword else "?"
            url += f"{sep}page={page}"

        print(f"  [Unstop page {page}/{pages}]", end=" ", flush=True)
        html = get_html(driver, url, wait_css="a[href*='/internships/']", delay=delay)
        soup = BeautifulSoup(html, "lxml")

        new = 0
        for a in soup.find_all("a", href=True):
            m = re.match(r"^/internships/([\w\-]+-\d+)$", a["href"])
            if not m or m.group(1) in seen_slugs:
                continue
            slug = m.group(1)
            seen_slugs.add(slug)
            rec = empty_record("Unstop")
            rec["apply_link"] = f"https://unstop.com/internships/{slug}"
            rec["title"] = slug.replace("-", " ").title()   # placeholder
            records.append(rec)
            new += 1
        print(f"found {new} new  (total Unstop: {len(records)})")
        time.sleep(delay)

    if fetch_details:
        print(f"\n  Fetching {len(records)} Unstop detail pages...")
        for i, rec in enumerate(records, 1):
            slug = rec["apply_link"].split("/internships/")[-1]
            print(f"    [{i:>3}/{len(records)}] {slug[:55]}", end=" ", flush=True)
            try:
                html = get_html(driver, rec["apply_link"], wait_css="h1", delay=delay * 0.6)
                _parse_unstop_detail(BeautifulSoup(html, "lxml"), rec)
                print((
                    f"\n         Stipend  : {rec.get('stipend','Not disclosed')}\n"
                    f"         Duration : {rec.get('duration','Not mentioned')}\n"
                    f"         Mode     : {rec.get('mode','Not mentioned')}\n"
                    f"         Type     : {rec.get('internship_type','Not mentioned')}\n"
                    f"         Branch   : {rec.get('branch_required','Not mentioned')}\n"
                    f"         CGPA     : {rec.get('cgpa_required','Not mentioned')}\n"
                    f"         Gender   : {rec.get('gender','All')}\n"
                    f"         Link     : {rec.get('apply_link','')}\n"
                ))
            except Exception as e:
                print(f"ERR:{e}")

    return records


def _parse_unstop_detail(soup: BeautifulSoup, rec: dict):
    h1 = soup.find("h1")
    if h1:
        rec["title"] = h1.get_text(strip=True)

    text = soup.get_text(" ", strip=True)

    # Company
    for sel in ["h2 a", "[class*='company']", "[class*='org-name']"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            rec["company"] = el.get_text(strip=True); break

    # Deadline
    m = re.search(r"Registration Deadline\s*[\*\n\s]+([\w\s,'\d:]+IST)", text, re.I)
    if m: rec["deadline"] = m.group(1).strip()

    # Applicants
    m = re.search(r"Applied\s*[\*\n\s]*([\d,]+)", text, re.I)
    if m: rec["applicants"] = m.group(1).replace(",", "")

    # Stipend — try Unstop label elements first
    stipend_found = False
    for tag in soup.find_all(string=re.compile(r"^stipend$", re.I)):
        p = tag.parent
        # Grab next sibling which contains the value
        nxt = p.find_next_sibling()
        if nxt:
            raw = nxt.get_text(" ", strip=True)
            if raw and len(raw) < 120:
                rec["stipend"] = raw; stipend_found = True; break
    if not stipend_found:
        # Regex on the Additional Information section
        m = re.search(r"Stipend\s*\n?(.*?)(?:Work Detail|Working Days|Job Type|Perks|$)",
                      text, re.I | re.S)
        block = m.group(1).strip() if m else text[:800]
        rec["stipend"] = extract_stipend(block)

    # Duration — Unstop shows it as "X Months" in Additional Information
    dur_found = False
    for tag in soup.find_all(string=re.compile(r"^duration$", re.I)):
        p = tag.parent
        nxt = p.find_next_sibling()
        if nxt:
            rec["duration"] = nxt.get_text(" ", strip=True)[:40]; dur_found = True; break
    if not dur_found:
        m = re.search(r"(?:Duration|Internship Duration)[:\s]+(\d[\w\s]{1,30}?)(?:Work|Job|Apply|$)",
                      text, re.I)
        rec["duration"] = m.group(1).strip() if m else extract_duration(text[:1000])

    # Mode — Unstop shows it under "Job Type" label
    mode_found = False
    for tag in soup.find_all(string=re.compile(r"^job\s*type$", re.I)):
        p = tag.parent
        nxt = p.find_next_sibling()
        if nxt:
            val = nxt.get_text(" ", strip=True)
            rec["mode"] = extract_mode(val) or val[:30]
            mode_found = True; break
    if not mode_found:
        rec["mode"] = extract_mode(text)

    # Internship type (Full Time / Part Time) — from "Job Timing" label
    type_found = False
    for tag in soup.find_all(string=re.compile(r"^job\s*timing$", re.I)):
        p = tag.parent
        nxt = p.find_next_sibling()
        if nxt:
            val = nxt.get_text(" ", strip=True)
            rec["internship_type"] = extract_internship_type(val) or val[:30]
            type_found = True; break
    if not type_found:
        rec["internship_type"] = extract_internship_type(text)

    # Eligibility block
    elig = _extract_elig_unstop(soup)
    rec["eligibility_raw"]   = elig or "Not mentioned"
    rec["cgpa_required"]     = parse_cgpa(elig)
    rec["branch_required"]   = parse_branches(elig)
    rec["gender"]            = parse_gender(elig, rec["title"])


def _extract_elig_unstop(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(string=re.compile(r"^Eligibility$", re.I)):
        parent = tag.parent
        nxt = parent.find_next_sibling()
        if nxt:
            return nxt.get_text(" ", strip=True)
        gp = parent.parent
        if gp:
            t = re.sub(r"Eligibility", "", gp.get_text(" ", strip=True), flags=re.I).strip()
            if t: return t
    pt = soup.get_text(" ", strip=True)
    m = re.search(
        r"Eligibility\s*[:\-]?\s*(.{5,300}?)(?:Application Deadline|Refer|Recruitment Process|Details|$)",
        pt, re.I | re.S
    )
    return m.group(1).strip() if m else ""


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 2 — INTERNSHALA
# ══════════════════════════════════════════════════════════════════════════════

def scrape_internshala(driver, pages: int, keyword: str, fetch_details: bool,
                       delay: float) -> list[dict]:
    print("\n  ── Internshala ─────────────────────────────────────")
    kw_slug = keyword.lower().replace(" ", "-") if keyword else ""
    records = []
    seen_urls = set()

    for page in range(1, pages + 1):
        if kw_slug:
            url = f"https://internshala.com/internships/{kw_slug}-internship/page-{page}/"
        else:
            url = f"https://internshala.com/internships/page-{page}/"

        print(f"  [Internshala page {page}/{pages}]", end=" ", flush=True)
        html = get_html(driver, url,
                        wait_css=".individual_internship, .internship_meta, [class*='internship']",
                        delay=delay)
        soup = BeautifulSoup(html, "lxml")
        new = 0

        # Each card has an <a> linking to the detail page
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not re.search(r"/internship/detail/", href):
                continue
            full = href if href.startswith("http") else "https://internshala.com" + href
            if full in seen_urls:
                continue
            seen_urls.add(full)

            rec = empty_record("Internshala")
            rec["apply_link"] = full

            # Try to pull basic info from the card
            card = a.find_parent()
            if card:
                for t in card.find_all(["h3", "h4", "strong"]):
                    txt = t.get_text(strip=True)
                    if len(txt) > 4:
                        rec["title"] = txt; break
                spans = [s.get_text(strip=True) for s in card.find_all("span") if s.get_text(strip=True)]
                if spans: rec["company"] = spans[0]

            records.append(rec)
            new += 1
        print(f"found {new} new  (total Internshala: {len(records)})")
        time.sleep(delay)

    if fetch_details:
        print(f"\n  Fetching {len(records)} Internshala detail pages...")
        for i, rec in enumerate(records, 1):
            print(f"    [{i:>3}/{len(records)}] {rec['apply_link'][-60:]}", end=" ", flush=True)
            try:
                html = get_html(driver, rec["apply_link"], wait_css="h1, .job-title", delay=delay * 0.6)
                _parse_internshala_detail(BeautifulSoup(html, "lxml"), rec)
                print((
                    f"\n         Stipend  : {rec.get('stipend','Not disclosed')}\n"
                    f"         Duration : {rec.get('duration','Not mentioned')}\n"
                    f"         Mode     : {rec.get('mode','Not mentioned')}\n"
                    f"         Type     : {rec.get('internship_type','Not mentioned')}\n"
                    f"         Branch   : {rec.get('branch_required','Not mentioned')}\n"
                    f"         CGPA     : {rec.get('cgpa_required','Not mentioned')}\n"
                    f"         Gender   : {rec.get('gender','All')}\n"
                    f"         Link     : {rec.get('apply_link','')}\n"
                ))
            except Exception as e:
                print(f"ERR:{e}")

    return records


def _parse_internshala_detail(soup: BeautifulSoup, rec: dict):
    text = soup.get_text(" ", strip=True)

    h1 = soup.find("h1")
    if h1: rec["title"] = h1.get_text(strip=True)

    # Company — Internshala shows it in .company_name or .internship_heading
    for sel in [".company_name a", ".company-name", "[class*='company']"]:
        el = soup.select_one(sel)
        if el: rec["company"] = el.get_text(strip=True); break

    # Stipend — try multiple CSS selectors Internshala uses
    stipend_selectors = [
        ".stipend", "#stipend", "[class*=stipend]",
        "[class*=salary]", ".salary",
        # Internshala detail page specific
        ".detail-salary-container", ".other-details-container",
    ]
    for sel in stipend_selectors:
        el = soup.select_one(sel)
        if el:
            raw = el.get_text(" ", strip=True)
            if raw and len(raw) < 100:
                rec["stipend"] = raw; break

    # Fallback: find "Stipend" label in page and grab adjacent value
    if rec["stipend"] == "Not disclosed":
        for tag in soup.find_all(string=re.compile(r"^stipend$", re.I)):
            p = tag.parent
            nxt = p.find_next_sibling()
            if nxt:
                rec["stipend"] = nxt.get_text(" ", strip=True)[:80]; break

    # Final fallback: regex on full text
    if rec["stipend"] == "Not disclosed":
        rec["stipend"] = extract_stipend(text[:1500])

    # Duration — Internshala shows it as "X months" near top of page
    # Try label-based extraction first
    dur_found = False
    for tag in soup.find_all(string=re.compile(r"^duration$", re.I)):
        p = tag.parent
        nxt = p.find_next_sibling()
        if nxt:
            rec["duration"] = extract_duration(nxt.get_text(" ", strip=True)) or nxt.get_text(strip=True)[:30]
            dur_found = True; break
    if not dur_found:
        # Look for duration in the detail metadata section
        for sel in ["[class*=duration]", ".duration", "#duration"]:
            el = soup.select_one(sel)
            if el:
                rec["duration"] = extract_duration(el.get_text(" ", strip=True)) or el.get_text(strip=True)[:30]
                dur_found = True; break
    if not dur_found:
        # Regex fallback
        m = re.search(r"(\d+\s*(?:months?|weeks?|days?)(?:\s*[-–]\s*\d+\s*(?:months?|weeks?|days?))?)", text, re.I)
        if m: rec["duration"] = m.group(1).strip()

    # Location
    for sel in [".location_link", "[class*='location']", ".locations"]:
        el = soup.select_one(sel)
        if el: rec["location"] = el.get_text(" ", strip=True); break

    # Deadline
    m = re.search(r"(?:apply\s*by|last\s*date)[:\s]*([\w\s,\d]+\d{4})", text, re.I)
    if m: rec["deadline"] = m.group(1).strip()

    # Skills
    skills_els = soup.select(".round_tabs, [class*='skill'], [class*='tag']")
    if skills_els:
        rec["skills"] = ", ".join(s.get_text(strip=True) for s in skills_els[:10])

    # Mode — Internshala encodes WFH in URL and page title
    url_str = rec.get("apply_link", "")
    if "work-from-home" in url_str.lower() or "work-from-home" in rec.get("title","").lower():
        rec["mode"] = "Work From Home"
    elif "hybrid" in url_str.lower():
        rec["mode"] = "Hybrid"
    else:
        rec["mode"] = extract_mode(text)

    # Internship type — Internshala encodes part-time in URL
    if "part-time" in url_str.lower():
        rec["internship_type"] = "Part Time"
    else:
        rec["internship_type"] = extract_internship_type(text)

    # Eligibility block — Internshala uses "Who can apply" section
    elig = _extract_elig_internshala(soup)
    rec["eligibility_raw"]   = elig or "Not mentioned"
    rec["cgpa_required"]     = parse_cgpa(elig)
    rec["branch_required"]   = parse_branches(elig)
    rec["gender"]            = parse_gender(elig, rec["title"])


def _extract_elig_internshala(soup: BeautifulSoup) -> str:
    # Internshala uses "Who can apply" as the eligibility heading
    for heading_text in ["Who can apply", "Eligibility", "Requirements"]:
        for tag in soup.find_all(string=re.compile(rf"^{heading_text}$", re.I)):
            parent = tag.parent
            # Grab the next container sibling
            nxt = parent.find_next_sibling()
            if nxt:
                return nxt.get_text(" ", strip=True)
            # Or the whole section
            section = parent.find_parent(["section", "div"])
            if section:
                t = re.sub(heading_text, "", section.get_text(" ", strip=True), flags=re.I).strip()
                if t: return t

    # Fallback regex on full text
    pt = soup.get_text(" ", strip=True)
    for label in ["Who can apply", "Eligibility Criteria", "Eligibility"]:
        m = re.search(
            r"(?:" + label + r")\s*[:\-]?\s*(.{5,400}?)(?:About|Skill|Number of|Apply|$)",
            pt, re.I | re.S
        )
        if m: return m.group(1).strip()
    return ""


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 3 — NAUKRI
# ══════════════════════════════════════════════════════════════════════════════

def scrape_naukri(driver, pages: int, keyword: str, fetch_details: bool,
                  delay: float) -> list[dict]:
    print("\n  ── Naukri ──────────────────────────────────────────")
    kw_slug = keyword.lower().replace(" ", "-") if keyword else "internship"
    records = []
    seen_urls = set()

    for page in range(1, pages + 1):
        url = f"https://www.naukri.com/{kw_slug}-internship-jobs?pageNo={page}"
        print(f"  [Naukri page {page}/{pages}]", end=" ", flush=True)
        html = get_html(driver, url,
                        wait_css=".jobTuple, .job-container, [class*='jobTuple']",
                        delay=delay + 1)   # Naukri is slower
        soup = BeautifulSoup(html, "lxml")
        new = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not re.search(r"naukri\.com/.+-\d+\?", href) and \
               not re.search(r"naukri\.com/job-listings", href):
                continue
            if href in seen_urls: continue
            seen_urls.add(href)

            rec = empty_record("Naukri")
            rec["apply_link"] = href

            card = a.find_parent()
            if card:
                for t in card.find_all(["a", "h2", "strong"]):
                    txt = t.get_text(strip=True)
                    if len(txt) > 4 and not txt.startswith("http"):
                        rec["title"] = txt; break

            records.append(rec)
            new += 1
        print(f"found {new} new  (total Naukri: {len(records)})")
        time.sleep(delay)

    if fetch_details:
        print(f"\n  Fetching {len(records)} Naukri detail pages...")
        for i, rec in enumerate(records, 1):
            print(f"    [{i:>3}/{len(records)}] {rec['apply_link'][-60:]}", end=" ", flush=True)
            try:
                html = get_html(driver, rec["apply_link"],
                                wait_css="h1.jd-header-title, .job-header",
                                delay=delay * 0.8)
                _parse_naukri_detail(BeautifulSoup(html, "lxml"), rec)
                print((
                    f"\n         Stipend  : {rec.get('stipend','Not disclosed')}\n"
                    f"         Duration : {rec.get('duration','Not mentioned')}\n"
                    f"         Mode     : {rec.get('mode','Not mentioned')}\n"
                    f"         Type     : {rec.get('internship_type','Not mentioned')}\n"
                    f"         Branch   : {rec.get('branch_required','Not mentioned')}\n"
                    f"         CGPA     : {rec.get('cgpa_required','Not mentioned')}\n"
                    f"         Gender   : {rec.get('gender','All')}\n"
                    f"         Link     : {rec.get('apply_link','')}\n"
                ))
            except Exception as e:
                print(f"ERR:{e}")

    return records


def _parse_naukri_detail(soup: BeautifulSoup, rec: dict):
    text = soup.get_text(" ", strip=True)

    h1 = soup.select_one("h1.jd-header-title, h1")
    if h1: rec["title"] = h1.get_text(strip=True)

    for sel in [".jd-header-comp-name a", ".company-name", "[class*='comp-name']"]:
        el = soup.select_one(sel)
        if el: rec["company"] = el.get_text(strip=True); break

    # Location
    for sel in [".loc", ".location", "[class*='loc']"]:
        el = soup.select_one(sel)
        if el: rec["location"] = el.get_text(" ", strip=True); break

    # Salary/Stipend
    for sel in [".salary", "[class*='salary']", "[class*='ctc']"]:
        el = soup.select_one(sel)
        if el: rec["stipend"] = el.get_text(strip=True); break

    # Skills
    skills = soup.select(".chipWrapper span, .key-skill span, [class*='skill'] span")
    if skills:
        rec["skills"] = ", ".join(s.get_text(strip=True) for s in skills[:10])

    # Mode and internship type
    rec["mode"]            = extract_mode(text)
    rec["internship_type"] = extract_internship_type(text)

    # Duration
    rec["duration"] = extract_duration(text[:800])

    # Stipend — CSS first, then extractor
    if rec["stipend"] == "Not disclosed":
        rec["stipend"] = extract_stipend(text[:600])

    # Eligibility/education block
    elig = _extract_elig_naukri(soup)
    rec["eligibility_raw"]   = elig or "Not mentioned"
    rec["cgpa_required"]     = parse_cgpa(elig)
    rec["branch_required"]   = parse_branches(elig)
    rec["gender"]            = parse_gender(elig, rec["title"])


def _extract_elig_naukri(soup: BeautifulSoup) -> str:
    # Naukri shows eligibility/education under "Education" or "Key Skills" sections
    for label in ["Education", "Eligibility", "Who can apply"]:
        for tag in soup.find_all(string=re.compile(rf"^{label}$", re.I)):
            p = tag.parent
            nxt = p.find_next_sibling()
            if nxt: return nxt.get_text(" ", strip=True)
    pt = soup.get_text(" ", strip=True)
    m = re.search(
        r"(?:Education|Eligibility|Key Skills)\s*[:\-]?\s*(.{10,400}?)(?:About|Company|Job Description|$)",
        pt, re.I | re.S
    )
    return m.group(1).strip() if m else ""


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 4 — AICTE
# ══════════════════════════════════════════════════════════════════════════════

# Public category pages on AICTE that don't require login.
# Each has static HTML cards with title, company, stipend, deadline etc.
AICTE_PUBLIC_PAGES = [
    ("TULIP (Urban Local Bodies)",    "https://internship.aicte-india.org/fetch_ubl1.php"),
    ("Rural Ministry (PRATIBHA)",     "https://internship.aicte-india.org/fetch_rural.php"),
    ("Cisco",                         "https://internship.aicte-india.org/cisco.php"),
    ("IBM / Microsoft / Shell",       "https://internship.aicte-india.org/internship_by_ibm.php"),
    ("Microsoft",                     "https://internship.aicte-india.org/microsoft.php"),
    ("Maharashtra Govt",              "https://internship.aicte-india.org/dashboard/state/maharashtra/internship-list.php"),
    ("Bharatiya Bhasha Samiti",       "https://internship.aicte-india.org/bharatiya_bhasha_samiti.php"),
    ("AICTE Research",                "https://internship.aicte-india.org/dashboard/aicte-research-internship/"),
    ("Corporate Internships",         "https://internship.aicte-india.org/corporate.php"),
    ("Ministry of Cooperation",       "https://internship.aicte-india.org/ibyministryofcoop.php"),
]


def scrape_aicte(driver, pages: int, keyword: str, fetch_details: bool,
                 delay: float) -> list[dict]:
    """
    Scrapes AICTE public category pages — no login required.
    Each category page has static HTML cards with full internship details.
    The 'pages' argument controls how many category pages to scrape
    (max = len(AICTE_PUBLIC_PAGES)).
    """
    print("\n  ── AICTE ───────────────────────────────────────────")
    BASE = "https://internship.aicte-india.org"
    records = []
    seen_urls = set()

    # Limit to requested number of category pages
    categories = AICTE_PUBLIC_PAGES[:max(pages, len(AICTE_PUBLIC_PAGES))]

    for idx, (cat_name, cat_url) in enumerate(categories, 1):
        print(f"  [AICTE {idx}/{len(categories)}] {cat_name:<35}", end=" ", flush=True)
        try:
            html = get_html(driver, cat_url,
                            wait_css="h3, h4, .card, [class*='intern']",
                            delay=delay + 0.5)
        except Exception as e:
            print(f"FAILED: {e}"); continue

        soup = BeautifulSoup(html, "lxml")
        new  = 0

        # AICTE cards structure (from fetch_ubl1.php):
        # <h3>TITLE</h3>
        # <h5>Company Name</h5>
        # <li>Full Time</li>  <li>date</li>  <li>location</li>  <li>X Months</li>
        # Stipend / Apply by / Openings in sub-items
        # <a href="internship-details.php?uid=...">Apply Now</a>

        # Find all Apply Now links — each = one internship card
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "internship-details.php" not in href and "internship-list.php" not in href:
                continue
            full_url = href if href.startswith("http") else BASE + "/" + href.lstrip("/")
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            rec = empty_record("AICTE")
            rec["apply_link"]      = full_url
            rec["mode"] = "On-site"  # default; AICTE is mostly on-site govt
            rec["internship_type"] = "Full Time"

            # Walk up the DOM to find the card container
            # Typically the card is wrapped in a <div> a few levels up
            card = a
            for _ in range(6):
                card = card.find_parent()
                if card is None:
                    break
                # Stop when we find the container that has an h3 (title)
                if card.find("h3") or card.find("h4"):
                    break

            if card:
                # Title
                h = card.find("h3") or card.find("h4")
                if h:
                    rec["title"] = h.get_text(strip=True)

                # Company (h5 after title)
                h5 = card.find("h5")
                if h5:
                    rec["company"] = h5.get_text(strip=True)

                # Pull all <li> text — AICTE puts type/date/location/duration there
                lis = [li.get_text(strip=True) for li in card.find_all("li") if li.get_text(strip=True)]

                # li[0] = internship type (Full Time / Virtual / Part Time)
                if len(lis) > 0 and lis[0]:
                    val = lis[0].strip()
                    # "Virtual" = Remote mode
                    if "virtual" in val.lower() or "online" in val.lower():
                        rec["mode"] = "Remote"
                        rec["internship_type"] = "Full Time"
                    else:
                        rec["internship_type"] = extract_internship_type(val) or val
                        rec["mode"] = extract_mode(val)
                # li[2] = location (state, city)
                if len(lis) > 2 and lis[2]:
                    rec["location"] = lis[2]
                # li[3] = duration
                if len(lis) > 3 and lis[3]:
                    rec["duration"] = lis[3]

                # Stipend, Apply by, Openings are in labelled sub-items
                full_text = card.get_text(" ", strip=True)

                # Stipend — use dedicated extractor on card text
                stipend_m = re.search(r"Stipend\s+(.{3,80}?)(?:Number|Apply|Start|$)", full_text, re.I)
                if stipend_m:
                    rec["stipend"] = extract_stipend(stipend_m.group(1)) or stipend_m.group(1).strip()
                else:
                    rec["stipend"] = extract_stipend(full_text)

                # Duration — li[3] already captured above; enrich with extractor
                if rec["duration"] == "Not mentioned":
                    rec["duration"] = extract_duration(full_text)

                m = re.search(r"Apply\s+by\s+([\d\-\/A-Za-z]+)", full_text, re.I)
                if m:
                    rec["deadline"] = m.group(1).strip()

                m = re.search(r"Number of Openings\s+(\d+)", full_text, re.I)
                if m:
                    rec["applicants"] = m.group(1)  # reusing applicants field for openings

                # Eligibility — AICTE often encodes branch in title itself
                # e.g. "INTERNS FOR OUHM (B.TECH CIVIL ENGINEERING)"
                title_elig = re.search(r"\(([^)]+)\)", rec["title"])
                elig = title_elig.group(1) if title_elig else ""

                rec["eligibility_raw"]   = elig or "Not mentioned"
                rec["cgpa_required"]     = parse_cgpa(elig)
                rec["branch_required"] = parse_branches(elig)
                rec["gender"]            = parse_gender(elig, rec["title"])

            records.append(rec)
            new += 1

        print(f"found {new}  (total AICTE: {len(records)})")
        time.sleep(delay)

    # ── Detail page fetch for AICTE ────────────────────────────────────────
    if fetch_details and records:
        print(f"\n  Fetching {len(records)} AICTE detail pages...")
        for i, rec in enumerate(records, 1):
            print(f"    [{i:>3}/{len(records)}] {rec['title'][:50]:<50}", end=" ", flush=True)
            try:
                html = get_html(driver, rec["apply_link"],
                                wait_css="h3, h4, table, .container",
                                delay=delay * 0.7)
                _parse_aicte_detail(BeautifulSoup(html, "lxml"), rec)
                print((
                    f"\n         Stipend  : {rec.get('stipend','Not disclosed')}\n"
                    f"         Duration : {rec.get('duration','Not mentioned')}\n"
                    f"         Mode     : {rec.get('mode','Not mentioned')}\n"
                    f"         Type     : {rec.get('internship_type','Not mentioned')}\n"
                    f"         Branch   : {rec.get('branch_required','Not mentioned')}\n"
                    f"         CGPA     : {rec.get('cgpa_required','Not mentioned')}\n"
                    f"         Gender   : {rec.get('gender','All')}\n"
                    f"         Link     : {rec.get('apply_link','')}\n"
                ))
            except Exception as e:
                print(f"ERR:{e}")

    return records


def _parse_aicte_detail(soup: BeautifulSoup, rec: dict):
    """
    Parse AICTE internship-details.php page.
    These pages have a table layout with labelled rows.
    """
    text = soup.get_text(" ", strip=True)

    # Title
    for sel in ["h3", "h4", "h2", "h1"]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 4:
            rec["title"] = el.get_text(strip=True); break

    # AICTE detail pages use a table with label: value rows
    for row in soup.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label = cells[0].lower().strip().rstrip(":")
        value = cells[1].strip()
        if not value:
            continue
        if "stipend" in label or "salary" in label:
            rec["stipend"] = value
        elif "duration" in label:
            rec["duration"] = value
        elif "location" in label or "city" in label or "state" in label:
            rec["location"] = value
        elif "apply" in label or "deadline" in label or "last date" in label:
            rec["deadline"] = value
        elif "opening" in label or "vacancy" in label or "seats" in label:
            rec["applicants"] = value
        elif "start" in label:
            rec["posted_on"] = value
        elif "type" in label:
            rec["internship_type"] = extract_internship_type(value) or value
            rec["mode"]            = extract_mode(value)
        elif "eligib" in label or "qualification" in label or "who can" in label:
            elig = value
            rec["eligibility_raw"]   = elig
            rec["cgpa_required"]     = parse_cgpa(elig)
            rec["branch_required"]   = parse_branches(elig)
            rec["gender"]            = parse_gender(elig, rec["title"])

    # If eligibility not found in table, check title brackets as fallback
    if rec["eligibility_raw"] == "Not mentioned":
        title_elig = re.search(r"\(([^)]+)\)", rec["title"])
        if title_elig:
            elig = title_elig.group(1)
            rec["eligibility_raw"]   = elig
            rec["cgpa_required"]     = parse_cgpa(elig)
            rec["branch_required"]   = parse_branches(elig)
            rec["gender"]            = parse_gender(elig, rec["title"])



# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 5 — COMPANY CAREER PAGES
#  Strategy:
#   • Heavy JS SPA portals (Google, Microsoft, Amazon, Apple, Meta etc.) load
#     jobs via internal APIs — scraping them is fragile and breaks constantly.
#     Instead we store their KNOWN, STABLE direct internship program URLs as
#     curated records. These are real public links your backend can serve.
#   • Semi-static pages (ISRO, RBI, NITI Aayog, Bosch, Siemens, L&T) are
#     scraped with Selenium since they render HTML server-side.
# ══════════════════════════════════════════════════════════════════════════════

# ── Curated company internship program entries ─────────────────────────────
# Each entry is a dict that becomes one record in the output.
# apply_link points to the OFFICIAL internship page for that program.
# gender = "Girls Only" for female-specific programs.
CURATED_COMPANY_PROGRAMS = [
    # ── Big Tech ──────────────────────────────────────────────────────────
    {
        "company": "Google",
        "title": "Software Engineering Internship (SWE Intern)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Multiple Locations / Remote",
        "branch_required": "Computer Science, Information Technology",
        "gender": "All",
        "apply_link": "https://www.google.com/about/careers/applications/jobs/results?q=intern&employment_type=INTERN",
        "notes": "Search for active openings on Google Careers",
    },
    {
        "company": "Google",
        "title": "STEP Internship (Student Training in Engineering Program)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Multiple Locations",
        "branch_required": "Computer Science, Information Technology",
        "gender": "All",
        "apply_link": "https://buildyourfuture.withgoogle.com/programs/step",
        "notes": "For 1st and 2nd year undergrad CS students",
    },
    {
        "company": "Microsoft",
        "title": "University Internship (Software Engineering)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Multiple Locations / India",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "All",
        "apply_link": "https://careers.microsoft.com/v2/global/en/universityinternship",
        "notes": "Pre-final year STEM students eligible",
    },
    {
        "company": "Microsoft",
        "title": "Explore Microsoft Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "India / USA",
        "branch_required": "Computer Science, Information Technology",
        "gender": "All",
        "apply_link": "https://careers.microsoft.com/v2/global/en/exploremicrosoft",
        "notes": "For 1st and 2nd year students only",
    },
    {
        "company": "Apple",
        "title": "Apple Internship Program",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Multiple Locations",
        "branch_required": "Computer Science, Electronics, Electrical, Mechanical",
        "gender": "All",
        "apply_link": "https://www.apple.com/careers/us/students.html",
        "notes": "Search 'intern' on Apple Jobs for active roles",
    },
    {
        "company": "Meta (Facebook)",
        "title": "Software Engineer Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Multiple Locations",
        "branch_required": "Computer Science, Information Technology",
        "gender": "All",
        "apply_link": "https://www.metacareers.com/jobs?q=intern&teams[0]=Internship%20-%20Engineering%2C%20Tech%20%26%20Design",
        "notes": "Filter by Internship team on Meta Careers",
    },
    {
        "company": "Amazon",
        "title": "Software Development Engineer Internship (SDE Intern)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Multiple Locations / India",
        "branch_required": "Computer Science, Information Technology",
        "gender": "All",
        "apply_link": "https://www.amazon.jobs/en/job_categories/student-programs",
        "notes": "Check Student Programs section on Amazon Jobs",
    },
    {
        "company": "Adobe",
        "title": "Adobe Research Internship / Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Noida / Bengaluru / USA",
        "branch_required": "Computer Science, Information Technology, Data Science",
        "gender": "All",
        "apply_link": "https://careers.adobe.com/us/en/search-results?keywords=intern",
        "notes": "Search intern on Adobe Careers",
    },
    {
        "company": "Adobe",
        "title": "SheCodes by Adobe (Women in Tech)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "India",
        "branch_required": "Computer Science, Information Technology",
        "gender": "Girls Only",
        "apply_link": "https://careers.adobe.com/us/en/search-results?keywords=shecodes",
        "notes": "Female-specific program. Check Adobe Careers for active cycle.",
    },
    # ── Finance ───────────────────────────────────────────────────────────
    {
        "company": "Goldman Sachs",
        "title": "Summer Analyst Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Mumbai / Global",
        "branch_required": "Computer Science, Finance, Mathematics, Economics",
        "gender": "All",
        "apply_link": "https://www.goldmansachs.com/careers/students/programs/",
        "notes": "Look under Asia Pacific / India programs",
    },
    {
        "company": "Goldman Sachs",
        "title": "Goldman Sachs Women's Possibilities Summit",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "India",
        "branch_required": "All",
        "gender": "Girls Only",
        "apply_link": "https://www.goldmansachs.com/careers/students/programs/india/",
        "notes": "Female-specific program. Check India student programs page.",
    },
    {
        "company": "Morgan Stanley",
        "title": "Summer Analyst Program",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Bengaluru",
        "branch_required": "Computer Science, Finance, Mathematics, Economics",
        "gender": "All",
        "apply_link": "https://www.morganstanley.com/people-opportunities/students-graduates",
        "notes": "Check Asia-Pacific / India under Students & Graduates",
    },
    {
        "company": "J.P. Morgan Chase",
        "title": "Summer Analyst / Code for Good Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Bengaluru / Hyderabad",
        "branch_required": "Computer Science, Finance, Mathematics, Economics",
        "gender": "All",
        "apply_link": "https://careers.jpmorgan.com/global/en/students/programs",
        "notes": "Code for Good is a 24-hour hackathon-style internship",
    },
    # ── Consulting ────────────────────────────────────────────────────────
    {
        "company": "McKinsey & Company",
        "title": "McKinsey Young Leaders Programme / Business Analyst Intern",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "India (Multiple cities)",
        "branch_required": "All",
        "gender": "All",
        "apply_link": "https://www.mckinsey.com/careers/students",
        "notes": "Check Students section for current India openings",
    },
    {
        "company": "BCG (Boston Consulting Group)",
        "title": "BCG Platinion / Summer Consulting Intern",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "India",
        "branch_required": "All",
        "gender": "All",
        "apply_link": "https://careers.bcg.com/students",
        "notes": "Check Students section for India internship openings",
    },
    # ── Semiconductor / Hardware ──────────────────────────────────────────
    {
        "company": "NXP Semiconductors",
        "title": "Women in Technology (WIT) Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Noida / Bengaluru / Hyderabad",
        "branch_required": "Electronics, Electrical, Computer Science",
        "gender": "Girls Only",
        "apply_link": "https://www.nxp.com/company/about-nxp/careers/students-and-recent-graduates:STUDENTS-GRADUATES",
        "notes": "Female-specific program. Check NXP careers for active cycle.",
    },
    # ── Finance / India ───────────────────────────────────────────────────
    {
        "company": "D.E. Shaw",
        "title": "Ascend Internship (Women in STEM)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Hyderabad",
        "branch_required": "Computer Science, Mathematics, Statistics",
        "gender": "Girls Only",
        "apply_link": "https://www.deshawindia.com/forms/NFS.aspx",
        "notes": "Female-specific program by D.E. Shaw India",
    },
    # ── FMCG ─────────────────────────────────────────────────────────────
    {
        "company": "Nestlé India",
        "title": "Nesternship (Summer Internship Program)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Multiple Locations, India",
        "branch_required": "MBA, Management, Food Technology, Chemical",
        "gender": "All",
        "apply_link": "https://www.nestle.in/jobs/nesternship",
        "notes": "Annual summer internship program for MBA/PG students",
    },
    # ── Core Engineering / India MNCs ─────────────────────────────────────
    {
        "company": "Bosch India",
        "title": "Bosch Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Coimbatore / Chennai",
        "branch_required": "Electronics, Mechanical, Computer Science, Electrical",
        "gender": "All",
        "apply_link": "https://www.bosch.in/careers/your-entry-into-bosch/internships/",
        "notes": "Check Bosch India Careers for active openings",
    },
    {
        "company": "Siemens India",
        "title": "Siemens Student Internship Program",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Pune / Bengaluru / Gurgaon",
        "branch_required": "Electronics, Electrical, Mechanical, Computer Science",
        "gender": "All",
        "apply_link": "https://jobs.siemens.com/careers?query=intern&domain=siemens.com",
        "notes": "Search intern on Siemens global jobs portal filtered to India",
    },
    {
        "company": "Larsen & Toubro (L&T)",
        "title": "L&T Summer Internship Program",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Pan India",
        "branch_required": "Civil, Mechanical, Electrical, Electronics, Computer Science",
        "gender": "All",
        "apply_link": "https://www.larsentoubro.com/corporate/career/campus-recruitment/",
        "notes": "Check Campus Recruitment section on L&T website",
    },
    # ── Government / Research India ───────────────────────────────────────
    {
        "company": "ISRO",
        "title": "ISRO Student Internship / Project Trainee Scheme",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Thiruvananthapuram / Ahmedabad (various centres)",
        "branch_required": "Electronics, Computer Science, Mechanical, Electrical",
        "gender": "All",
        "apply_link": "https://www.isro.gov.in/Internship.html",
        "notes": "Apply directly to individual ISRO centres. Min 60% / 6.32 CGPA required.",
        "cgpa_required": "6.32",
    },
    {
        "company": "DRDO",
        "title": "DRDO Apprentice / Internship Program",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Pan India (various DRDO labs)",
        "branch_required": "Electronics, Computer Science, Mechanical, Electrical, Chemical",
        "gender": "All",
        "apply_link": "https://www.drdo.gov.in/internship-scheme",
        "notes": "Apply to individual DRDO labs. Requires college NOC.",
    },
    {
        "company": "NITI Aayog",
        "title": "NITI Aayog Young Professional / Internship Programme",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "New Delhi",
        "branch_required": "All",
        "gender": "All",
        "apply_link": "https://www.niti.gov.in/internship",
        "notes": "2-6 months. Open to UG/PG/PhD students from recognized institutions.",
    },
    {
        "company": "Reserve Bank of India (RBI)",
        "title": "RBI Summer Internship Programme",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Regional offices",
        "branch_required": "Finance, Economics, Mathematics, Statistics, Management",
        "gender": "All",
        "apply_link": "https://opportunities.rbi.org.in/Scripts/Internships.aspx",
        "notes": "Paid internship. Open to students of Economics/Finance/Statistics.",
    },

    # ══════════════════════════════════════════════════════════════
    #  FASHION & LIFESTYLE
    # ══════════════════════════════════════════════════════════════
    {
        "company": "Sabyasachi Mukherjee",
        "title": "Design / Visual Merchandising Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Kolkata / Mumbai",
        "branch_required": "Fashion Design, Textile Design, Fine Arts",
        "gender": "All",
        "apply_link": "https://www.sabyasachi.com/careers",
        "notes": "Check careers page or email careers@sabyasachi.com. Roles in design, embroidery, and retail.",
    },
    {
        "company": "Manish Malhotra",
        "title": "Fashion Design / Styling Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Delhi",
        "branch_required": "Fashion Design, Textile Design, Mass Communication",
        "gender": "All",
        "apply_link": "https://www.manishmalhotra.in/pages/careers",
        "notes": "Also listed periodically on Internshala and LinkedIn. Check brand website for active roles.",
    },
    {
        "company": "Anita Dongre",
        "title": "Design / Production / Retail Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai",
        "branch_required": "Fashion Design, Textile Design, Management",
        "gender": "All",
        "apply_link": "https://www.anitadongre.com/pages/careers",
        "notes": "House of Anita Dongre. Check careers page and LinkedIn for open internship roles.",
    },
    {
        "company": "Fabindia",
        "title": "Retail / Design / Buying & Merchandising Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "New Delhi / Pan India stores",
        "branch_required": "Fashion Design, Textile, Management, MBA",
        "gender": "All",
        "apply_link": "https://www.fabindia.com/careers",
        "notes": "Internships in design, retail ops, and B&M. Check Fabindia careers and Naukri.",
    },
    {
        "company": "Reliance Retail (Fashion & Lifestyle)",
        "title": "Management Trainee / Buying & Merchandising Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Pan India",
        "branch_required": "MBA, Fashion Design, Management, Retail",
        "gender": "All",
        "apply_link": "https://www.relianceretail.com/career.html",
        "notes": "Covers brands: Trends, Azorte, Centro. Also posted on Naukri and Internshala.",
    },
    {
        "company": "Aditya Birla Fashion and Retail (ABFRL)",
        "title": "Management Intern / Design / Merchandising Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Bengaluru",
        "branch_required": "MBA, Fashion Design, Textile, Management",
        "gender": "All",
        "apply_link": "https://careers.abfrl.com/",
        "notes": "Covers Manyavar, Pantaloons, Van Heusen, Louis Philippe. Active roles on ABFRL careers portal.",
    },
    {
        "company": "Aditya Birla Fashion and Retail (ABFRL)",
        "title": "ABFRL Women Leadership Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Bengaluru",
        "branch_required": "MBA, Management, Fashion Design",
        "gender": "Girls Only",
        "apply_link": "https://careers.abfrl.com/",
        "notes": "Female-focused internship tracks under ABFRL's diversity initiatives. Verify on careers portal.",
    },

    # ══════════════════════════════════════════════════════════════
    #  MEDIA & JOURNALISM
    # ══════════════════════════════════════════════════════════════
    {
        "company": "The Times Group (Bennett, Coleman & Co. Ltd.)",
        "title": "Editorial / Digital Media / Marketing Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Delhi / Bengaluru",
        "branch_required": "Mass Communication, Journalism, Marketing, MBA",
        "gender": "All",
        "apply_link": "https://careers.timesgroup.com/",
        "notes": "Covers TOI, ET, Navbharat Times, Mirchi. Check Times Group careers and Internshala.",
    },
    {
        "company": "NDTV (New Delhi Television)",
        "title": "Journalism / Digital Content / Video Production Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "New Delhi / Mumbai",
        "branch_required": "Mass Communication, Journalism, Film Production",
        "gender": "All",
        "apply_link": "https://www.ndtv.com/careers",
        "notes": "Internship openings on NDTV careers. Also search 'NDTV intern' on LinkedIn.",
    },
    {
        "company": "India Today Group",
        "title": "Editorial / Digital / Marketing Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "New Delhi / Mumbai",
        "branch_required": "Mass Communication, Journalism, Marketing",
        "gender": "All",
        "apply_link": "https://www.indiatodaygroup.com/careers.html",
        "notes": "Covers India Today, Aaj Tak, Business Today. Check careers page and LinkedIn.",
    },
    {
        "company": "The Hindu Group",
        "title": "Editorial / Journalism / Research Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Chennai / Delhi / Bengaluru",
        "branch_required": "Mass Communication, Journalism, Economics",
        "gender": "All",
        "apply_link": "https://careers.thehindu.com/",
        "notes": "Covers The Hindu, Frontline, Sportstar. Check The Hindu careers portal.",
    },
    {
        "company": "Network18",
        "title": "Journalism / Content / Production Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / New Delhi",
        "branch_required": "Mass Communication, Journalism, Film Production",
        "gender": "All",
        "apply_link": "https://www.network18online.com/careers/",
        "notes": "Covers CNN-News18, CNBC-TV18, News18 India. Also on Internshala.",
    },
    {
        "company": "The Indian Express Group",
        "title": "Journalism / Data / Digital Media Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / New Delhi",
        "branch_required": "Mass Communication, Journalism, Computer Science",
        "gender": "All",
        "apply_link": "https://indianexpress.com/about/career-with-us/",
        "notes": "Covers Indian Express, Financial Express. Also listed on Internshala.",
    },

    # ══════════════════════════════════════════════════════════════
    #  FILM / ENTERTAINMENT
    # ══════════════════════════════════════════════════════════════
    {
        "company": "Yash Raj Films (YRF)",
        "title": "Film Production / Marketing / Music Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai",
        "branch_required": "Mass Communication, Film Production, Marketing, MBA",
        "gender": "All",
        "apply_link": "https://www.yashrajfilms.com/careers",
        "notes": "Internships across production, marketing, music. Check YRF careers and LinkedIn.",
    },
    {
        "company": "Dharma Productions",
        "title": "Film / Digital Content / Production Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai",
        "branch_required": "Mass Communication, Film Production, Digital Media",
        "gender": "All",
        "apply_link": "https://www.dharmaproductions.com",
        "notes": "Check Dharma Productions social media and LinkedIn for internship openings.",
    },
    {
        "company": "Red Chillies Entertainment",
        "title": "VFX / Film Production / Post-Production Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai",
        "branch_required": "Animation, VFX, Film Production, Computer Science",
        "gender": "All",
        "apply_link": "https://www.redchillies.com/careers",
        "notes": "SRK's production house. Strong VFX division. Check LinkedIn for open roles.",
    },
    {
        "company": "Excel Entertainment",
        "title": "Film / Content / Production Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai",
        "branch_required": "Mass Communication, Film Production, Digital Media",
        "gender": "All",
        "apply_link": "https://www.excelentertainment.in",
        "notes": "Farhan Akhtar & Ritesh Sidhwani's banner. Check LinkedIn for internship posts.",
    },
    {
        "company": "Hombale Films",
        "title": "Film Production / Content Strategy Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Mumbai",
        "branch_required": "Mass Communication, Film Production, Marketing",
        "gender": "All",
        "apply_link": "https://www.hombalefilms.com",
        "notes": "KGF, Salaar producer. Check LinkedIn and their official handles for internship openings.",
    },
    {
        "company": "Reliance Entertainment",
        "title": "Content / Production / Distribution Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai",
        "branch_required": "Mass Communication, Film Production, MBA",
        "gender": "All",
        "apply_link": "https://www.relianceentertainment.net/careers",
        "notes": "Check Reliance Entertainment careers page and LinkedIn for internship openings.",
    },

    # ══════════════════════════════════════════════════════════════
    #  IT SERVICES
    # ══════════════════════════════════════════════════════════════
    {
        "company": "Tata Consultancy Services (TCS)",
        "title": "TCS BPS / IT Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Pan India",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "All",
        "apply_link": "https://www.tcs.com/careers/india/students",
        "notes": "Check TCS NextStep portal. Also appears on Internshala and AICTE.",
    },
    {
        "company": "Tata Consultancy Services (TCS)",
        "title": "TCS Ingenium – Women in Tech Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Pan India",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "Girls Only",
        "apply_link": "https://www.tcs.com/careers/india/students",
        "notes": "Female-specific tech internship initiative by TCS. Verify active cycle on TCS NextStep.",
    },
    {
        "company": "Infosys",
        "title": "Infosys Internship / InStep Program",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Hyderabad / Pune / Chennai",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "All",
        "apply_link": "https://www.infosys.com/careers/student-opportunities.html",
        "notes": "InStep is the global internship program. Also check Infosys campus connect.",
    },
    {
        "company": "Infosys",
        "title": "Infosys Springboard – Women in Tech Program",
        "internship_type": "Full Time",
        "mode": "Remote",
        "location": "India (Remote)",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "Girls Only",
        "apply_link": "https://infyspringboard.onwingspan.com/",
        "notes": "Female-focused tech learning and internship path. Free upskilling + internship opportunity.",
    },
    {
        "company": "HCLTech",
        "title": "TechBee / Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Noida / Chennai / Bengaluru / Hyderabad",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "All",
        "apply_link": "https://www.hcltech.com/careers/students",
        "notes": "TechBee is HCL's early career program. Check HCLTech student careers page.",
    },
    {
        "company": "Wipro",
        "title": "Wipro Turbo Internship / Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Hyderabad / Pune",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "All",
        "apply_link": "https://careers.wipro.com/careers-home/students",
        "notes": "Wipro Turbo is an elite pre-placement internship. Check Wipro careers for active cycle.",
    },
    {
        "company": "Wipro",
        "title": "Wipro Unnati – Women in Technology",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Pan India",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "Girls Only",
        "apply_link": "https://careers.wipro.com/careers-home/students",
        "notes": "Female-focused program. Check Wipro careers page for active openings.",
    },
    {
        "company": "LTIMindtree",
        "title": "Campus to Corporate Internship / Engineer Trainee",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Bengaluru / Pune / Hyderabad",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "All",
        "apply_link": "https://www.ltimindtree.com/careers/campus/",
        "notes": "LTIMindtree Campus Hire. Search 'intern' on LTIMindtree careers portal.",
    },

    # ══════════════════════════════════════════════════════════════
    #  GLOBAL CAPTIVES / GCCs
    # ══════════════════════════════════════════════════════════════
    {
        "company": "Global Captives (GCCs – General)",
        "title": "GCC Engineering / Data / Finance Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Hyderabad / Pune / Chennai",
        "branch_required": "Computer Science, Information Technology, Electronics, Finance",
        "gender": "All",
        "apply_link": "https://www.nasscom.in/gcc",
        "notes": "GCCs include JP Morgan, Citi, Wells Fargo, Philips, Shell, Honeywell India centres. Search each company's India careers page directly.",
    },

    # ══════════════════════════════════════════════════════════════
    #  AI STARTUPS (INDIA)
    # ══════════════════════════════════════════════════════════════
    {
        "company": "Sarvam AI",
        "title": "Research / ML Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru",
        "branch_required": "Computer Science, Mathematics, Data Science",
        "gender": "All",
        "apply_link": "https://www.sarvam.ai/careers",
        "notes": "Indian foundational AI startup (speech, language models). Check Sarvam AI careers and LinkedIn.",
    },
    {
        "company": "Krutrim (Ola AI)",
        "title": "AI / ML / Software Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru",
        "branch_required": "Computer Science, Mathematics, Data Science",
        "gender": "All",
        "apply_link": "https://www.krutrim.com/careers",
        "notes": "Bhavish Aggarwal's AI venture. Check Krutrim careers and LinkedIn for intern openings.",
    },

    # ══════════════════════════════════════════════════════════════
    #  PRODUCT / ENGINEERING COMPANIES
    # ══════════════════════════════════════════════════════════════
    {
        "company": "Tata Elxsi",
        "title": "Design / Embedded / Software Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Bengaluru / Thiruvananthapuram / Pune",
        "branch_required": "Computer Science, Electronics, Electrical, Mechanical",
        "gender": "All",
        "apply_link": "https://www.tataelxsi.com/careers/campus-hiring",
        "notes": "Strong in automotive, media, healthcare tech. Check campus hiring portal.",
    },
    {
        "company": "Persistent Systems",
        "title": "Software Engineering / Cloud / AI Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Pune / Nagpur / Bengaluru / Hyderabad",
        "branch_required": "Computer Science, Information Technology, Electronics",
        "gender": "All",
        "apply_link": "https://careers.persistent.com/students",
        "notes": "Check Persistent careers student page and Internshala for active roles.",
    },
    {
        "company": "Fractal Analytics",
        "title": "Data Science / AI / Analytics Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai / Bengaluru / Hyderabad",
        "branch_required": "Computer Science, Mathematics, Statistics, Data Science",
        "gender": "All",
        "apply_link": "https://fractal.ai/careers/",
        "notes": "AI-first analytics company. Check Fractal careers and LinkedIn for intern openings.",
    },
    {
        "company": "Affle",
        "title": "Software / Data / Product Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Gurugram / Bengaluru",
        "branch_required": "Computer Science, Information Technology, Data Science",
        "gender": "All",
        "apply_link": "https://www.affle.com/careers",
        "notes": "Consumer intelligence tech company. Check Affle careers and LinkedIn.",
    },

    # ══════════════════════════════════════════════════════════════
    #  QUANT / HFT FIRMS
    # ══════════════════════════════════════════════════════════════
    {
        "company": "D. E. Shaw India",
        "title": "Software Development / Quantitative Research Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Hyderabad",
        "branch_required": "Computer Science, Mathematics, Statistics, Physics",
        "gender": "All",
        "apply_link": "https://www.deshawindia.com/careers",
        "notes": "Highly competitive. Check D.E. Shaw India careers for SDE and Quant intern roles.",
    },
    {
        "company": "D. E. Shaw India",
        "title": "Ascend Internship (Women in STEM)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Hyderabad",
        "branch_required": "Computer Science, Mathematics, Statistics",
        "gender": "Girls Only",
        "apply_link": "https://www.deshawindia.com/forms/NFS.aspx",
        "notes": "Female-specific program by D.E. Shaw India. Prestigious and competitive.",
    },
    {
        "company": "Tower Research Capital",
        "title": "Software Engineer / Quantitative Research Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Gurugram",
        "branch_required": "Computer Science, Mathematics, Statistics, Physics",
        "gender": "All",
        "apply_link": "https://www.tower-research.com/open-positions",
        "notes": "Global HFT firm. India office in Gurugram. Very competitive. Check Tower open positions.",
    },
    {
        "company": "AlphaGrep Securities",
        "title": "Quant / Software Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Mumbai",
        "branch_required": "Computer Science, Mathematics, Statistics, Physics",
        "gender": "All",
        "apply_link": "https://www.alphagrep.com/careers",
        "notes": "India-based HFT firm. Check AlphaGrep careers and LinkedIn for intern openings.",
    },
    {
        "company": "Graviton Research Capital",
        "title": "Quantitative / Software Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Gurugram",
        "branch_required": "Computer Science, Mathematics, Physics, Statistics",
        "gender": "All",
        "apply_link": "https://gravitonrc.com/careers",
        "notes": "Indian quant trading firm. Check Graviton careers and LinkedIn.",
    },
    {
        "company": "Quadeye",
        "title": "Software / Quantitative Trading Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Gurugram",
        "branch_required": "Computer Science, Mathematics, Statistics, Physics",
        "gender": "All",
        "apply_link": "https://quadeye.com/careers/",
        "notes": "India-based HFT. Check Quadeye careers and LinkedIn. Competitive selection.",
    },
    {
        "company": "WorldQuant",
        "title": "Quantitative Researcher / Consultant Internship",
        "internship_type": "Full Time",
        "mode": "Remote",
        "location": "Remote / India",
        "branch_required": "Computer Science, Mathematics, Statistics, Physics, Finance",
        "gender": "All",
        "apply_link": "https://www.worldquant.com/career-listing/",
        "notes": "WorldQuant Virtual Research Program (WQVR) is a remote quant research internship accessible globally.",
    },
    {
        "company": "WorldQuant",
        "title": "WorldQuant Virtual Research Program – Women Edition",
        "internship_type": "Full Time",
        "mode": "Remote",
        "location": "Remote / India",
        "branch_required": "Mathematics, Statistics, Computer Science, Finance",
        "gender": "Girls Only",
        "apply_link": "https://www.worldquant.com/career-listing/",
        "notes": "Female-focused quant research program. Verify active cycle on WorldQuant careers.",
    },
    {
        "company": "Jane Street",
        "title": "Software Engineering / Trading Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Singapore / Hong Kong / London / New York (no India office)",
        "branch_required": "Computer Science, Mathematics, Statistics, Physics",
        "gender": "All",
        "apply_link": "https://www.janestreet.com/join-jane-street/internships/",
        "notes": "No India office. Indian students apply via Singapore/global. Extremely competitive.",
    },
    {
        "company": "Jane Street",
        "title": "Jane Street INSIGHT (Women & Non-Binary in Finance/Tech)",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "New York / London / Hong Kong",
        "branch_required": "Computer Science, Mathematics, Finance, Statistics",
        "gender": "Girls Only",
        "apply_link": "https://www.janestreet.com/join-jane-street/programs-and-events/insight/",
        "notes": "Female/non-binary-focused program. No India office — travel to NY/London required.",
    },
    {
        "company": "Citadel Securities",
        "title": "Quant / Software Engineering Internship",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "Singapore / USA / Europe (no India office)",
        "branch_required": "Computer Science, Mathematics, Statistics, Physics",
        "gender": "All",
        "apply_link": "https://www.citadelsecurities.com/careers/students-and-graduates/",
        "notes": "No India office. Indian students apply via Singapore or USA. Very competitive.",
    },
    {
        "company": "Citadel Securities",
        "title": "Citadel / Citadel Securities Women in Finance & Technology Scholarships",
        "internship_type": "Full Time",
        "mode": "On-site",
        "location": "USA / Europe / Singapore",
        "branch_required": "Computer Science, Mathematics, Finance, Statistics",
        "gender": "Girls Only",
        "apply_link": "https://www.citadel.com/careers/students-recent-graduates/",
        "notes": "Female-focused scholarship + internship pathway. Check Citadel student programs.",
    },
]


def scrape_companies(driver, pages: int, keyword: str, fetch_details: bool,
                     delay: float) -> list[dict]:
    """
    Returns curated company internship program records + attempts to scrape
    live openings from semi-static Indian company career pages.
    The keyword filter is applied to title, company, and notes fields.
    """
    print("\n  ── Company Career Pages ────────────────────────────")

    records = []

    # ── Part A: Curated stable program entries ─────────────────────────────
    kw = keyword.lower() if keyword else ""
    for prog in CURATED_COMPANY_PROGRAMS:
        if kw:
            searchable = (prog.get("title","") + " " + prog.get("company","") +
                          " " + prog.get("notes","") + " " +
                          prog.get("branch_required","")).lower()
            if kw not in searchable:
                continue
        rec = empty_record("Company Careers")
        rec.update({
            "title":             prog.get("title", "N/A"),
            "company":          prog.get("company", "N/A"),
            "location":         prog.get("location", "N/A"),
            "mode":             prog.get("mode", "Not mentioned"),
        "internship_type":  prog.get("internship_type", "Full Time"),
        "duration":         prog.get("duration", "Not mentioned"),
            "branch_required":   prog.get("branch_required", "Not mentioned"),
            "gender":           prog.get("gender", "All"),
            "apply_link":       prog.get("apply_link", ""),
            "eligibility_raw":  prog.get("notes", "Not mentioned"),
            "cgpa_required":    prog.get("cgpa_required", "Not mentioned"),
            "stipend":          prog.get("stipend", "Not disclosed"),
            "duration":         prog.get("duration", "N/A"),
        })
        records.append(rec)

    print(f"  Loaded {len(records)} curated company program entries")

    # ── Part B: Priority-based live scrape of company career pages ────────────
    #
    #  Companies are ranked by "fame" (hiring volume + brand recognition) into
    #  three live-scrape priority tiers:
    #
    #  PRIORITY 1 — scraped every run (high-volume, most competitive)
    #  PRIORITY 2 — scraped every other run (mid-tier, moderate volume)
    #  PRIORITY 3 — scraped once per day / infrequently (niche / low-volume)
    #
    #  Each entry has:
    #    company     : display name
    #    url         : careers / internships page to scrape
    #    title_sel   : CSS selector to wait for before parsing
    #    priority    : 1 / 2 / 3  (controls refresh frequency)
    #    fame_score  : 1–10 scale (used for logging / sorting output)
    #
    #  How priority is decided:
    #    10  — global brand, thousands of applicants/cycle (Google, TCS, Infosys)
    #    7-9 — major Indian brand, high applicant volume
    #    4-6 — known brand, moderate applicant traffic
    #    1-3 — niche / boutique / early-stage, low applicant volume
    #
    #  Priority assignment:
    #    fame_score 8-10  → priority 1  (refresh every scrape cycle)
    #    fame_score  5-7  → priority 2  (refresh every 2nd cycle)
    #    fame_score  1-4  → priority 3  (refresh every 4th cycle)
    #
    COMPANY_LIVE_TARGETS = [
        # ── IT SERVICES (very high volume — Priority 1) ───────────────────
        {
            "company":    "Tata Consultancy Services (TCS)",
            "url":        "https://www.tcs.com/careers/india/students",
            "title_sel":  "h1, h2, .section-title",
            "priority":   1,
            "fame_score": 10,
        },
        {
            "company":    "Infosys",
            "url":        "https://www.infosys.com/careers/student-opportunities.html",
            "title_sel":  "h1, h2",
            "priority":   1,
            "fame_score": 10,
        },
        {
            "company":    "Wipro",
            "url":        "https://careers.wipro.com/careers-home/students",
            "title_sel":  "h1, h2",
            "priority":   1,
            "fame_score": 9,
        },
        {
            "company":    "HCLTech",
            "url":        "https://www.hcltech.com/careers/students",
            "title_sel":  "h1, h2",
            "priority":   1,
            "fame_score": 9,
        },
        {
            "company":    "LTIMindtree",
            "url":        "https://www.ltimindtree.com/careers/campus/",
            "title_sel":  "h1, h2, h3",
            "priority":   1,
            "fame_score": 8,
        },
        # ── PRODUCT / ENGINEERING (Priority 1) ───────────────────────────
        {
            "company":    "Tata Elxsi",
            "url":        "https://www.tataelxsi.com/careers/campus-hiring",
            "title_sel":  "h1, h2",
            "priority":   1,
            "fame_score": 8,
        },
        {
            "company":    "Persistent Systems",
            "url":        "https://careers.persistent.com/students",
            "title_sel":  "h1, h2",
            "priority":   1,
            "fame_score": 7,
        },
        # ── QUANT / HFT — high prestige, lower volume (Priority 1) ───────
        {
            "company":    "D. E. Shaw India",
            "url":        "https://www.deshawindia.com/careers",
            "title_sel":  "h1, h2, .job-title",
            "priority":   1,
            "fame_score": 9,
        },
        {
            "company":    "Tower Research Capital",
            "url":        "https://www.tower-research.com/open-positions",
            "title_sel":  "h1, h2, .position",
            "priority":   1,
            "fame_score": 8,
        },
        {
            "company":    "WorldQuant",
            "url":        "https://www.worldquant.com/career-listing/",
            "title_sel":  "h1, h2, .job-listing",
            "priority":   1,
            "fame_score": 8,
        },
        # ── AI STARTUPS (Priority 1 — fast-changing openings) ─────────────
        {
            "company":    "Sarvam AI",
            "url":        "https://www.sarvam.ai/careers",
            "title_sel":  "h1, h2",
            "priority":   1,
            "fame_score": 7,
        },
        {
            "company":    "Krutrim (Ola AI)",
            "url":        "https://www.krutrim.com/careers",
            "title_sel":  "h1, h2",
            "priority":   1,
            "fame_score": 7,
        },
        # ── MEDIA (Priority 2) ────────────────────────────────────────────
        {
            "company":    "The Times Group",
            "url":        "https://careers.timesgroup.com/",
            "title_sel":  "h1, h2, h3",
            "priority":   2,
            "fame_score": 7,
        },
        {
            "company":    "NDTV",
            "url":        "https://www.ndtv.com/careers",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 6,
        },
        {
            "company":    "India Today Group",
            "url":        "https://www.indiatodaygroup.com/careers.html",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 6,
        },
        {
            "company":    "The Hindu Group",
            "url":        "https://careers.thehindu.com/",
            "title_sel":  "h1, h2, h3",
            "priority":   2,
            "fame_score": 6,
        },
        {
            "company":    "Network18",
            "url":        "https://www.network18online.com/careers/",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 6,
        },
        {
            "company":    "The Indian Express Group",
            "url":        "https://indianexpress.com/about/career-with-us/",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 5,
        },
        # ── FASHION (Priority 2) ─────────────────────────────────────────
        {
            "company":    "Reliance Retail (Fashion & Lifestyle)",
            "url":        "https://www.relianceretail.com/career.html",
            "title_sel":  "h1, h2, h3",
            "priority":   2,
            "fame_score": 7,
        },
        {
            "company":    "Aditya Birla Fashion and Retail (ABFRL)",
            "url":        "https://careers.abfrl.com/",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 7,
        },
        {
            "company":    "Fabindia",
            "url":        "https://www.fabindia.com/careers",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 6,
        },
        # ── ANALYTICS / DATA (Priority 2) ────────────────────────────────
        {
            "company":    "Fractal Analytics",
            "url":        "https://fractal.ai/careers/",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 6,
        },
        {
            "company":    "Affle",
            "url":        "https://www.affle.com/careers",
            "title_sel":  "h1, h2",
            "priority":   2,
            "fame_score": 5,
        },
        # ── GOVERNMENT (Priority 2 — but slow-changing content) ──────────
        {
            "company":    "NITI Aayog",
            "url":        "https://www.niti.gov.in/internship",
            "title_sel":  "h1, h2, .field-item",
            "priority":   2,
            "fame_score": 6,
        },
        {
            "company":    "RBI",
            "url":        "https://opportunities.rbi.org.in/Scripts/Internships.aspx",
            "title_sel":  "h2, h3, td",
            "priority":   2,
            "fame_score": 7,
        },
        {
            "company":    "Bosch India",
            "url":        "https://www.bosch.in/careers/your-entry-into-bosch/internships/",
            "title_sel":  "h1, h2, h3",
            "priority":   2,
            "fame_score": 7,
        },
        # ── BOUTIQUE FASHION (Priority 3 — low applicant volume) ─────────
        {
            "company":    "Sabyasachi Mukherjee",
            "url":        "https://www.sabyasachi.com/careers",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 4,
        },
        {
            "company":    "Manish Malhotra",
            "url":        "https://www.manishmalhotra.in/pages/careers",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 4,
        },
        {
            "company":    "Anita Dongre",
            "url":        "https://www.anitadongre.com/pages/careers",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 4,
        },
        # ── FILM / ENTERTAINMENT (Priority 3 — rare/irregular openings) ──
        {
            "company":    "Yash Raj Films (YRF)",
            "url":        "https://www.yashrajfilms.com/careers",
            "title_sel":  "h1, h2, h3",
            "priority":   3,
            "fame_score": 5,
        },
        {
            "company":    "Red Chillies Entertainment",
            "url":        "https://www.redchillies.com/careers",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 4,
        },
        {
            "company":    "Reliance Entertainment",
            "url":        "https://www.relianceentertainment.net/careers",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 4,
        },
        # ── QUANT (Priority 3 — rare openings) ───────────────────────────
        {
            "company":    "AlphaGrep Securities",
            "url":        "https://www.alphagrep.com/careers",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 5,
        },
        {
            "company":    "Graviton Research Capital",
            "url":        "https://gravitonrc.com/careers",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 5,
        },
        {
            "company":    "Quadeye",
            "url":        "https://quadeye.com/careers/",
            "title_sel":  "h1, h2",
            "priority":   3,
            "fame_score": 4,
        },
    ]

    # ══════════════════════════════════════════════════════════════════════
    #  TIME-BASED PRIORITY SCHEDULER
    #
    #  Instead of a call-count cycle, we track the LAST SCRAPED TIMESTAMP
    #  for every company in a persistent JSON sidecar file.
    #  A company is re-scraped only when:
    #      now - last_scraped  >=  priority_interval
    #
    #  Priority intervals (overridden by scheduler_intervals dict below):
    #    Priority 1 (fame ≥ 8) — every 3 hours   (high-volume companies)
    #    Priority 2 (fame 5-7) — every 6 hours   (mid-tier companies)
    #    Priority 3 (fame 1-4) — every 24 hours  (govt / boutique / rare)
    #
    #  The sidecar file is:  company_scrape_times.json
    #  Format: { "TCS": "2024-04-14T09:30:00", ... }
    # ══════════════════════════════════════════════════════════════════════

    SCRAPE_TIMES_FILE = "company_scrape_times.json"
    PRIORITY_INTERVALS = {1: 3, 2: 6, 3: 24}   # hours

    # Load last-scraped timestamps
    try:
        with open(SCRAPE_TIMES_FILE, encoding="utf-8") as _f:
            _last_scraped: dict = json.load(_f)
    except (FileNotFoundError, json.JSONDecodeError):
        _last_scraped = {}

    def _is_due(target: dict) -> bool:
        """Return True if the company hasn't been scraped recently enough."""
        key       = target["company"]
        interval  = PRIORITY_INTERVALS.get(target["priority"], 24)
        last_str  = _last_scraped.get(key)
        if not last_str:
            return True   # never scraped
        try:
            last_dt = datetime.fromisoformat(last_str)
        except ValueError:
            return True
        elapsed_hours = (datetime.now() - last_dt).total_seconds() / 3600
        return elapsed_hours >= interval

    # Determine which companies are due this run — sorted by fame desc
    targets_due = [
        t for t in sorted(COMPANY_LIVE_TARGETS,
                          key=lambda x: x["fame_score"], reverse=True)
        if _is_due(t)
    ]

    p1 = sum(1 for t in targets_due if t["priority"] == 1)
    p2 = sum(1 for t in targets_due if t["priority"] == 2)
    p3 = sum(1 for t in targets_due if t["priority"] == 3)
    skipped = len(COMPANY_LIVE_TARGETS) - len(targets_due)

    print(f"\n  [Time-based] Scraping {len(targets_due)} companies due "
          f"(P1={p1}×3h, P2={p2}×6h, P3={p3}×24h | {skipped} skipped — not due yet)")

    # ── Helper: fallback navigation steps when a page cannot be opened ──
    def _fallback_steps(target: dict) -> str:
        """
        Return a human-readable string with step-by-step instructions to
        manually reach the internship page, used when scraping fails.
        """
        company = target["company"]
        url     = target["url"]

        # Extract root domain for homepage link
        m = re.match(r"(https?://[^/]+)", url)
        homepage = m.group(1) if m else url

        steps = (
            f"1. Go to: {homepage}\n"
            f"2. Look for 'Careers', 'Jobs', or 'Work With Us' in the header/footer.\n"
            f"3. Click on 'Students', 'Campus', or 'Internships' section.\n"
            f"4. Search or filter for 'Intern' or 'Trainee' roles.\n"
            f"5. Direct careers URL (may require login or JS): {url}"
        )
        return steps

    # ── Helper: build one internship record from scraped page text ───────
    def _build_company_record(
        target: dict,
        title_text: str,
        link: str,
        page_text: str,
        page_ok: bool,
    ) -> dict:
        """
        Build a full internship record with all requested fields:
          - company, title, apply_link
          - mode (WFH / On-site / Hybrid / Remote)
          - stipend (amount if mentioned, or Not disclosed / Unpaid)
          - duration (months/weeks if mentioned)
          - gender (All / Girls Only / Boys Only)
          - location, deadline, eligibility, branch, cgpa
          - access_note: navigation steps if page was blocked/empty
        """
        rec = empty_record("Company Careers")
        rec["company"]    = target["company"]
        rec["title"]      = title_text
        rec["apply_link"] = link or target["url"]
        rec["fame_score"] = target["fame_score"]
        rec["priority"]   = target["priority"]

        if not page_ok or len(page_text.strip()) < 80:
            # Page failed to load or was mostly empty (JS SPA / login wall)
            rec["access_note"] = _fallback_steps(target)
            rec["mode"]           = "Check official page"
            rec["stipend"]        = "Check official page"
            rec["duration"]       = "Check official page"
            rec["gender"]         = "Check official page"
            return rec

        # ── Mode ────────────────────────────────────────────────────────
        rec["mode"] = extract_mode(page_text)

        # ── Stipend ─────────────────────────────────────────────────────
        # First try a tight window around stipend/salary keywords
        stipend_window = ""
        m = re.search(
            r"(?:stipend|salary|pay|compensation|remuneration)"
            r"[^\n]{0,120}",
            page_text, re.I
        )
        if m:
            stipend_window = m.group(0)
        rec["stipend"] = extract_stipend(stipend_window or page_text[:1000])

        # ── Duration ────────────────────────────────────────────────────
        dur_window = ""
        m = re.search(
            r"(?:duration|tenure|period|internship\s+for)"
            r"[^\n]{0,80}",
            page_text, re.I
        )
        if m:
            dur_window = m.group(0)
        rec["duration"] = extract_duration(dur_window or page_text[:800])

        # ── Internship type ─────────────────────────────────────────────
        rec["internship_type"] = extract_internship_type(page_text)

        # ── Location ────────────────────────────────────────────────────
        loc_m = re.search(
            r"(?:location|city|place|office)[:\s]+([\w\s,/]+?)(?:\.|,|\n|apply|$)",
            page_text, re.I,
        )
        rec["location"] = loc_m.group(1).strip() if loc_m else "India"

        # ── Deadline ────────────────────────────────────────────────────
        dead_m = re.search(
            r"(?:last\s*date|apply\s*by|deadline|closes?)[:\s]+([\d\w\s,]+?)(?:\.|,|\n|$)",
            page_text, re.I,
        )
        rec["deadline"] = dead_m.group(1).strip() if dead_m else "N/A"

        # ── Eligibility block ────────────────────────────────────────────
        elig = ""
        for label in [
            "eligibility", "who can apply", "qualification",
            "requirements", "criteria", "education"
        ]:
            em = re.search(
                r"(?:" + re.escape(label) + r")\s*[:\-]?\s*(.{10,400}?)(?:\n\n|apply|$)",
                page_text, re.I | re.S,
            )
            if em:
                elig = em.group(1).strip(); break

        rec["eligibility_raw"] = elig if elig else "Check official page"
        rec["cgpa_required"]   = parse_cgpa(elig)
        rec["branch_required"] = parse_branches(elig)

        # ── Gender ───────────────────────────────────────────────────────
        # Check eligibility block + title + a wider gender-specific window
        gender_window = page_text[:2000]
        rec["gender"] = parse_gender(elig + " " + title_text + " " + gender_window,
                                     title_text)

        # ── Skills ───────────────────────────────────────────────────────
        skills_m = re.search(
            r"(?:skills?|technologies?|tools?)[:\s]+([\w\s,/+#.]+?)(?:\n|apply|$)",
            page_text, re.I,
        )
        if skills_m:
            rec["skills"] = skills_m.group(1).strip()[:200]

        # ── Access note: empty if page loaded fine ────────────────────────
        rec["access_note"] = ""
        return rec

    # ── Main scrape loop ─────────────────────────────────────────────────
    for target in targets_due:
        p_label = f"P{target['priority']}(★{target['fame_score']})"
        interval_h = PRIORITY_INTERVALS[target["priority"]]
        print(f"  [{p_label} every {interval_h}h] {target['company']:<42}", end=" ", flush=True)

        page_ok   = False
        page_text = ""
        soup      = None

        try:
            html = get_html(
                driver, target["url"],
                wait_css=target["title_sel"].split(",")[0].strip(),
                delay=delay,
            )
            soup      = BeautifulSoup(html, "lxml")
            page_text = soup.get_text(" ", strip=True)
            page_ok   = len(page_text.strip()) > 80

        except Exception as e:
            print(f"LOAD-ERR({e}) — using fallback steps")

        if page_ok and soup:
            # ── Collect all internship-looking links ─────────────────
            apply_links = []
            for a in soup.find_all("a", href=True):
                href   = a["href"]
                anchor = a.get_text(strip=True).lower()
                if re.search(
                    r"apply|intern|trainee|register|apply now|view|job|opening|campus",
                    anchor, re.I
                ):
                    full = (href if href.startswith("http")
                            else target["url"].rstrip("/") + "/" + href.lstrip("/"))
                    apply_links.append(full)

            # ── Find per-listing headings on the page ────────────────
            headings      = soup.find_all(["h2", "h3", "h4"])
            intern_hdrs   = [
                h for h in headings
                if re.search(
                    r"intern|trainee|student|campus|summer|placement",
                    h.get_text(), re.I
                )
            ]

            if intern_hdrs:
                for i, h in enumerate(intern_hdrs[:10]):
                    link = apply_links[i] if i < len(apply_links) else target["url"]
                    rec  = _build_company_record(
                        target, h.get_text(strip=True), link, page_text, True
                    )
                    records.append(rec)
                print(f"OK — {len(intern_hdrs)} listing(s)")
            else:
                # Single-record fallback
                h_tag = soup.find("h1") or soup.find("h2")
                title = (h_tag.get_text(strip=True)
                         if h_tag else f"{target['company']} Internship")
                link  = apply_links[0] if apply_links else target["url"]
                rec   = _build_company_record(
                    target, title, link, page_text, True
                )
                records.append(rec)
                print(f"OK — 1 listing (page-level fallback)")

        else:
            # Page blocked / empty — store a record with navigation guide
            rec = _build_company_record(
                target,
                f"{target['company']} Internship",
                target["url"],
                page_text,
                False,
            )
            records.append(rec)
            print(f"BLOCKED — fallback navigation steps stored")

        # ── Update last-scraped timestamp ─────────────────────────────
        _last_scraped[target["company"]] = datetime.now().isoformat(timespec="seconds")
        try:
            with open(SCRAPE_TIMES_FILE, "w", encoding="utf-8") as _f:
                json.dump(_last_scraped, _f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        time.sleep(delay * 0.5)

    # ── Print next-due schedule ───────────────────────────────────────────
    print(f"\n  {'Company':<42} {'Priority':<10} {'Interval':<10} {'Next scrape due'}")
    print(f"  {'-'*80}")
    for t in sorted(COMPANY_LIVE_TARGETS, key=lambda x: x["fame_score"], reverse=True):
        last = _last_scraped.get(t["company"])
        if last:
            try:
                next_due = datetime.fromisoformat(last)
                from datetime import timedelta
                next_due += timedelta(hours=PRIORITY_INTERVALS[t["priority"]])
                next_str = next_due.strftime("%Y-%m-%d %H:%M")
            except Exception:
                next_str = "Unknown"
        else:
            next_str = "Immediately"
        print(f"  {t['company']:<42} P{t['priority']:<9} "
              f"{PRIORITY_INTERVALS[t['priority']]}h{'':<7} {next_str}")

    girls_count = sum(1 for r in records if r.get("gender") == "Girls Only")
    blocked     = sum(1 for r in records if r.get("access_note", "").strip())
    print(f"\n  Company entries total : {len(records)}")
    print(f"  Female-specific       : {girls_count}")
    print(f"  Blocked / fallback    : {blocked} (navigation steps included in access_note)")
    return records

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

SOURCE_MAP = {
    "unstop":      scrape_unstop,
    "internshala": scrape_internshala,
    "naukri":      scrape_naukri,
    "aicte":       scrape_aicte,
    "companies":   scrape_companies,
}

FINAL_COLS = [
    "source", "title", "company", "location",
    # ── Key fields ──────────────────────────────────────────────────────
    "stipend",          # Pay amount / Unpaid / Not disclosed / Check official page
    "duration",         # 2 months / 6 weeks / Check official page
    "mode",             # Work From Home / On-site / Hybrid / Remote
    "internship_type",  # Full Time / Part Time / Flexible
    # ── Eligibility ─────────────────────────────────────────────────────
    "branch_required",  # CSE / ECE / All / Not mentioned
    "cgpa_required",
    "gender",           # All / Girls Only / Boys Only / Check official page
    "eligibility_raw",
    # ── Access / Navigation ──────────────────────────────────────────────
    "apply_link",       # Direct URL — or homepage if page was blocked
    "access_note",      # Step-by-step navigation guide if page was blocked/JS
    # ── Metadata ────────────────────────────────────────────────────────
    "priority",         # 1 / 2 / 3 — scrape frequency tier
    "fame_score",       # 1–10 fame ranking
    "skills", "deadline", "applicants",
]


def scrape_all(sources: list[str], pages: int, keyword: str,
               fetch_details: bool, headless: bool, delay: float) -> list[dict]:

    print(f"\n{'='*62}")
    print(f"  Multi-Source Internship Scraper")
    print(f"  Sources : {', '.join(sources)}")
    print(f"  Keyword : '{keyword or 'all'}' | Pages/source: {pages} | Details: {'ON' if fetch_details else 'OFF'}")
    print(f"{'='*62}")

    driver = make_driver(headless=headless)
    all_records = []

    try:
        for src in sources:
            fn = SOURCE_MAP.get(src)
            if not fn:
                print(f"  [WARN] Unknown source '{src}' — skipping."); continue
            try:
                results = fn(driver, pages, keyword, fetch_details, delay)
                all_records.extend(results)
                print(f"  → {src}: {len(results)} listings collected")
            except Exception as e:
                print(f"  [ERROR] {src} scraper failed: {e}")
    finally:
        driver.quit()

    return all_records


def save(records: list[dict], output_path: str):
    """
    Saves scraped data in THREE formats so the Flask backend can
    easily consume it:

      1. internships_YYYYMMDD.json   — Main file. Flask loads this directly.
      2. internships_YYYYMMDD.csv    — Spreadsheet for manual review.
      3. internships_YYYYMMDD_by_source.json — Data split by source,
                                               useful for filtered API endpoints.

    JSON structure (internships_YYYYMMDD.json):
    {
      "scraped_at": "2024-04-14T10:30:00",
      "total": 150,
      "sources": ["Unstop", "Internshala", "Naukri", "AICTE"],
      "internships": [
        {
          "source": "Unstop",
          "title": "...",
          "company": "...",
          "location": "...",
          "stipend": "...",
          "duration": "...",
          "job_type": "...",
          "deadline": "...",
          "skills": "...",
          "applicants": "...",
          "eligibility_raw": "...",
          "cgpa_required": "...",
          "branch_required": "...",
          "gender": "All / Girls Only / Boys Only",
          "apply_link": "https://..."
        },
        ...
      ]
    }
    """
    if not records:
        print("\nNo data scraped — nothing to save."); return

    # Deduplicate and filter columns
    df = pd.DataFrame(records)
    df.drop_duplicates(subset=["apply_link"], inplace=True)
    df = df[[c for c in FINAL_COLS if c in df.columns]]
    df = df.where(pd.notna(df), None)   # replace NaN with None → null in JSON

    scraped_at = datetime.now().isoformat(timespec="seconds")
    internships = df.to_dict(orient="records")

    # ── 1. Main JSON file ──────────────────────────────────────────────────
    base = output_path.replace(".csv", "").replace(".json", "")
    json_path = base + ".json"

    payload = {
        "scraped_at":  scraped_at,
        "total":       len(internships),
        "sources":     sorted(df["source"].unique().tolist()),
        "internships": internships,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # ── 2. CSV (for manual review / Excel) ────────────────────────────────
    csv_path = base + ".csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # ── 3. Split by source JSON (for filtered Flask endpoints) ────────────
    by_source_path = base + "_by_source.json"
    by_source = {}
    for src, group in df.groupby("source"):
        by_source[src] = group.to_dict(orient="records")
    with open(by_source_path, "w", encoding="utf-8") as f:
        json.dump(by_source, f, ensure_ascii=False, indent=2)

    # ── Terminal summary ───────────────────────────────────────────────────
    print(f"\n{'='*62}")
    print(f"  Saved {len(df)} internships")
    print(f"  📄 JSON (Flask ready) → {json_path}")
    print(f"  📊 CSV  (spreadsheet) → {csv_path}")
    print(f"  📦 By-source JSON     → {by_source_path}")
    print(f"\n  Breakdown by source:")
    for src, cnt in df["source"].value_counts().items():
        print(f"    {src:<20}: {cnt}")

    girls = df[df["gender"] == "Girls Only"]
    print(f"\n  Female-specific programs : {len(girls)}")
    if not girls.empty:
        print(girls[["source","title","company","apply_link"]].to_string(index=False))

    if "access_note" in df.columns:
        blocked = df[df["access_note"].str.strip().astype(bool)]
        print(f"\n  Blocked pages (fallback navigation provided): {len(blocked)}")
        if not blocked.empty:
            for _, row in blocked.iterrows():
                print(f"\n    ── {row.get('company','?')} ──")
                print(f"    Link  : {row.get('apply_link','')}")
                print(f"    Steps :\n" +
                      "\n".join("      " + l for l in
                                str(row.get("access_note","")).splitlines()))

    if "priority" in df.columns:
        print(f"\n  Company scrape priority breakdown:")
        for pri, lbl in [(1,"P1 every 3h"),(2,"P2 every 6h"),(3,"P3 every 24h")]:
            n = len(df[df["priority"] == pri])
            if n: print(f"    {lbl:<15}: {n} listings")

    print(f"{'='*62}")

    print("\nPreview (first 5 rows):\n")
    preview = ["source", "title", "company", "cgpa_required", "gender", "apply_link"]
    print(df[[c for c in preview if c in df.columns]].head(5).to_string(index=False))

    # ── Flask usage hint ───────────────────────────────────────────────────
    print(f"""
  Flask backend — load data like this:
  ─────────────────────────────────────────────────────────
  import json
  from flask import Flask, jsonify, request

  app = Flask(__name__)

  with open("{json_path}", encoding="utf-8") as f:
      DATA = json.load(f)

  @app.route("/internships")
  def get_internships():
      src    = request.args.get("source")       # ?source=Unstop
      gender = request.args.get("gender")       # ?gender=Girls Only
      cgpa   = request.args.get("cgpa")         # ?cgpa=7
      result = DATA["internships"]
      if src:
          result = [i for i in result if i["source"] == src]
      if gender:
          result = [i for i in result if i["gender"] == gender]
      if cgpa:
          result = [i for i in result if i["cgpa_required"] != "Not mentioned"
                    and float(i["cgpa_required"] or 0) <= float(cgpa)]
      return jsonify(total=len(result), internships=result)

  @app.route("/internships/female")
  def female_internships():
      result = [i for i in DATA["internships"] if i["gender"] == "Girls Only"]
      return jsonify(total=len(result), internships=result)
  ─────────────────────────────────────────────────────────
""")


# ══════════════════════════════════════════════════════════════════════════════
#  TIER-BASED SCHEDULER
#
#  Source-level tiers (what platform/aggregator to scrape):
#  Tier 1 — every 6h  : Unstop + Company Career Pages
#  Tier 2 — every 12h : Internshala, Naukri
#  Tier 3 — every 24h : AICTE
#
#  Company-level priority (inside scrape_companies, per call):
#  Priority 1 (fame ≥8) — scraped EVERY call  (TCS, Infosys, D.E. Shaw, etc.)
#  Priority 2 (fame 5-7) — scraped every 2nd call  (media, fashion, govt)
#  Priority 3 (fame 1-4) — scraped every 4th call  (boutique fashion, film)
#
#  Fame scores (1–10):
#   10 : TCS, Infosys          (massive hiring volume)
#    9 : Wipro, HCLTech, D.E. Shaw
#    8 : LTIMindtree, Tata Elxsi, Tower Research, WorldQuant
#    7 : Persistent, Sarvam AI, Krutrim, Times Group, RBI, Bosch, Reliance Retail
#    6 : NDTV, India Today, The Hindu, Network18, NITI Aayog, Fractal, Fabindia
#    5 : Indian Express, Affle, YRF, AlphaGrep, Graviton
#    4 : Sabyasachi, Manish Malhotra, Anita Dongre, Quadeye, Red Chillies
#
#  Each tier runs in its OWN thread independently.
#  All tiers write to LATEST_JSON which Flask always reads.
# ══════════════════════════════════════════════════════════════════════════════

import threading
import signal
import sys
import os

LATEST_JSON = "internships_latest.json"

# ── Tier definitions ───────────────────────────────────────────────────────
TIERS = {
    1: {
        "name":     "Tier 1 — High-Fame Companies (every 3h)",
        "sources":  ["unstop", "companies"],
        "interval": 3,
        "color":    "🔴",
    },
    2: {
        "name":     "Tier 2 — Mid-Fame / Aggregators (every 6h)",
        "sources":  ["internshala", "naukri"],
        "interval": 6,
        "color":    "🟡",
    },
    3: {
        "name":     "Tier 3 — Govt / Boutique / AICTE (every 24h)",
        "sources":  ["aicte"],
        "interval": 24,
        "color":    "🟢",
    },
}

# Shared store — each tier writes its results here under its tier key.
# Protected by a lock so concurrent writes don't corrupt data.
_data_store: dict = {1: [], 2: [], 3: []}
_store_lock = threading.Lock()
_stop_event = threading.Event()


def _merge_and_save():
    """
    Merges all tier data into one unified JSON file (LATEST_JSON).
    Called every time any tier finishes a scrape cycle.
    """
    with _store_lock:
        all_records = []
        for tier_records in _data_store.values():
            all_records.extend(tier_records)

    if not all_records:
        return

    # Deduplicate by apply_link across all tiers
    seen, unique = set(), []
    for r in all_records:
        key = r.get("apply_link", "") or r.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)

    # Build company priority summary for the JSON metadata
    company_priority_map = {
        t["company"]: {"priority": t["priority"], "fame_score": t["fame_score"]}
        for t in (
            # inline the priority table so _merge_and_save stays self-contained
            [{"company": c, "priority": p, "fame_score": f} for c, p, f in [
                ("Tata Consultancy Services (TCS)", 1, 10),
                ("Infosys",                          1, 10),
                ("Wipro",                            1,  9),
                ("HCLTech",                          1,  9),
                ("D. E. Shaw India",                 1,  9),
                ("LTIMindtree",                      1,  8),
                ("Tata Elxsi",                       1,  8),
                ("Tower Research Capital",           1,  8),
                ("WorldQuant",                       1,  8),
                ("Sarvam AI",                        1,  7),
                ("Krutrim (Ola AI)",                 1,  7),
                ("Persistent Systems",               1,  7),
                ("The Times Group",                  2,  7),
                ("RBI",                              2,  7),
                ("Bosch India",                      2,  7),
                ("Reliance Retail (Fashion & Lifestyle)", 2, 7),
                ("Aditya Birla Fashion and Retail (ABFRL)", 2, 7),
                ("NDTV",                             2,  6),
                ("India Today Group",                2,  6),
                ("The Hindu Group",                  2,  6),
                ("Network18",                        2,  6),
                ("NITI Aayog",                       2,  6),
                ("Fractal Analytics",                2,  6),
                ("Fabindia",                         2,  6),
                ("The Indian Express Group",         2,  5),
                ("Affle",                            2,  5),
                ("Yash Raj Films (YRF)",             3,  5),
                ("AlphaGrep Securities",             3,  5),
                ("Graviton Research Capital",        3,  5),
                ("Sabyasachi Mukherjee",             3,  4),
                ("Manish Malhotra",                  3,  4),
                ("Anita Dongre",                     3,  4),
                ("Red Chillies Entertainment",       3,  4),
                ("Reliance Entertainment",           3,  4),
                ("Quadeye",                          3,  4),
            ]]
        )
    }

    payload = {
        "scraped_at":   datetime.now().isoformat(timespec="seconds"),
        "total":        len(unique),
        "sources":      sorted({r.get("source","") for r in unique}),
        "tier_summary": {
            f"tier_{t}": {
                "sources":        TIERS[t]["sources"],
                "interval_hours": TIERS[t]["interval"],
                "count":          len(_data_store[t]),
            }
            for t in TIERS
        },
        "company_priority_summary": {
            "description": (
                "fame_score 8-10 → Priority 1 (scraped every cycle), "
                "5-7 → Priority 2 (every 2nd cycle), "
                "1-4 → Priority 3 (every 4th cycle)"
            ),
            "companies": company_priority_map,
        },
        "internships":  unique,
    }

    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  💾 Merged {len(unique)} listings → {LATEST_JSON}")


def _run_tier(tier_num, pages, keyword, fetch_details, headless, delay):
    """Run one scrape cycle for a specific tier and update the data store."""
    tier   = TIERS[tier_num]
    icon   = tier["color"]
    name   = tier["name"]
    sources = tier["sources"]

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{icon} [{ts}] {name} — scraping: {', '.join(sources)}")

    try:
        results = scrape_all(
            sources=sources,
            pages=pages,
            keyword=keyword,
            fetch_details=fetch_details,
            headless=headless,
            delay=delay,
        )

        # Update this tier's slice in the shared store
        with _store_lock:
            _data_store[tier_num] = results

        # Save archive copy for this tier
        os.makedirs("archive", exist_ok=True)
        archive_base = (
            f"archive/tier{tier_num}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        save(results, archive_base)

        # Merge all tiers and write latest file
        _merge_and_save()

        ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{icon} [{ts2}] {name} done — "
              f"{len(results)} listings. Next in {tier['interval']}h.")

    except Exception as e:
        print(f"{icon} [ERROR] {name} cycle failed: {e}")


def _tier_loop(tier_num, pages, keyword, fetch_details, headless, delay):
    """
    Independent loop for one tier.
    Runs immediately on start, then waits its interval before repeating.
    """
    interval_sec = TIERS[tier_num]["interval"] * 3600

    while not _stop_event.is_set():
        _run_tier(tier_num, pages, keyword, fetch_details, headless, delay)
        _stop_event.wait(timeout=interval_sec)

    print(f"  {TIERS[tier_num]['color']} {TIERS[tier_num]['name']} stopped.")


def signal_handler(sig, frame):
    print("\n\n  Ctrl+C received — stopping all tiers gracefully...")
    _stop_event.set()
    sys.exit(0)


def parse_args():
    p = argparse.ArgumentParser(
        description="Multi-source internship scraper — fame-based tier scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scrape Schedule:
  Tier 1 (every  3h): Unstop + Company careers (P1 companies: TCS, Infosys, D.E. Shaw…)
  Tier 2 (every  6h): Internshala, Naukri      (P2 companies: Times Group, ABFRL…)
  Tier 3 (every 24h): AICTE                    (P3 companies: Govt, boutique fashion…)

Company Priority (inside each companies scrape):
  P1 fame≥8  — refreshed every 3h  (TCS, Infosys, Wipro, D.E. Shaw, WorldQuant…)
  P2 fame5-7 — refreshed every 6h  (Times Group, NDTV, ABFRL, Fabindia, RBI…)
  P3 fame1-4 — refreshed every 24h (Sabyasachi, Hombale, Red Chillies, Quadeye…)

If a company page is blocked / JS-only, the record will contain:
  apply_link  : the careers homepage (fallback)
  access_note : step-by-step navigation instructions

Examples:
  python internship_scraper.py                         # full scheduler
  python internship_scraper.py --once                  # run once, no scheduler
  python internship_scraper.py --tiers 1,2             # only Tier 1 and 2
  python internship_scraper.py --t1 2 --t2 4 --t3 12  # custom intervals
  python internship_scraper.py --once --no-details --pages 1  # quick test
        """
    )
    p.add_argument("--pages",       type=int,   default=2,
                   help="Pages per source per cycle (default: 2)")
    p.add_argument("--keyword",     type=str,   default="",
                   help="Filter keyword e.g. 'data science'")
    p.add_argument("--delay",       type=float, default=2.5,
                   help="Seconds between requests (default: 2.5)")
    p.add_argument("--tiers",       type=str,   default="1,2,3",
                   help="Which tiers to run, e.g. --tiers 1,2 (default: all)")
    p.add_argument("--t1",          type=float, default=3.0,
                   help="Tier 1 interval in hours (default: 3)")
    p.add_argument("--t2",          type=float, default=6.0,
                   help="Tier 2 interval in hours (default: 6)")
    p.add_argument("--t3",          type=float, default=24.0,
                   help="Tier 3 interval in hours (default: 24)")
    p.add_argument("--once",        action="store_true",
                   help="Run all selected tiers once and exit (no scheduler)")
    p.add_argument("--no-details",  action="store_true",
                   help="Skip detail pages — faster but less eligibility data")
    p.add_argument("--no-headless", action="store_true",
                   help="Show browser window (useful for debugging)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Apply custom intervals from CLI
    TIERS[1]["interval"] = args.t1
    TIERS[2]["interval"] = args.t2
    TIERS[3]["interval"] = args.t3

    # Which tiers to activate
    active_tiers = [int(t.strip()) for t in args.tiers.split(",") if t.strip().isdigit()]

    common = dict(
        pages=args.pages,
        keyword=args.keyword,
        fetch_details=not args.no_details,
        headless=not args.no_headless,
        delay=args.delay,
    )

    signal.signal(signal.SIGINT, signal_handler)
    os.makedirs("archive", exist_ok=True)

    if args.once:
        # ── Single run — all active tiers sequentially ─────────────────────
        print("\n  Running all tiers once (no scheduler)...")
        for t in active_tiers:
            _run_tier(t, **common)
        print(f"\n  Done. Output → {LATEST_JSON}")

    else:
        # ── Tier-based scheduler — each tier in its own thread ─────────────
        print(f"""
{"="*66}
  Fame-Based Tier Scheduler
{"="*66}
  🔴 Tier 1 — every {TIERS[1]["interval"]:>2}h : {", ".join(TIERS[1]["sources"])}
              Company P1 (fame≥8): TCS, Infosys, D.E. Shaw, WorldQuant…
  🟡 Tier 2 — every {TIERS[2]["interval"]:>2}h : {", ".join(TIERS[2]["sources"])}
              Company P2 (fame5-7): Times Group, ABFRL, Fabindia, RBI…
  🟢 Tier 3 — every {TIERS[3]["interval"]:>2}h : {", ".join(TIERS[3]["sources"])}
              Company P3 (fame1-4): Sabyasachi, Hombale, Quadeye…
{"="*66}
  Active tiers : {active_tiers}
  Output       : {LATEST_JSON}  (merged, always latest)
  Times sidecar: company_scrape_times.json
  Archive      : archive/tierN_YYYYMMDD_HHMM.json
  Stop         : Ctrl+C
{"="*66}

  Flask tip:
    @app.route("/internships")
    def get_internships():
        with open("internships_latest.json", encoding="utf-8") as f:
            return jsonify(json.load(f))

    @app.route("/internships/female")
    def female_only():
        data = json.load(open("internships_latest.json"))
        return jsonify([i for i in data["internships"] if i["gender"]=="Girls Only"])

    # When apply_link is blocked, access_note has step-by-step navigation:
    @app.route("/internships/blocked")
    def blocked():
        data = json.load(open("internships_latest.json"))
        return jsonify([i for i in data["internships"] if i.get("access_note","")])
""")

        threads = []
        for t in active_tiers:
            thread = threading.Thread(
                target=_tier_loop,
                kwargs={"tier_num": t, **common},
                name=f"Tier-{t}",
                daemon=True,
            )
            thread.start()
            threads.append(thread)
            # Stagger tier starts so they don't all hammer sites at once
            time.sleep(10)

        print(f"  {len(threads)} tier thread(s) running. Waiting...")

        try:
            while any(t.is_alive() for t in threads):
                time.sleep(1)
        except KeyboardInterrupt:
            _stop_event.set()
