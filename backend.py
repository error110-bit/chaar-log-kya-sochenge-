import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request

try:
    from flask_cors import CORS
except ImportError:
    CORS = None


app = Flask(__name__)
if CORS is not None:
    CORS(app)


DATA_FILE = Path(os.getenv("INTERNSHIPS_DATA_FILE", "internships_latest.json"))
MENTORSHIP_FILE = Path(os.getenv("MENTORSHIP_DATA_FILE", "mentorship_latest.json"))
AUTO_RELOAD_ON_FILE_CHANGE = os.getenv("AUTO_RELOAD_ON_FILE_CHANGE", "1").lower() not in {"0", "false", "no"}
DATA = {"scraped_at": None, "total": 0, "sources": [], "internships": []}
MENTORSHIP_DATA = {"scraped_at": None, "total": 0, "companies": [], "mentorship_programmes": []}
DATA_FILE_MTIME = None
MENTORSHIP_FILE_MTIME = None

PROJECT_COMPLIANCE = {
    "uses_preexisting_job_api": False,
    "data_collection_mode": "direct_html_scraping_and_curated_company_links",
    "backend_data_source": {
        "internships": str(DATA_FILE),
        "mentorship": str(MENTORSHIP_FILE),
    },
    "requires_user_login": False,
    "collects_user_credentials": False,
    "authentication_mechanism": "none",
    "project_visibility": "open_source_ready",
}

ALLOWED_SORT_FIELDS = {
    "title",
    "company",
    "source",
    "location",
    "stipend",
    "duration",
    "mode",
    "internship_type",
    "branch_required",
    "cgpa_required",
    "gender",
    "deadline",
}

MENTORSHIP_SORT_FIELDS = {
    "source",
    "company",
    "programme_name",
    "programme_type",
    "duration",
    "mode",
    "branch_required",
    "cgpa_required",
    "gender",
    "deadline",
}


def _safe_float(value):
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {"", "none", "n/a", "not mentioned", "not disclosed"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_data():
    global DATA, DATA_FILE_MTIME
    if not DATA_FILE.exists():
        DATA = {"scraped_at": None, "total": 0, "sources": [], "internships": []}
        DATA_FILE_MTIME = None
        return

    with DATA_FILE.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    internships = payload.get("internships", []) if isinstance(payload, dict) else []
    DATA = {
        "scraped_at": payload.get("scraped_at") if isinstance(payload, dict) else None,
        "total": len(internships),
        "sources": sorted({item.get("source", "Unknown") for item in internships}),
        "internships": internships,
    }
    DATA_FILE_MTIME = DATA_FILE.stat().st_mtime


def load_mentorship_data():
    global MENTORSHIP_DATA, MENTORSHIP_FILE_MTIME
    if not MENTORSHIP_FILE.exists():
        MENTORSHIP_DATA = {
            "scraped_at": None,
            "total": 0,
            "companies": [],
            "mentorship_programmes": [],
        }
        MENTORSHIP_FILE_MTIME = None
        return

    with MENTORSHIP_FILE.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    programmes = payload.get("mentorship_programmes", []) if isinstance(payload, dict) else []
    MENTORSHIP_DATA = {
        "scraped_at": payload.get("scraped_at") if isinstance(payload, dict) else None,
        "total": len(programmes),
        "companies": sorted({item.get("company", "Unknown") for item in programmes}),
        "mentorship_programmes": programmes,
    }
    MENTORSHIP_FILE_MTIME = MENTORSHIP_FILE.stat().st_mtime


def refresh_if_files_changed():
    if not AUTO_RELOAD_ON_FILE_CHANGE:
        return

    if DATA_FILE.exists():
        current_data_mtime = DATA_FILE.stat().st_mtime
        if DATA_FILE_MTIME is None or current_data_mtime > DATA_FILE_MTIME:
            load_data()
    elif DATA_FILE_MTIME is not None:
        load_data()

    if MENTORSHIP_FILE.exists():
        current_mentorship_mtime = MENTORSHIP_FILE.stat().st_mtime
        if MENTORSHIP_FILE_MTIME is None or current_mentorship_mtime > MENTORSHIP_FILE_MTIME:
            load_mentorship_data()
    elif MENTORSHIP_FILE_MTIME is not None:
        load_mentorship_data()


def _contains(hay, needle):
    return needle.lower() in (hay or "").lower()


def apply_filters(items, args):
    result = items

    source = args.get("source")
    gender = args.get("gender")
    company = args.get("company")
    mode = args.get("mode")
    internship_type = args.get("internship_type")
    branch = args.get("branch")
    keyword = args.get("keyword")
    max_cgpa = _safe_float(args.get("max_cgpa"))

    if source:
        result = [i for i in result if _contains(i.get("source", ""), source)]
    if gender:
        result = [i for i in result if _contains(i.get("gender", ""), gender)]
    if company:
        result = [i for i in result if _contains(i.get("company", ""), company)]
    if mode:
        result = [i for i in result if _contains(i.get("mode", ""), mode)]
    if internship_type:
        result = [i for i in result if _contains(i.get("internship_type", ""), internship_type)]
    if branch:
        result = [i for i in result if _contains(i.get("branch_required", ""), branch)]
    if keyword:
        result = [
            i for i in result
            if any(
                _contains(i.get(field, ""), keyword)
                for field in ("title", "company", "skills", "eligibility_raw", "location")
            )
        ]
    if max_cgpa is not None:
        filtered = []
        for item in result:
            required = _safe_float(item.get("cgpa_required"))
            if required is None or required <= max_cgpa:
                filtered.append(item)
        result = filtered

    return result


def apply_sort(items, sort_by, sort_order):
    if sort_by not in ALLOWED_SORT_FIELDS and sort_by not in MENTORSHIP_SORT_FIELDS:
        return items

    reverse = sort_order.lower() == "desc"

    def sort_key(item):
        value = item.get(sort_by)
        if sort_by == "cgpa_required":
            parsed = _safe_float(value)
            return (parsed is None, parsed if parsed is not None else float("inf"))
        text = str(value or "").strip().lower()
        return (text == "", text)

    return sorted(items, key=sort_key, reverse=reverse)


def apply_mentorship_filters(items, args):
    result = items

    source = args.get("source")
    gender = args.get("gender")
    company = args.get("company")
    mode = args.get("mode")
    programme_type = args.get("programme_type")
    branch = args.get("branch")
    keyword = args.get("keyword")
    max_cgpa = _safe_float(args.get("max_cgpa"))

    if source:
        result = [i for i in result if _contains(i.get("source", ""), source)]
    if gender:
        result = [i for i in result if _contains(i.get("gender", ""), gender)]
    if company:
        result = [i for i in result if _contains(i.get("company", ""), company)]
    if mode:
        result = [i for i in result if _contains(i.get("mode", ""), mode)]
    if programme_type:
        result = [i for i in result if _contains(i.get("programme_type", ""), programme_type)]
    if branch:
        result = [i for i in result if _contains(i.get("branch_required", ""), branch)]
    if keyword:
        result = [
            i for i in result
            if any(
                _contains(i.get(field, ""), keyword)
                for field in (
                    "programme_name",
                    "company",
                    "description",
                    "eligibility",
                    "branch_required",
                    "how_to_apply",
                )
            )
        ]
    if max_cgpa is not None:
        filtered = []
        for item in result:
            required = _safe_float(item.get("cgpa_required"))
            if required is None or required <= max_cgpa:
                filtered.append(item)
        result = filtered

    return result


def paginate(items, page, page_size):
    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], page, page_size


@app.route("/")
def home():
    return jsonify(
        {
            "service": "Opportunity Radar API",
            "status": "ok",
            "data_file": str(DATA_FILE),
            "endpoints": [
                "/health",
                "/internships",
                "/internships/stats",
                "/mentorships",
                "/mentorships/stats",
                "/reload",
                "/reload/mentorship",
                "/compliance",
            ],
        }
    )


@app.route("/compliance")
def compliance():
    return jsonify(PROJECT_COMPLIANCE)


@app.route("/health")
def health():
    refresh_if_files_changed()
    return jsonify(
        {
            "status": "ok",
            "server_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "internships": {
                "scraped_at": DATA.get("scraped_at"),
                "total": DATA.get("total", 0),
                "sources": DATA.get("sources", []),
            },
            "mentorships": {
                "scraped_at": MENTORSHIP_DATA.get("scraped_at"),
                "total": MENTORSHIP_DATA.get("total", 0),
                "companies": MENTORSHIP_DATA.get("companies", []),
            },
        }
    )


@app.route("/reload", methods=["POST"])
def reload_data():
    load_data()
    return jsonify(
        {
            "message": "Internship data reloaded",
            "total": DATA.get("total", 0),
            "scraped_at": DATA.get("scraped_at"),
        }
    )


@app.route("/reload/mentorship", methods=["POST"])
def reload_mentorship_data():
    load_mentorship_data()
    return jsonify(
        {
            "message": "Mentorship data reloaded",
            "total": MENTORSHIP_DATA.get("total", 0),
            "scraped_at": MENTORSHIP_DATA.get("scraped_at"),
        }
    )


@app.route("/internships", methods=["GET"])
def get_internships():
    refresh_if_files_changed()
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    sort_by = request.args.get("sort_by", "title")
    sort_order = request.args.get("sort_order", "asc")

    filtered = apply_filters(DATA.get("internships", []), request.args)
    sorted_items = apply_sort(filtered, sort_by, sort_order)
    paged, page, page_size = paginate(sorted_items, page, page_size)

    return jsonify(
        {
            "meta": {
                "total": len(filtered),
                "page": page,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "scraped_at": DATA.get("scraped_at"),
            },
            "data": paged,
        }
    )


@app.route("/internships/stats", methods=["GET"])
def get_stats():
    refresh_if_files_changed()
    items = DATA.get("internships", [])
    by_source = {}
    by_gender = {}

    for item in items:
        source = item.get("source", "Unknown")
        gender = item.get("gender", "Unknown")
        by_source[source] = by_source.get(source, 0) + 1
        by_gender[gender] = by_gender.get(gender, 0) + 1

    return jsonify(
        {
            "total": len(items),
            "sources": sorted(DATA.get("sources", [])),
            "by_source": by_source,
            "by_gender": by_gender,
            "scraped_at": DATA.get("scraped_at"),
        }
    )


@app.route("/mentorships", methods=["GET"])
def get_mentorships():
    refresh_if_files_changed()
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 20))
    sort_by = request.args.get("sort_by", "programme_name")
    sort_order = request.args.get("sort_order", "asc")

    filtered = apply_mentorship_filters(MENTORSHIP_DATA.get("mentorship_programmes", []), request.args)
    sorted_items = apply_sort(filtered, sort_by, sort_order)
    paged, page, page_size = paginate(sorted_items, page, page_size)

    return jsonify(
        {
            "meta": {
                "total": len(filtered),
                "page": page,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "scraped_at": MENTORSHIP_DATA.get("scraped_at"),
            },
            "data": paged,
        }
    )


@app.route("/mentorships/stats", methods=["GET"])
def get_mentorship_stats():
    refresh_if_files_changed()
    items = MENTORSHIP_DATA.get("mentorship_programmes", [])
    by_source = {}
    by_gender = {}
    by_company = {}

    for item in items:
        source = item.get("source", "Unknown")
        gender = item.get("gender", "Unknown")
        company = item.get("company", "Unknown")
        by_source[source] = by_source.get(source, 0) + 1
        by_gender[gender] = by_gender.get(gender, 0) + 1
        by_company[company] = by_company.get(company, 0) + 1

    return jsonify(
        {
            "total": len(items),
            "companies": sorted(MENTORSHIP_DATA.get("companies", [])),
            "by_source": by_source,
            "by_gender": by_gender,
            "by_company": by_company,
            "scraped_at": MENTORSHIP_DATA.get("scraped_at"),
        }
    )


@app.route("/internships", methods=["POST"])
def replace_or_append_data():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Invalid JSON payload"}), 400

    if isinstance(payload, dict) and "internships" in payload:
        incoming = payload.get("internships", [])
        DATA["internships"] = incoming if isinstance(incoming, list) else []
        DATA["scraped_at"] = payload.get("scraped_at", DATA.get("scraped_at"))
    elif isinstance(payload, list):
        DATA["internships"].extend(payload)
    elif isinstance(payload, dict):
        DATA["internships"].append(payload)
    else:
        return jsonify({"error": "Payload must be a dict or list"}), 400

    DATA["total"] = len(DATA["internships"])
    DATA["sources"] = sorted({item.get("source", "Unknown") for item in DATA["internships"]})

    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scraped_at": DATA.get("scraped_at"),
                "total": DATA.get("total"),
                "sources": DATA.get("sources"),
                "internships": DATA.get("internships"),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return jsonify({"message": "Data updated", "total": DATA["total"]})


load_data()
load_mentorship_data()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)