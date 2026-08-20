# XING Job Application Pipeline

Location: [`XING/`](../XING)

End-to-end automated pipeline that discovers job postings on XING.com, filters them with AI, tailors a CV and cover letter per job, compiles them to PDF, and submits the application through XING's own "Easy Apply" flow. Includes a Flask dashboard for monitoring and control.

## Pipeline stages

Orchestrated by `src/main_pipeline.py` (`python src/main_pipeline.py -s all`, or `-s 1 2 3 4 5` for specific steps). Each stage reads/writes an Excel file so the pipeline can resume after a crash without losing progress.

| Step | File | What it does |
|---|---|---|
| 1. Harvest | `src/harvest.py` | Playwright scrapes `xing.com/jobs/search` for each keyword in `config/keywords.json`, scrolling/clicking "Show more" to page through results. Dismisses the Usercentrics cookie banner. Dedupes by MD5 hash of the job URL. Writes shallow listings (title, company, location, URL) to `output/intermediate_jobs.csv` incrementally. |
| 2. AI Filter | `src/filters.py` | A regex pre-filter locally rejects obviously irrelevant titles (senior/manager/sales roles, blocked companies) for free. Remaining jobs are batched to Gemini 2.5 Flash, which returns a strict JSON verdict per job: keep/reject, an `AI Score (0–100)`, and an `AI Reason`. Writes `output/filtered_jobs.xlsx`. |
| 3. Enrich | `src/enrich_jobs.py` | Visits each kept job's URL, scrapes the full description, and determines whether it's "Easy Apply" (in-site) or redirects externally — by scanning button text (multilingual-aware) rather than relying on a single selector. Splits results into `output/final_jobs_auto.xlsx` (Easy Apply) and `output/final_jobs_manual.xlsx` (external, handled manually). Restarts the browser every 50 jobs or on crash for resilience. |
| 4. Classify | `src/application_manager.py` (`classify_all_jobs`) | Gemini 2.5 Flash (with a keyword-heuristic fallback) labels each job "Student/Intern" or "Full-Time" to pick the right base CV template. Writes `output/jobs_student.xlsx` / `output/jobs_fulltime.xlsx`. |
| 5. Apply | `src/apply_all.py` + `src/apply/*` | For each pending row in `final_jobs_auto.xlsx`: selects a CV template, tailors CV + cover letter with Gemini, compiles both to PDF via the `latex-self-hosted` compiler service, then drives the full XING application flow in Playwright. |

## `src/apply/` package

Split out of a monolithic `apply_all.py` (the split was performed by `refactor.py`, a one-off script not meant to be re-run):

- **`utils.py`** — `get_cv_template()` picks Student vs. Full-time template by job type/title heuristics; `handle_cookies()` dismisses the Usercentrics banner.
- **`compiler.py`** — `compile_cv()` POSTs the generated `.tex` content to the [`latex-self-hosted`](latex-self-hosted.md) compiler service (`LATEX_COMPILER_URL`, see [deployment.md](deployment.md)) and writes the returned PDF bytes to disk. Deletes a bad `.tex` file on failure so the next run regenerates it. (Previously shelled out to `docker run texlive/texlive:latest pdflatex` directly — replaced so the pipeline doesn't need Docker socket access, which is required for running it in Kubernetes.)
- **`ai_agent.py`** —
  - `tailor_cv()` / `tailor_cover_letter()`: Gemini 2.5 Flash calls using prompt templates from `config/prompts/` with `{{base_prompt}}` / `{{cv_template_content}}` / `{{description}}` placeholders.
  - `answer_questions()`: the "Smart Questions" agent — extracts every unanswered form field (inputs, selects, checkboxes, radios) via injected JavaScript, sends them in one batch to Gemini alongside `config/personal_info.txt`, and fills/selects/checks the answers.
  - `find_element_with_ai()`: DOM-dump + Gemini fallback for locating an element when standard selectors fail.
- **`browser.py`** — `apply_to_job()`: clicks Apply → "Edit your application" → navigates the multi-step form (retry loop for Next/Continue) → removes any existing CV on the ATS before uploading the new one → optionally attaches a cover letter and certificates from `Optional_files/` → fills phone number → runs the Smart Questions agent → submits. Returns a status string that gets written back to the `Status` column.

## Other scripts

- **`src/login.py`** — one-time manual login (non-headless Chromium) that saves Playwright's storage state to `config/session.json` for reuse by every other script.
- **`src/dashboard.py`** — Flask SPA (`templates/dashboard.html`, port 5000) with routes: `/api/jobs` (reads `final_jobs_auto.xlsx`, including AI Score/Reason columns), `/api/pdf/<id>/<cv|cl>`, `/api/action/<harvest|filter|enrich|classify|apply|full>` (spawns `main_pipeline.py -s N` as a subprocess and streams its log to the browser), `/api/status`, `/api/settings` (edit keywords/prompts/personal info from the UI).
- **`src/research.py`** — standalone debug script for testing XING search UI selectors (dumps a screenshot to `search_debug.png`).
- **`src/repair_state.py`** — one-off consistency fixer that resets `Enrichment Status` for jobs marked "Done" in `filtered_jobs.xlsx` but missing from `final_jobs_auto.xlsx`.
- **`src/migrate_legacy.py`** — one-off migration marking old pending rows as "Old"/"Legacy".
- **`src/models.py`** — `Job` dataclass (title, company, location, url, id).

> Note: `application_manager.py` also contains a legacy `generate_applications()` tailoring path that predates the `src/apply/` package and is no longer used by the main pipeline.

## Configuration (`XING/config/`)

- **`.env`** — `GEMINI_API_KEY`.
- **`settings.py`** — centralized paths and constants: `GOOGLE_API_KEY`, all `output/`/`config/` paths, `PHONE_NUMBER`, `FINAL_PDF_NAME`, `LATEX_COMPILER_URL` (defaults to `http://localhost:5000`).
- **`keywords.json`** — job search terms used by the harvester (`keywords.json.bak` is a backup copy).
- **`personal_info.txt`** — candidate details fed to the Smart Questions agent.
- **`session.json`** — saved Playwright login state.
- **`prompts/`** — Gemini prompt templates for CV tailoring, cover letter generation, filtering, etc.

## External services

- **XING.com** — scrape/apply target.
- **Google Gemini API** (`google-generativeai`, model `gemini-2.5-flash`) — filtering, classification, tailoring, form-question answering.
- **`latex-self-hosted`** — the compiler service used for CV/cover-letter PDF generation (see [latex-self-hosted.md](latex-self-hosted.md)). Run it locally via Docker, or point `LATEX_COMPILER_URL` at a deployed instance.

## Environment variables

- `GEMINI_API_KEY`
- `LATEX_COMPILER_URL` (defaults to `http://localhost:5000`)

## Running it

```bash
pip install -r requirements.txt
playwright install chromium
python src/main_pipeline.py       # full pipeline
python src/harvest.py             # or run a single stage
python src/apply_all.py
```

`config/.env` must contain `GEMINI_API_KEY=<your key>` (see `config/.env.example`), and `config/keywords.json` should be updated with your desired search terms before the first run. A `latex-self-hosted` instance must be reachable at `LATEX_COMPILER_URL` for PDF compilation — see [latex-self-hosted.md](latex-self-hosted.md) to run one locally, or [deployment.md](deployment.md) for the Kubernetes deployment.
