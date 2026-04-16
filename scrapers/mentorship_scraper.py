"""
Multi-Source Mentorship Programme Scraper
==========================================
Scrapes mentorship programme listings from official company websites.

Strategy (same as internship scraper):
  • Tier 1 (every  6h) : Google, Microsoft, Amazon, Apple, Meta, Adobe, Goldman Sachs,
                         JP Morgan, McKinsey, BCG, Morgan Stanley, NXP, D.E. Shaw, Nestlé
  • Tier 2 (every 12h) : Bosch, Siemens, L&T, Unstop Mentorship, Internshala Mentorship
  • Tier 3 (every 24h) : ISRO, DRDO, NITI Aayog, RBI, AICTE Mentorship

No APIs used anywhere — pure Selenium + BeautifulSoup scraping.
Curated stable entries used for heavy JS SPA portals (same as internship scraper).

Output:
  mentorship_latest.json          ← Flask reads this (always latest, merged)
  mentorship_latest.csv           ← Spreadsheet
  archive/tierN_YYYYMMDD_HHMM.*   ← Per-tier timestamped history

Terminal output format mirrors internship scraper exactly.

Requirements:
    pip install selenium pandas beautifulsoup4 lxml

Usage:
    python mentorship_scraper.py               # all tiers, auto-refresh
    python mentorship_scraper.py --once        # run once and exit
    python mentorship_scraper.py --tiers 1,2   # only tier 1 and 2
    python mentorship_scraper.py --t1 4 --t2 8 --t3 16   # custom intervals
    python mentorship_scraper.py --no-headless # show browser window
"""

import re
import os
import time
import json
import signal
import threading
import argparse
import sys
from urllib.parse import quote_plus
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ══════════════════════════════════════════════════════════════════════════════
#  TIER DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

TIERS = {
    1: {
        "name":     "Tier 1 (High Frequency)",
        "sources":  ["google", "microsoft", "amazon", "apple", "meta",
                     "adobe", "goldman_sachs", "jpmorgan", "mckinsey",
                     "bcg", "morgan_stanley", "nxp", "deshaw", "nestle"],
        "interval": 6,
        "color":    "🔴",
    },
    2: {
        "name":     "Tier 2 (Medium Frequency)",
        "sources":  [
            "bosch", "siemens", "lt", "unstop", "internshala",
            "infosys", "wipro", "hcltech", "ltimindtree", "tata_elxsi",
            "persistent", "fractal", "affle", "sarvam_ai", "krutrim",
            "worldquant", "jane_street", "citadel", "tower_research",
            "alphagrep", "graviton", "quadeye", "times_group", "ndtv",
            "india_today", "hindu_group", "network18", "indian_express",
            "yrf", "dharma", "red_chillies", "excel", "hombale",
            "reliance_entertainment", "sabyasachi", "manish_malhotra",
            "anita_dongre", "fabindia", "reliance_retail", "abfrl",
            "global_captives"
        ],
        "interval": 12,
        "color":    "🟡",
    },
    3: {
        "name":     "Tier 3 (Low Frequency)",
        "sources":  ["isro", "drdo", "niti_aayog", "rbi", "aicte"],
        "interval": 24,
        "color":    "🟢",
    },
}

# Shared store
_data_store: dict = {1: [], 2: [], 3: []}
_store_lock  = threading.Lock()
_stop_event  = threading.Event()

LATEST_JSON = "mentorship_latest.json"

FINAL_COLS = [
    "source", "company", "programme_name", "programme_type",
    "description", "duration", "mode", "eligibility",
    "branch_required", "cgpa_required", "gender",
    "stipend_or_benefits", "deadline", "apply_link",
    "how_to_apply",   # Step-by-step instructions after landing on the page
]


# ══════════════════════════════════════════════════════════════════════════════
#  DRIVER
# ══════════════════════════════════════════════════════════════════════════════

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


def get_html(driver, url: str, wait_css: str = None,
             scroll: bool = True, delay: float = 2.5) -> str:
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


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

FEMALE_RE = re.compile(
    r"\b(women|woman|girls?|female|she\s*codes?|pragati|saksham|"
    r"girls?\s*only|female\s*only|women\s*only|only\s*(?:girls?|women|female))\b",
    re.I,
)

BRANCH_KEYWORDS = [
    "computer science", "cse", "information technology", "it",
    "electronics", "ece", "eee", "electrical", "mechanical", "civil",
    "chemical", "biotechnology", "data science", "mba", "bca", "mca",
    "mathematics", "statistics", "physics", "commerce", "management",
    "finance", "marketing", "all branches", "any branch",
]


def extract_gender(text: str, title: str = "") -> str:
    combined = (text + " " + title).lower()
    if FEMALE_RE.search(combined):
        return "Girls Only / Women"
    if re.search(r"\b(boys?\s*only|male\s*only|men\s*only)\b", combined):
        return "Boys Only"
    return "All"


def extract_branch(text: str) -> str:
    tl = text.lower()
    if re.search(r"\ball\s*(branches|engineering|streams|students)\b", tl):
        return "All"
    if re.search(r"\bopen\s+to\s+all\b", tl):
        return "All"
    found, seen = [], set()
    for kw in BRANCH_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", tl):
            if kw in ("cse", "computer science"):           c = "Computer Science"
            elif kw in ("it", "information technology"):    c = "Information Technology"
            elif kw in ("ece", "eee", "electronics"):       c = "Electronics"
            elif kw in ("all branches", "any branch"):      return "All"
            else:                                            c = kw.title()
            if c not in seen:
                seen.add(c); found.append(c)
    return ", ".join(found) if found else "Not mentioned"


def extract_cgpa(text: str) -> str:
    if not text.strip():
        return "Not mentioned"
    pats = [
        re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:cgpa|gpa|cpi|aggregate)", re.I),
        re.compile(r"(?:cgpa|gpa|cpi|aggregate)\s*(?:of\s*)?(\d+(?:\.\d+)?)", re.I),
        re.compile(r"(?:minimum|min\.?|at\s*least|above|>=?)\s*(\d+(?:\.\d+)?)\s*(?:cgpa|gpa)", re.I),
    ]
    for p in pats:
        m = p.search(text)
        if m:
            try:
                if 1.0 <= float(m.group(1)) <= 10.0:
                    return m.group(1)
            except ValueError:
                pass
    return "Not mentioned"


def extract_duration(text: str) -> str:
    pats = [
        re.compile(r"(\d+)\s*(?:to|[-])\s*(\d+)\s*(months?|weeks?|days?)", re.I),
        re.compile(r"(\d+)\s*(months?|weeks?|days?|years?)", re.I),
        re.compile(r"(one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s*(months?|weeks?)", re.I),
    ]
    for p in pats:
        m = p.search(text)
        if m:
            return m.group(0).strip()
    return "Not mentioned"


def extract_mode(text: str) -> str:
    tl = text.lower()
    if re.search(r"work\s*from\s*home|wfh|fully\s*remote|100%\s*remote", tl):
        return "Remote / Online"
    if re.search(r"\bhybrid\b", tl):
        return "Hybrid"
    if re.search(r"\bvirtual\b|\bonline\b", tl):
        return "Online / Virtual"
    if re.search(r"\bin.person\b|\bon.?site\b|\boffice\b|\boffline\b", tl):
        return "In-Person"
    return "Not mentioned"


def empty_record(source: str, company: str = "N/A") -> dict:
    return {
        "source":             source,
        "company":            company,
        "programme_name":     "N/A",
        "programme_type":     "Mentorship",   # Mentorship / Research / Fellowship
        "description":        "N/A",
        "duration":           "Not mentioned",
        "mode":               "Not mentioned",
        "eligibility":        "Not mentioned",
        "branch_required":    "Not mentioned",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Not mentioned",
        "deadline":           "Not mentioned",
        "apply_link":         "",
        "how_to_apply":       "Visit the link and look for mentorship/student programmes section.",
    }


def print_record(idx: int, total: int, rec: dict):
    """Print one record in the same style as the internship scraper."""
    print(
        f"  [{idx:>4}/{total}] {rec['programme_name'][:55]:<55}\n"
        f"         Company     : {rec['company']}\n"
        f"         Type        : {rec['programme_type']}\n"
        f"         Duration    : {rec['duration']}\n"
        f"         Mode        : {rec['mode']}\n"
        f"         Branch      : {rec['branch_required']}\n"
        f"         CGPA        : {rec['cgpa_required']}\n"
        f"         Gender      : {rec['gender']}\n"
        f"         Benefits    : {rec['stipend_or_benefits'][:50]}\n"
        f"         Deadline    : {rec['deadline']}\n"
        f"         Link        : {rec['apply_link']}\n"
        f"         How to Apply: {rec.get('how_to_apply', 'Visit the link above')}\n"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  CURATED MENTORSHIP PROGRAMMES
#  (Stable known URLs — used for heavy JS SPA portals)
# ══════════════════════════════════════════════════════════════════════════════

CURATED_PROGRAMMES = [
    # ── Google ────────────────────────────────────────────────────────────
    {
        "company":            "Google",
        "programme_name":     "Google Summer of Code (GSoC)",
        "programme_type":     "Mentorship + Open Source",
        "description":        "Paid mentorship programme where students work on open source projects with mentor guidance over 12 weeks.",
        "duration":           "12 weeks",
        "mode":               "Remote / Online",
        "eligibility":        "18+ years, enrolled in post-secondary institution",
        "branch_required":    "Computer Science, Information Technology",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"USD 1,500–3,000 stipend",
        "deadline":           "Check summerofcode.withgoogle.com",
        "apply_link":         "https://summerofcode.withgoogle.com/",
        "how_to_apply":       "Go to summerofcode.withgoogle.com → Click 'Get Started' → Register as a contributor → Browse organisations → Submit proposal.",
    },
    {
        "company":            "Google",
        "programme_name":     "CS Research Mentorship Program (CSRMP)",
        "programme_type":     "Research Mentorship",
        "description":        "Connects students from historically marginalized groups with Google researchers for CS research mentorship.",
        "duration":           "6 months",
        "mode":               "Online / Virtual",
        "eligibility":        "UG/PG students in CS or related fields from underrepresented groups",
        "branch_required":    "Computer Science",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Stipend + Google research exposure",
        "deadline":           "Check research.google/csrmp",
        "apply_link":         "https://research.google/outreach/csrmp/",
        "how_to_apply":       "Go to research.google/outreach/csrmp → Click 'Apply' during open application window → Fill the student application form.",
    },
    {
        "company":            "Google",
        "programme_name":     "Google Developer Student Clubs (GDSC) Mentorship",
        "programme_type":     "Community Mentorship",
        "description":        "Campus-based mentorship through Google-supported student clubs; workshops, projects, and networking.",
        "duration":           "Academic year",
        "mode":               "Hybrid",
        "eligibility":        "All students at participating colleges",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Certifications, Google resources",
        "deadline":           "Check gdsc.community",
        "apply_link":         "https://gdsc.community.dev/",
        "how_to_apply":       "Go to gdsc.community.dev → Search for your college → Click 'Join Club' or contact your campus GDSC lead.",
    },
    # ── Microsoft ─────────────────────────────────────────────────────────
    {
        "company":            "Microsoft",
        "programme_name":     "Microsoft Research Asia Fellowship",
        "programme_name":     "Microsoft Mentorship / Aspire Program",
        "programme_type":     "Career Mentorship",
        "description":        "Mentorship programme for new graduates and interns pairing them with senior Microsoft employees.",
        "duration":           "12 weeks (internship period)",
        "mode":               "Hybrid",
        "eligibility":        "Pre-final year STEM students",
        "branch_required":    "Computer Science, Information Technology, Electronics",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Part of internship compensation",
        "deadline":           "Check careers.microsoft.com",
        "apply_link":         "https://careers.microsoft.com/v2/global/en/universityinternship",
        "how_to_apply":       "Go to careers.microsoft.com → Click 'Students' → Select 'University Internship' → Search open roles → Apply. Mentorship is embedded in the internship.",
    },
    {
        "company":            "Microsoft",
        "programme_name":     "Microsoft Research PhD Fellowship",
        "programme_type":     "Research Fellowship + Mentorship",
        "description":        "Fellowship for PhD students with mentorship from Microsoft Research scientists.",
        "duration":           "1–2 years",
        "mode":               "Hybrid",
        "eligibility":        "PhD students in CS, AI, or related fields",
        "branch_required":    "Computer Science, Data Science, Mathematics",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Fellowship funding + research stipend",
        "deadline":           "Check microsoft.com/research",
        "apply_link":         "https://www.microsoft.com/en-us/research/academic-program/phd-fellowship/",
        "how_to_apply":       "Go to microsoft.com/research → Academic Programs → PhD Fellowship → Click Apply → Submit research proposal and CV.",
    },
    # ── Amazon ────────────────────────────────────────────────────────────
    {
        "company":            "Amazon",
        "programme_name":     "AWS AI & ML Scholars Mentorship",
        "programme_type":     "Learning + Mentorship",
        "description":        "Free AI/ML learning programme with mentorship from AWS experts. Aims to sponsor 100,000 learners.",
        "duration":           "Self-paced",
        "mode":               "Online / Virtual",
        "eligibility":        "18+ years, no prior AI/ML experience required",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Free AWS certifications",
        "deadline":           "June 24, 2026",
        "apply_link":         "https://aws.amazon.com/about-aws/our-impact/scholars/",
        "how_to_apply":       "Go to aws.amazon.com/scholars → Click 'Apply Now' → Create AWS account → Fill application form → Enroll in AWS Skill Builder courses.",
    },
    {
        "company":            "Amazon",
        "programme_name":     "Amazon Future Engineer Mentorship",
        "programme_type":     "Career Mentorship",
        "description":        "Amazon's student outreach programme providing mentorship, scholarships, and internship pipeline.",
        "duration":           "Academic year",
        "mode":               "Online / Virtual",
        "eligibility":        "High school and college students in CS",
        "branch_required":    "Computer Science",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Scholarships + internship pathway",
        "deadline":           "Check amazonfutureengineer.com",
        "apply_link":         "https://www.amazonfutureengineer.com/",
        "how_to_apply":       "Go to amazonfutureengineer.com → Click 'Explore Programs' → Select scholarship or mentorship track → Apply through the form.",
    },
    # ── Apple ─────────────────────────────────────────────────────────────
    {
        "company":            "Apple",
        "programme_name":     "Apple Next-Gen Innovators Mentorship",
        "programme_type":     "Technical Mentorship",
        "description":        "One-on-one mentorship pairing engineering students with Apple engineers for 8 months.",
        "duration":           "8 months",
        "mode":               "Hybrid",
        "eligibility":        "Engineering students at selected universities",
        "branch_required":    "Electronics, Computer Science, Mechanical",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Industry exposure, career guidance",
        "deadline":           "Check apple.com/careers",
        "apply_link":         "https://www.apple.com/careers/us/students.html",
        "how_to_apply":       "Go to apple.com/careers → Click 'Students' → Search 'mentorship' or 'intern' → Apply to relevant programmes. Next-Gen Innovators is invite-only via selected universities.",
    },
    # ── Meta ──────────────────────────────────────────────────────────────
    {
        "company":            "Meta",
        "programme_name":     "Meta University (Mentorship for Underrepresented Students)",
        "programme_type":     "Mentorship + Internship",
        "description":        "Paid internship with embedded mentorship for first and second year underrepresented students in tech.",
        "duration":           "12 weeks",
        "mode":               "Hybrid",
        "eligibility":        "1st/2nd year underrepresented students in CS",
        "branch_required":    "Computer Science",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Competitive internship stipend",
        "deadline":           "Check metacareers.com",
        "apply_link":         "https://www.metacareers.com/careerprograms/pathways/metauniversity",
        "how_to_apply":       "Go to metacareers.com/careerprograms/pathways/metauniversity → Click 'Apply' → Create Meta Careers account → Submit application with resume.",
    },
    # ── Adobe ─────────────────────────────────────────────────────────────
    {
        "company":            "Adobe",
        "programme_name":     "Adobe Research Women-in-Technology Scholarship",
        "programme_type":     "Scholarship + Mentorship",
        "description":        "Scholarship and mentorship programme for women pursuing degrees in CS or related fields.",
        "duration":           "1 year",
        "mode":               "Hybrid",
        "eligibility":        "Female students in CS or related fields",
        "branch_required":    "Computer Science, Data Science",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"USD 10,000 scholarship + Adobe mentorship",
        "deadline":           "Check adobe.com/careers",
        "apply_link":         "https://research.adobe.com/scholarship/",
        "how_to_apply":       "Go to research.adobe.com/scholarship → Read eligibility → Click 'Apply' → Submit application with transcript and recommendation letter.",
    },
    {
        "company":            "Adobe",
        "programme_name":     "SheCodes by Adobe Mentorship",
        "programme_type":     "Women in Tech Mentorship",
        "description":        "Female-specific mentorship and coding programme supporting women in technology careers.",
        "duration":           "3–6 months",
        "mode":               "Online / Virtual",
        "eligibility":        "Female students in technical programs",
        "branch_required":    "Computer Science, Information Technology",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"Adobe certification + career support",
        "deadline":           "Check Adobe Careers for current cycle",
        "apply_link":         "https://careers.adobe.com/us/en/search-results?keywords=shecodes",
        "how_to_apply":       "Go to careers.adobe.com → Search 'SheCodes' → Click on the listing → Create Adobe Careers account → Apply with resume.",
    },
    # ── Goldman Sachs ─────────────────────────────────────────────────────
    {
        "company":            "Goldman Sachs",
        "programme_name":     "Goldman Sachs Catalyst Programme (India)",
        "programme_type":     "Women Mentorship",
        "description":        "3-month virtual mentoring for women students from low-income communities. Partners with Empower Ananya & Katalyst NGOs.",
        "duration":           "3 months",
        "mode":               "Online / Virtual",
        "eligibility":        "Women undergraduates from low-income communities in India",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"Professional skill development + GS internship pathway",
        "deadline":           "Check goldmansachs.com/india/catalyst",
        "apply_link":         "https://www.goldmansachs.com/worldwide/india/careers/catalyst-program",
        "how_to_apply":       "Go to goldmansachs.com/worldwide/india/careers/catalyst-program → Click 'Apply' → Applications sourced via Empower Ananya & Katalyst NGOs — contact them directly if no open form.",
    },
    {
        "company":            "Goldman Sachs",
        "programme_name":     "Goldman Sachs Emerging Leaders Series",
        "programme_type":     "Leadership Mentorship",
        "description":        "Technical training + mentorship + transparency into GS recruitment for 2nd year undergraduates.",
        "duration":           "Programme duration varies",
        "mode":               "Hybrid",
        "eligibility":        "2nd year undergraduate students",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Mentorship + fast-track to GS internship",
        "deadline":           "Check goldmansachs.com/careers/students",
        "apply_link":         "https://www.goldmansachs.com/careers/students/programs-and-internships",
        "how_to_apply":       "Go to goldmansachs.com/careers/students → Click 'Programs & Internships' → Select 'Emerging Leaders' or 'India Programs' → Apply during open window.",
    },
    # ── JP Morgan ─────────────────────────────────────────────────────────
    {
        "company":            "J.P. Morgan Chase",
        "programme_name":     "JPMorgan Chase Code for Good Mentorship",
        "programme_type":     "Tech Mentorship",
        "description":        "Mentorship embedded in Code for Good hackathon — students work with JPM technologists on social impact tech.",
        "duration":           "24 hours + follow-up",
        "mode":               "In-Person",
        "eligibility":        "Pre-final year CS/IT students",
        "branch_required":    "Computer Science, Information Technology",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Internship pipeline + mentorship from JPM engineers",
        "deadline":           "Check careers.jpmorgan.com",
        "apply_link":         "https://careers.jpmorgan.com/global/en/students/programs/code-for-good",
        "how_to_apply":       "Go to careers.jpmorgan.com/global/en/students/programs/code-for-good → Click 'Apply' → Create JPM Careers account → Submit application.",
    },
    {
        "company":            "J.P. Morgan Chase",
        "programme_name":     "JPMorgan Winning Women Programme",
        "programme_type":     "Women Leadership Mentorship",
        "description":        "Mentorship + networking programme for women students to explore careers in finance and technology.",
        "duration":           "2 days",
        "mode":               "In-Person",
        "eligibility":        "Female penultimate year students",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"Mentorship + internship fast-track",
        "deadline":           "Check careers.jpmorgan.com",
        "apply_link":         "https://careers.jpmorgan.com/global/en/students/programs",
        "how_to_apply":       "Go to careers.jpmorgan.com/global/en/students/programs → Find 'Winning Women' → Click Apply → Create account and submit application form.",
    },
    # ── McKinsey ──────────────────────────────────────────────────────────
    {
        "company":            "McKinsey & Company",
        "programme_name":     "McKinsey Next Generation Women Leaders",
        "programme_type":     "Women Leadership Mentorship",
        "description":        "Immersive mentorship and leadership development programme for undergraduate women.",
        "duration":           "2–3 days",
        "mode":               "In-Person",
        "eligibility":        "Female penultimate year undergraduates",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"Travel + accommodation covered, internship pathway",
        "deadline":           "Check mckinsey.com/careers",
        "apply_link":         "https://www.mckinsey.com/careers/students",
    },
    {
        "company":            "McKinsey & Company",
        "programme_name":     "McKinsey Freshman Leadership Program",
        "programme_type":     "Leadership Mentorship",
        "description":        "Mentorship programme for first-year students to explore consulting careers at McKinsey.",
        "duration":           "2 days",
        "mode":               "In-Person",
        "eligibility":        "1st year undergraduate students",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Travel + accommodation, McKinsey network access",
        "deadline":           "Check mckinsey.com/careers",
        "apply_link":         "https://www.mckinsey.com/careers/students",
    },
    # ── BCG ───────────────────────────────────────────────────────────────
    {
        "company":            "BCG (Boston Consulting Group)",
        "programme_name":     "BCG Platinion Mentorship / Advance Programme",
        "programme_type":     "Career Mentorship",
        "description":        "Mentorship embedded in BCG's tech consulting division for students interested in tech-driven consulting.",
        "duration":           "Programme varies",
        "mode":               "Hybrid",
        "eligibility":        "Penultimate year students",
        "branch_required":    "Computer Science, Management, All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"BCG network + consulting exposure",
        "deadline":           "Check careers.bcg.com",
        "apply_link":         "https://careers.bcg.com/students",
        "how_to_apply":       "Go to careers.bcg.com/students → Click 'Explore roles' → Filter by 'Internship' or 'Fellowship' → Select India region → Apply. Mentorship is embedded in the programme.",
    },
    # ── Morgan Stanley ────────────────────────────────────────────────────
    {
        "company":            "Morgan Stanley",
        "programme_name":     "Morgan Stanley Early Careers Mentorship (India)",
        "programme_type":     "Finance Career Mentorship",
        "description":        "Mentorship for students interested in technology and finance roles at Morgan Stanley India offices.",
        "duration":           "As part of internship programme",
        "mode":               "In-Person / Hybrid",
        "eligibility":        "Penultimate year students in Bengaluru/Mumbai",
        "branch_required":    "Computer Science, Finance, Mathematics",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Part of internship stipend",
        "deadline":           "Check morganstanley.com/people-opportunities",
        "apply_link":         "https://www.morganstanley.com/people-opportunities/students-graduates",
        "how_to_apply":       "Go to morganstanley.com/people-opportunities/students-graduates → Click 'Asia Pacific' → Select India programmes → Apply with resume and cover letter.",
    },
    # ── NXP ───────────────────────────────────────────────────────────────
    {
        "company":            "NXP Semiconductors",
        "programme_name":     "NXP Women in Technology (WIT) Mentorship",
        "programme_type":     "Women in Tech Mentorship",
        "description":        "Mentorship programme specifically for women in electronics/CS fields with NXP engineers as mentors.",
        "duration":           "As part of internship",
        "mode":               "Hybrid",
        "eligibility":        "Female students in ECE, CS, Electrical",
        "branch_required":    "Electronics, Computer Science, Electrical",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"Mentorship + internship pathway at NXP India",
        "deadline":           "Check nxp.com/careers",
        "apply_link":         "https://www.nxp.com/company/about-nxp/careers/students-and-recent-graduates:STUDENTS-GRADUATES",
        "how_to_apply":       "Go to nxp.com/careers → Click 'Students & Graduates' → Search for WIT/Women in Technology roles in India → Apply online.",
    },
    # ── D.E. Shaw ─────────────────────────────────────────────────────────
    {
        "company":            "D.E. Shaw",
        "programme_name":     "D.E. Shaw Ascend (Women STEM Mentorship)",
        "programme_type":     "Women STEM Mentorship",
        "description":        "Mentorship + internship pipeline for women in STEM. One of India's most prestigious female-specific tech programmes.",
        "duration":           "Summer (as part of internship)",
        "mode":               "In-Person",
        "eligibility":        "Female students in CS, Maths, Statistics at top engineering colleges",
        "branch_required":    "Computer Science, Mathematics, Statistics",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"Competitive stipend + D.E. Shaw PPO opportunity",
        "deadline":           "Check deshawindia.com",
        "apply_link":         "https://www.deshawindia.com/forms/NFS.aspx",
        "how_to_apply":       "Go to deshawindia.com → Click 'Ascend' programme → Fill the online application form with college, branch, CGPA details → Submit.",
    },
    # ── Nestlé ────────────────────────────────────────────────────────────
    {
        "company":            "Nestlé India",
        "programme_name":     "Nestlé Nesternship Mentorship",
        "programme_type":     "Industry Mentorship",
        "description":        "Summer internship with embedded mentorship from Nestlé leaders. Students work on real business projects.",
        "duration":           "2 months",
        "mode":               "In-Person",
        "eligibility":        "MBA / PG students",
        "branch_required":    "MBA, Management, Food Technology",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Stipend + Nestlé network access",
        "deadline":           "Check nestle.in/jobs",
        "apply_link":         "https://www.nestle.in/jobs/nesternship",
        "how_to_apply":       "Go to nestle.in/jobs/nesternship → Click 'Apply' → Create profile → Upload resume → Submit application during open cycle (usually Jan-March).",
    },
    # ── Bosch ─────────────────────────────────────────────────────────────
    {
        "company":            "Bosch India",
        "programme_name":     "Bosch Tech Compass Mentorship",
        "programme_type":     "Technical Mentorship",
        "description":        "Mentorship programme for engineering students working with Bosch engineers on real projects.",
        "duration":           "As part of internship (3–6 months)",
        "mode":               "In-Person",
        "eligibility":        "Engineering students in ECE, Mechanical, CS",
        "branch_required":    "Electronics, Mechanical, Computer Science",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Stipend + certification",
        "deadline":           "Check bosch.in/careers",
        "apply_link":         "https://www.bosch.in/careers/your-entry-into-bosch/internships/",
        "how_to_apply":       "Go to bosch.in/careers → Click 'Your Entry into Bosch' → 'Internships' → Click 'Find your internship' → Filter by India → Apply with resume.",
    },
    # ── Siemens ───────────────────────────────────────────────────────────
    {
        "company":            "Siemens India",
        "programme_name":     "Siemens Student Mentorship Programme",
        "programme_type":     "Technical Mentorship",
        "description":        "Mentorship for engineering students embedded in Siemens India internship programme.",
        "duration":           "3–6 months",
        "mode":               "In-Person",
        "eligibility":        "Engineering students in ECE, Electrical, CS, Mechanical",
        "branch_required":    "Electronics, Electrical, Computer Science, Mechanical",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Stipend + Siemens industry exposure",
        "deadline":           "Check jobs.siemens.com",
        "apply_link":         "https://jobs.siemens.com/careers?query=intern&domain=siemens.com",
        "how_to_apply":       "Go to jobs.siemens.com → Search 'intern' → Filter Country = India → Click on listing → Create Siemens account → Apply.",
    },
    # ── L&T ───────────────────────────────────────────────────────────────
    {
        "company":            "Larsen & Toubro (L&T)",
        "programme_name":     "L&T Build India Scholarship cum Mentorship",
        "programme_type":     "Scholarship + Mentorship",
        "description":        "Scholarship and mentorship for engineering students from economically weaker sections.",
        "duration":           "Academic year",
        "mode":               "Hybrid",
        "eligibility":        "B.E./B.Tech students from EWS backgrounds",
        "branch_required":    "Civil, Mechanical, Electrical, Electronics",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Scholarship + L&T mentorship",
        "deadline":           "Check larsentoubro.com",
        "apply_link":         "https://www.larsentoubro.com/corporate/career/campus-recruitment/",
        "how_to_apply":       "Go to larsentoubro.com/corporate/career/campus-recruitment → Look for 'Build India Scholarship' → Click Apply → Submit academic documents.",
    },
    # ── ISRO ──────────────────────────────────────────────────────────────
    {
        "company":            "ISRO",
        "programme_name":     "ISRO Yuva Vigyan Vaigyanik (YUVIKA) Programme",
        "programme_type":     "Research Mentorship",
        "description":        "Annual 2-week residential programme for Class 9 students — hands-on mentorship by ISRO scientists.",
        "duration":           "2 weeks",
        "mode":               "In-Person",
        "eligibility":        "Class 9 students (school level)",
        "branch_required":    "Science",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Free residential programme",
        "deadline":           "Check isro.gov.in",
        "apply_link":         "https://www.isro.gov.in/Students.html",
        "how_to_apply":       "Go to isro.gov.in/Students.html → Click 'YUVIKA' → Register on the YUVIKA portal during open window (usually Jan-Feb) → Submit application with school documents.",
    },
    {
        "company":            "ISRO",
        "programme_name":     "ISRO Student Project Trainee Mentorship",
        "programme_type":     "Research Mentorship",
        "description":        "Students work under ISRO scientists on live projects. Direct mentorship from space scientists.",
        "duration":           "45 days minimum",
        "mode":               "In-Person",
        "eligibility":        "B.E./B.Tech 6th semester or above; min 60% / 6.32 CGPA",
        "branch_required":    "Electronics, Computer Science, Mechanical, Electrical",
        "cgpa_required":      "6.32",
        "gender":             "All",
        "stipend_or_benefits":"Certificate from ISRO + research experience",
        "deadline":           "Check individual ISRO centre websites",
        "apply_link":         "https://www.isro.gov.in/InternshipAndProjects.html",
        "how_to_apply":       "Go to isro.gov.in/InternshipAndProjects.html → Read eligibility → Visit individual ISRO centre websites (VSSC, SAC, URSC etc.) → Apply directly to centre with college NOC + resume.",
    },
    # ── DRDO ──────────────────────────────────────────────────────────────
    {
        "company":            "DRDO",
        "programme_name":     "DRDO Research Mentorship / Apprenticeship",
        "programme_type":     "Defence Research Mentorship",
        "description":        "Students work under DRDO scientists on defence research projects. Mentorship from senior researchers.",
        "duration":           "1–6 months",
        "mode":               "In-Person",
        "eligibility":        "UG/PG students in Engineering or Science",
        "branch_required":    "Electronics, Computer Science, Mechanical, Electrical, Chemical",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Certificate + defence research exposure",
        "deadline":           "Check drdo.gov.in",
        "apply_link":         "https://www.drdo.gov.in/internship-scheme",
        "how_to_apply":       "Go to drdo.gov.in/internship-scheme → Read eligibility → Contact specific DRDO lab directly with application + college NOC + resume. No central portal — apply to labs individually.",
    },
    # ── NITI Aayog ────────────────────────────────────────────────────────
    {
        "company":            "NITI Aayog",
        "programme_name":     "NITI Aayog Young Professional Mentorship",
        "programme_type":     "Policy Mentorship",
        "description":        "Policy mentorship where students work with NITI Aayog officers on national development projects.",
        "duration":           "2–6 months",
        "mode":               "In-Person / Hybrid",
        "eligibility":        "UG/PG/PhD students from recognized institutions",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Stipend + NITI Aayog certificate",
        "deadline":           "Check niti.gov.in",
        "apply_link":         "https://www.niti.gov.in/internship",
        "how_to_apply":       "Go to niti.gov.in/internship → Click 'Apply' → Fill the online form with academic details → Upload resume and NOC → Submit during open window.",
    },
    # ── RBI ───────────────────────────────────────────────────────────────
    {
        "company":            "Reserve Bank of India (RBI)",
        "programme_name":     "RBI Young Scholars Mentorship",
        "programme_type":     "Finance Mentorship",
        "description":        "Mentorship embedded in RBI Summer Internship — students learn monetary policy and financial systems directly.",
        "duration":           "2 months",
        "mode":               "In-Person",
        "eligibility":        "Undergraduate students in Economics, Finance, Statistics",
        "branch_required":    "Finance, Economics, Mathematics, Statistics",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Stipend + RBI experience certificate",
        "deadline":           "Check opportunities.rbi.org.in",
        "apply_link":         "https://opportunities.rbi.org.in/Scripts/Internships.aspx",
        "how_to_apply":       "Go to opportunities.rbi.org.in/Scripts/Internships.aspx → Click 'Apply Online' → Register with email → Fill application form → Upload documents → Submit.",
    },
    # ── AICTE ─────────────────────────────────────────────────────────────
    {
        "company":            "AICTE",
        "programme_name":     "AICTE Mentor-Mentee Scheme (Margdarshan)",
        "programme_type":     "Institutional Mentorship",
        "description":        "AICTE scheme pairing weaker engineering institutions with mentor institutions for academic improvement.",
        "duration":           "Ongoing",
        "mode":               "Hybrid",
        "eligibility":        "Students from AICTE-approved institutions",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Institutional resources, industry exposure",
        "deadline":           "Check aicte-india.org",
        "apply_link":         "https://www.aicte-india.org/",
        "how_to_apply":       "Go to aicte-india.org → Search 'Margdarshan' or 'Mentor Scheme' → Your institution registers — individual student access via college TPO.",
    },
    {
        "company":            "AICTE",
        "programme_name":     "Pragati Scholarship cum Mentorship (Girls)",
        "programme_type":     "Women Scholarship + Mentorship",
        "description":        "Scholarship and mentorship for female students in technical education from economically weaker families.",
        "duration":           "Academic year",
        "mode":               "Hybrid",
        "eligibility":        "Female students in AICTE-approved technical programs from EWS",
        "branch_required":    "All technical branches",
        "cgpa_required":      "Not mentioned",
        "gender":             "Girls Only / Women",
        "stipend_or_benefits":"INR 50,000/year scholarship",
        "deadline":           "Check aicte-india.org/pragati",
        "apply_link":         "https://www.aicte-india.org/bureaus/rifd/pragati",
        "how_to_apply":       "Go to aicte-india.org/bureaus/rifd/pragati → Click 'Apply' → Register as student → Fill income/academic details → Submit before deadline (usually Sep-Oct).",
    },
    # ── Unstop Mentorship ─────────────────────────────────────────────────
    {
        "company":            "Unstop",
        "programme_name":     "Unstop Mentorship Platform",
        "programme_type":     "Career Mentorship Platform",
        "description":        "Platform connecting students with industry mentors across tech, finance, consulting, and more.",
        "duration":           "Session-based",
        "mode":               "Online / Virtual",
        "eligibility":        "All students registered on Unstop",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Free / paid sessions",
        "deadline":           "Open year-round",
        "apply_link":         "https://unstop.com/mentorship",
        "how_to_apply":       "Go to unstop.com/mentorship → Browse mentors by domain → Click 'Book Session' → Register/Login → Schedule a session.",
    },
    # ── Internshala Mentorship ────────────────────────────────────────────
    {
        "company":            "Internshala",
        "programme_name":     "Internshala Trainings + Mentorship",
        "programme_type":     "Skill + Career Mentorship",
        "description":        "Online training programmes with mentorship from industry professionals in tech, marketing, and more.",
        "duration":           "4–8 weeks per course",
        "mode":               "Online / Virtual",
        "eligibility":        "All students",
        "branch_required":    "All",
        "cgpa_required":      "Not mentioned",
        "gender":             "All",
        "stipend_or_benefits":"Placement assistance + certificate",
        "deadline":           "Open year-round",
        "apply_link":         "https://trainings.internshala.com/",
        "how_to_apply":       "Go to trainings.internshala.com → Browse courses with mentorship → Click 'Enroll Now' → Register/Login → Pay fee (if any) → Start learning with mentor support.",
    },
]

# Additional companies discovered via enhanced internship scrape.
# These are included as mentorship placeholders so they appear in the
# mentorship dataset and can be reviewed/expanded with exact programmes later.
EXTRA_MENTORSHIP_COMPANIES = [
    "Aditya Birla Fashion and Retail (ABFRL)",
    "Affle",
    "AlphaGrep Securities",
    "Anita Dongre",
    "Citadel Securities",
    "D. E. Shaw India",
    "Dharma Productions",
    "Excel Entertainment",
    "Fabindia",
    "Fractal Analytics",
    "Global Captives (GCCs – General)",
    "Graviton Research Capital",
    "HCLTech",
    "Hombale Films",
    "India Today Group",
    "Infosys",
    "Jane Street",
    "Krutrim (Ola AI)",
    "LTIMindtree",
    "Manish Malhotra",
    "NDTV",
    "Network18",
    "Persistent Systems",
    "Quadeye",
    "Red Chillies Entertainment",
    "Reliance Entertainment",
    "Reliance Retail (Fashion & Lifestyle)",
    "Sabyasachi Mukherjee",
    "Sarvam AI",
    "Tata Consultancy Services (TCS)",
    "Tata Elxsi",
    "The Hindu Group",
    "The Indian Express Group",
    "The Times Group",
    "Tower Research Capital",
    "Wipro",
    "WorldQuant",
    "Yash Raj Films (YRF)",
]


def build_placeholder_programmes() -> list[dict]:
    existing = {p.get("company", "").strip().lower() for p in CURATED_PROGRAMMES}
    placeholders = []

    for company in EXTRA_MENTORSHIP_COMPANIES:
        if company.strip().lower() in existing:
            continue

        query = quote_plus(f"{company} mentorship program careers internship")
        placeholders.append({
            "company":            company,
            "programme_name":     f"{company} Student Mentorship / Early Career Programmes",
            "programme_type":     "Mentorship / Early Career",
            "description":        "Consolidated placeholder entry auto-added from internship company expansion. Verify current mentorship, fellowship, or guided early-career tracks on the official careers page.",
            "duration":           "Not mentioned",
            "mode":               "Not mentioned",
            "eligibility":        "Check official careers page",
            "branch_required":    "All",
            "cgpa_required":      "Not mentioned",
            "gender":             "All",
            "stipend_or_benefits": "Not mentioned",
            "deadline":           "Rolling / check official page",
            "apply_link":         f"https://www.google.com/search?q={query}",
            "how_to_apply":       "Open the link, find official careers/university/student programmes for this company, then apply through the official portal.",
        })

    return placeholders


# ══════════════════════════════════════════════════════════════════════════════
#  LIVE SCRAPERS — Semi-static pages that can be scraped without login
# ══════════════════════════════════════════════════════════════════════════════

LIVE_SCRAPE_TARGETS = [
    {
        "company":  "Google",
        "source":   "google",
        "url":      "https://summerofcode.withgoogle.com/",
        "wait_css": "h1, h2, .timeline",
    },
    {
        "company":  "ISRO",
        "source":   "isro",
        "url":      "https://www.isro.gov.in/Students.html",
        "wait_css": "h1, h2, .container",
    },
    {
        "company":  "NITI Aayog",
        "source":   "niti_aayog",
        "url":      "https://www.niti.gov.in/internship",
        "wait_css": "h1, h2, .field-item",
    },
    {
        "company":  "RBI",
        "source":   "rbi",
        "url":      "https://opportunities.rbi.org.in/Scripts/Internships.aspx",
        "wait_css": "h2, h3, td",
    },
]


def scrape_live_page(driver, target: dict, delay: float) -> list[dict]:
    """Scrape a single live page and return records found."""
    records = []
    try:
        html = get_html(driver, target["url"],
                        wait_css=target.get("wait_css", "h1"),
                        delay=delay)
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        # Look for mentorship-related sections
        mentorship_sections = []
        for tag in soup.find_all(["h2", "h3", "h4"]):
            heading = tag.get_text(strip=True)
            if re.search(r"mentor|fellowship|scholar|programme|training", heading, re.I):
                # Grab content below this heading
                content = []
                for sib in tag.find_next_siblings():
                    if sib.name in ["h2", "h3", "h4"]:
                        break
                    content.append(sib.get_text(" ", strip=True))
                mentorship_sections.append({
                    "heading": heading,
                    "content": " ".join(content)[:500],
                })

        if mentorship_sections:
            for section in mentorship_sections[:5]:  # max 5 per page
                rec = empty_record(target["source"], target["company"])
                rec["programme_name"]     = section["heading"]
                rec["description"]        = section["content"][:300]
                rec["duration"]           = extract_duration(section["content"])
                rec["mode"]               = extract_mode(section["content"])
                rec["eligibility"]        = "Check official page"
                rec["branch_required"]    = extract_branch(section["content"])
                rec["cgpa_required"]      = extract_cgpa(section["content"])
                rec["gender"]             = extract_gender(section["content"], section["heading"])
                rec["apply_link"]         = target["url"]
                records.append(rec)
        else:
            # No mentorship sections found — create a generic entry
            rec = empty_record(target["source"], target["company"])
            rec["programme_name"] = f"{target['company']} Student Programmes"
            rec["description"]    = text[:300]
            rec["apply_link"]     = target["url"]
            rec["mode"]           = extract_mode(text)
            records.append(rec)

    except Exception as e:
        print(f"    [Live scrape error] {target['company']}: {e}")

    return records


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN SCRAPE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def scrape_mentorship(sources: list[str], pages: int, keyword: str,
                      headless: bool, delay: float) -> list[dict]:
    """
    Scrape mentorship programmes for given sources.
    Returns a list of record dicts.
    """
    print(f"\n{'='*62}")
    print(f"  Mentorship Scraper")
    print(f"  Sources : {', '.join(sources)}")
    print(f"  Keyword : '{keyword or 'all'}'")
    print(f"{'='*62}\n")

    kw = keyword.lower() if keyword else ""
    records = []

    # ── Step 1: Load matching curated entries ─────────────────────────────
    print("  Loading curated programme database...")
    curated_count = 0
    all_programmes = CURATED_PROGRAMMES + build_placeholder_programmes()
    for prog in all_programmes:
        source_key = prog.get("company", "").lower().replace(" ", "_").replace(".", "").replace("(", "").replace(")", "").replace("&", "")

        # Match source
        source_match = any(
            src in source_key or source_key.startswith(src)
            for src in sources
        ) or "all" in sources

        if not source_match:
            continue

        # Keyword filter
        if kw:
            searchable = " ".join([
                prog.get("programme_name", ""),
                prog.get("company", ""),
                prog.get("description", ""),
                prog.get("branch_required", ""),
                prog.get("programme_type", ""),
            ]).lower()
            if kw not in searchable:
                continue

        rec = empty_record(source_key, prog.get("company", "N/A"))
        rec.update({k: v for k, v in prog.items()
                    if k in FINAL_COLS or k in ("company", "apply_link")})
        records.append(rec)
        curated_count += 1

    print(f"  Loaded {curated_count} curated mentorship entries")

    # ── Step 2: Live scrape matching targets ──────────────────────────────
    live_targets = [
        t for t in LIVE_SCRAPE_TARGETS
        if any(src in t["source"] or t["source"].startswith(src)
               for src in sources) or "all" in sources
    ]

    if live_targets:
        print(f"\n  Live scraping {len(live_targets)} pages...")
        driver = make_driver(headless=headless)
        try:
            for target in live_targets:
                print(f"  [Live] {target['company']:<25}", end=" ", flush=True)
                live_recs = scrape_live_page(driver, target, delay)
                records.extend(live_recs)
                print(f"found {len(live_recs)} section(s)")
                time.sleep(delay * 0.5)
        finally:
            driver.quit()

    # ── Step 3: Print results ─────────────────────────────────────────────
    print(f"\n  Total mentorship records: {len(records)}\n")
    for i, rec in enumerate(records, 1):
        print_record(i, len(records), rec)

    return records


# ══════════════════════════════════════════════════════════════════════════════
#  SAVE — JSON + CSV (same pattern as internship scraper)
# ══════════════════════════════════════════════════════════════════════════════

def save(records: list[dict], output_base: str):
    if not records:
        print("\n  No data to save."); return

    df = pd.DataFrame(records)
    df.drop_duplicates(subset=["apply_link", "programme_name"], inplace=True)
    df = df[[c for c in FINAL_COLS if c in df.columns]]
    df = df.where(pd.notna(df), None)

    scraped_at    = datetime.now().isoformat(timespec="seconds")
    programmes    = df.to_dict(orient="records")

    json_path = output_base + ".json"
    csv_path  = output_base + ".csv"

    payload = {
        "scraped_at":   scraped_at,
        "total":        len(programmes),
        "companies":    sorted(df["company"].dropna().unique().tolist()),
        "mentorship_programmes": programmes,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # Copy to latest files
    import shutil
    shutil.copy(json_path, LATEST_JSON)
    shutil.copy(csv_path,  LATEST_JSON.replace(".json", ".csv"))

    print(f"\n{'='*62}")
    print(f"  Saved {len(df)} mentorship programmes")
    print(f"  📄 JSON  → {json_path}")
    print(f"  📊 CSV   → {csv_path}")
    print(f"  📌 Latest → {LATEST_JSON}")

    # Girls Only summary
    girls = df[df["gender"].str.contains("Girls Only", na=False)]
    print(f"\n  Female-specific programmes : {len(girls)}")
    if not girls.empty:
        for _, row in girls.iterrows():
            print(f"    • {row['company']:<25} {row['programme_name']}")
    print(f"{'='*62}")


# ══════════════════════════════════════════════════════════════════════════════
#  TIER-BASED SCHEDULER (mirrors internship scraper exactly)
# ══════════════════════════════════════════════════════════════════════════════

def _merge_and_save():
    with _store_lock:
        all_records = []
        for tier_records in _data_store.values():
            all_records.extend(tier_records)

    if not all_records:
        return

    seen, unique = set(), []
    for r in all_records:
        key = r.get("apply_link", "") + "|" + r.get("programme_name", "")
        if key and key not in seen:
            seen.add(key); unique.append(r)

    payload = {
        "scraped_at":   datetime.now().isoformat(timespec="seconds"),
        "total":        len(unique),
        "companies":    sorted({r.get("company", "") for r in unique}),
        "tier_summary": {
            f"tier_{t}": {
                "sources":        TIERS[t]["sources"],
                "interval_hours": TIERS[t]["interval"],
                "count":          len(_data_store[t]),
            }
            for t in TIERS
        },
        "mentorship_programmes": unique,
    }

    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"  💾 Merged {len(unique)} mentorship programmes → {LATEST_JSON}")


def _run_tier(tier_num, pages, keyword, headless, delay):
    tier    = TIERS[tier_num]
    icon    = tier["color"]
    name    = tier["name"]
    sources = tier["sources"]

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{icon} [{ts}] {name} — scraping: {', '.join(sources)}")

    try:
        results = scrape_mentorship(
            sources=sources,
            pages=pages,
            keyword=keyword,
            headless=headless,
            delay=delay,
        )

        with _store_lock:
            _data_store[tier_num] = results

        os.makedirs("archive", exist_ok=True)
        archive_base = f"archive/tier{tier_num}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        save(results, archive_base)
        _merge_and_save()

        ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{icon} [{ts2}] {name} done — "
              f"{len(results)} programmes. Next in {tier['interval']}h.")

    except Exception as e:
        print(f"{icon} [ERROR] {name} failed: {e}")


def _tier_loop(tier_num, pages, keyword, headless, delay):
    interval_sec = TIERS[tier_num]["interval"] * 3600
    while not _stop_event.is_set():
        _run_tier(tier_num, pages, keyword, headless, delay)
        _stop_event.wait(timeout=interval_sec)
    print(f"  {TIERS[tier_num]['color']} {TIERS[tier_num]['name']} stopped.")


def signal_handler(sig, frame):
    print("\n\n  Ctrl+C — stopping all tiers gracefully...")
    _stop_event.set()
    sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Mentorship programme scraper — tier-based auto-refresh",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tier Schedule:
  Tier 1 (every  6h): Google, Microsoft, Amazon, Apple, Meta, Adobe,
                       Goldman Sachs, JP Morgan, McKinsey, BCG,
                       Morgan Stanley, NXP, D.E. Shaw, Nestlé
  Tier 2 (every 12h): Bosch, Siemens, L&T, Unstop, Internshala
  Tier 3 (every 24h): ISRO, DRDO, NITI Aayog, RBI, AICTE

Examples:
  python mentorship_scraper.py                    # all tiers, auto-refresh
  python mentorship_scraper.py --once             # run once, all tiers
  python mentorship_scraper.py --tiers 1          # only tier 1
  python mentorship_scraper.py --keyword "women"  # filter by keyword
  python mentorship_scraper.py --t1 4 --t2 8 --t3 16
  python mentorship_scraper.py --once --no-headless
        """
    )
    p.add_argument("--tiers",       type=str,   default="1,2,3")
    p.add_argument("--pages",       type=int,   default=2)
    p.add_argument("--keyword",     type=str,   default="")
    p.add_argument("--delay",       type=float, default=2.5)
    p.add_argument("--t1",          type=float, default=6.0,
                   help="Tier 1 interval hours (default: 6)")
    p.add_argument("--t2",          type=float, default=12.0,
                   help="Tier 2 interval hours (default: 12)")
    p.add_argument("--t3",          type=float, default=24.0,
                   help="Tier 3 interval hours (default: 24)")
    p.add_argument("--once",        action="store_true",
                   help="Run all tiers once and exit")
    p.add_argument("--no-headless", action="store_true",
                   help="Show browser window")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    TIERS[1]["interval"] = args.t1
    TIERS[2]["interval"] = args.t2
    TIERS[3]["interval"] = args.t3

    active_tiers = [int(t.strip()) for t in args.tiers.split(",") if t.strip().isdigit()]

    common = dict(
        pages=args.pages,
        keyword=args.keyword,
        headless=not args.no_headless,
        delay=args.delay,
    )

    signal.signal(signal.SIGINT, signal_handler)
    os.makedirs("archive", exist_ok=True)

    if args.once:
        print("\n  Running all tiers once (no scheduler)...")
        for t in active_tiers:
            _run_tier(t, **common)
        print(f"\n  Done. Output → {LATEST_JSON}")
    else:
        print(f"""
{"="*62}
  Mentorship Scraper — Tier-Based Auto-Refresh
{"="*62}
  🔴 Tier 1 — every {TIERS[1]["interval"]:>2}h : Big Tech, Finance, Consulting
  🟡 Tier 2 — every {TIERS[2]["interval"]:>2}h : Bosch, Siemens, L&T, Unstop, Internshala
  🟢 Tier 3 — every {TIERS[3]["interval"]:>2}h : ISRO, DRDO, NITI Aayog, RBI, AICTE
{"="*62}
  Active tiers : {active_tiers}
  Output       : {LATEST_JSON}
  Archive      : archive/tierN_YYYYMMDD_HHMM.json
  Stop         : Ctrl+C
{"="*62}
""")

        threads = []
        for t in active_tiers:
            thread = threading.Thread(
                target=_tier_loop,
                kwargs={"tier_num": t, **common},
                name=f"MentorTier-{t}",
                daemon=True,
            )
            thread.start()
            threads.append(thread)
            time.sleep(10)  # stagger starts

        try:
            while any(t.is_alive() for t in threads):
                time.sleep(1)
        except KeyboardInterrupt:
            _stop_event.set()
