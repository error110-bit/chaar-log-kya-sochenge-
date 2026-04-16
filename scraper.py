import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INTERNSHIP_SCRAPER = ROOT / "scrapers" / "internship_scraper.py"
MENTORSHIP_SCRAPER = ROOT / "scrapers" / "mentorship_scraper.py"


def run_script(script_path: Path, extra_args: list[str]) -> int:
    if not script_path.exists():
        print(f"Missing script: {script_path}")
        return 1

    command = [sys.executable, str(script_path), *extra_args]
    return subprocess.call(command)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Unified scraper runner for internships and mentorship programmes.\n"
            "Examples:\n"
            "  python scraper.py internships --once --no-details --pages 1\n"
            "  python scraper.py mentorship --once\n"
            "  python scraper.py all --once --no-headless"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "target",
        choices=["internships", "mentorship", "all"],
        help="Which scraper to run",
    )
    parser.add_argument(
        "scraper_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the selected scraper(s)",
    )

    args = parser.parse_args()
    passthrough = list(args.scraper_args)

    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    if args.target == "internships":
        return run_script(INTERNSHIP_SCRAPER, passthrough)

    if args.target == "mentorship":
        return run_script(MENTORSHIP_SCRAPER, passthrough)

    internship_code = run_script(INTERNSHIP_SCRAPER, passthrough)
    mentorship_code = run_script(MENTORSHIP_SCRAPER, passthrough)

    if internship_code != 0:
        return internship_code
    return mentorship_code


if __name__ == "__main__":
    raise SystemExit(main())
