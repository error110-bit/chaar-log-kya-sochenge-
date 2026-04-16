Opportunity Radar: Scraper + Backend API

Restriction Compliance

This project does not use any pre-existing internship/job API.
Data is collected only through direct website HTML scraping and curated official company career links.
The site/backend has no login, no signup, and no user credential collection.
Project is open-source and licensed under MIT (see LICENSE).

This project has two runtime parts:

1. Scraper: one entry file `scraper.py` that runs internship and/or mentorship scraping.
2. Backend API: one entry file `backend.py` that serves filtered/sorted/paginated data.

Project layout is intentionally simplified:

- `scraper.py` (single scraper entrypoint)
- `backend.py` (single backend entrypoint)
- `scrapers/` (actual scraper implementations)
- `frontend/` (all frontend code in one place)

Quick Start

1. Install dependencies:

   pip install selenium pandas beautifulsoup4 lxml flask flask-cors requests

2. Run internship scraper once (writes internships_latest.json):

   python scraper.py internships --once --no-details --pages 1

2.1 Run mentorship scraper once (writes mentorship_latest.json):

python scraper.py mentorship --once

2.2 Run both in one command (optional):

python scraper.py all --once

3. Start backend:

   python backend.py

4. Verify API:

   python archive/legacy/test.py

Data File Used By Backend

By default, backend reads:

- internships_latest.json
- mentorship_latest.json

You can override this with an environment variable:

- INTERNSHIPS_DATA_FILE
- MENTORSHIP_DATA_FILE

Example:

set INTERNSHIPS_DATA_FILE=internships_20260414.json
set MENTORSHIP_DATA_FILE=mentorship_latest.json
python backend.py

API Endpoints

1. GET /
   Returns service info and available endpoints.

2. GET /health
   Basic health check and dataset metadata.

2.1 GET /compliance
Returns compliance metadata confirming that no pre-existing job/internship API is used.
Also confirms no-login and no-credentials policy.

3. POST /reload
   Reloads internship JSON file from disk without restarting backend.

3.1 POST /reload/mentorship
Reloads mentorship JSON file from disk without restarting backend.

4. GET /internships
   Main endpoint for frontend listing pages.

   Query params:
   - source
   - gender
   - company
   - mode
   - internship_type
   - branch
   - keyword
   - max_cgpa
   - page (default: 1)
   - page_size (default: 20, max: 100)
   - sort_by (title/company/source/location/stipend/duration/mode/internship_type/branch_required/cgpa_required/gender/deadline)
   - sort_order (asc/desc)

   Response shape:
   {
   "meta": {
   "total": 25,
   "page": 1,
   "page_size": 20,
   "sort_by": "title",
   "sort_order": "asc",
   "scraped_at": "2026-04-14T18:55:01"
   },
   "data": [ ...internship records... ]
   }

5. GET /internships/stats
   Aggregates counts by source and gender.

5.1 GET /mentorships
Main endpoint for mentorship page in frontend.

Query params:

- source
- gender
- company
- mode
- programme_type
- branch
- keyword
- max_cgpa
- page (default: 1)
- page_size (default: 20, max: 100)
- sort_by (source/company/programme_name/programme_type/duration/mode/branch_required/cgpa_required/gender/deadline)
- sort_order (asc/desc)

  5.2 GET /mentorships/stats
  Aggregates mentorship counts by source, company, and gender.

6. POST /internships
   Update backend data directly from JSON payload.
   - If payload is {"internships": [...]} then dataset is replaced.
   - If payload is [...] list then records are appended.
   - If payload is {...} single record then one record is appended.

Frontend Integration Notes

1. Backend has CORS enabled (if flask-cors is installed), so your frontend can call it directly.
2. Use /internships for list pages and /internships/stats for dashboard cards/charts.
3. Use /mentorships for mentorship page and /mentorships/stats for mentorship dashboard cards/charts.
4. After running internship scraper, call POST /reload.
5. After running mentorship scraper, call POST /reload/mentorship.
6. Keep frontend filters mapped 1:1 with query params listed above.

Suggested Frontend Call Example

GET http://127.0.0.1:5000/internships?keyword=data&page=1&page_size=12&sort_by=deadline&sort_order=asc

Frontend Integration Kit (Layout-Safe)

If your HTML/CSS layout is already done, use the generated JS files in frontend/static-integration/:

- frontend/static-integration/api.js
- frontend/static-integration/internships-page.js
- frontend/static-integration/mentorships-page.js
- frontend/static-integration/integration-example.html (reference markup only)

How to plug into your existing pages:

1. Keep your own HTML/CSS layout unchanged.
2. Add required element IDs where data should render:
   - Internships page IDs: internship-list, internship-total, internship-error, internship-pagination
   - Mentorship page IDs: mentorship-list, mentorship-total, mentorship-error, mentorship-pagination
3. Optional filter IDs:
   - Internships: internship-search, internship-source, internship-gender, internship-sort-by, internship-sort-order
   - Mentorship: mentorship-search, mentorship-source, mentorship-company, mentorship-gender, mentorship-sort-by, mentorship-sort-order
4. Include script tags in your page:

   <script>
     window.API_BASE_URL = "http://127.0.0.1:5000";
   </script>
   <script type="module" src="./frontend/static-integration/internships-page.js"></script>
   <script type="module" src="./frontend/static-integration/mentorships-page.js"></script>

You can include only one script per page if pages are separate.

Next.js frontend app location:

- frontend/next-app

To run it:

1. cd frontend/next-app
2. npm install
3. npm run dev
