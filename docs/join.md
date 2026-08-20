# Join.com Job Application Pipeline

Location: [`join/`](../join)

A fork/adaptation of the [XING pipeline](xing.md) retargeted at **join.com** (a German job-board/ATS platform — "join" is the platform's name, not a generic verb). Same overall concept — discover, filter, tailor, apply — but with a materially different job-discovery mechanism and a pluggable multi-provider AI layer. The folder even carries a copy of `XING.md`, the doc this fork started from.

## Key differences from XING

### Search-engine-based discovery instead of site search

join.com has no scrapable in-site job search, so `src/fetch_urls.py` instead queries one of five pluggable search engines with `site:join.com/companies {keyword} {region}` queries:

- Google Custom Search
- Perplexity
- SerpAPI (default)
- Brave Search
- ScrapingBee

Region/keyword priority ("DACH → Benelux → Others") comes from `config/search_keywords.json`. URLs are validated against the expected shape (`join.com/companies/<company>/<id>-<slug>`) and appended to `output/urls.txt`. If a query returns nothing, it falls back through time-filtered → unfiltered → broader query.

### Two-pass AI filtering

1. `src/filter_jobs.py` — cheap Pass 1 filter on the URL slug alone, before any scraping.
2. `src/enrich_jobs.py` — Playwright scrapes full descriptions and detects expired/404 postings.
3. `src/filter_deep.py` — Pass 2: regex blocklist + Gemini deep-filter on the full description.

### Multi-provider AI client

`src/ai_client.py` defines a shared `ai_client` singleton so every AI-touching script goes through one abstraction instead of calling `genai` directly:

- `AI_PROVIDER=gemini` → `google-generativeai`, model `gemini-3-flash-preview` / `gemini-2.5-flash`.
- `AI_PROVIDER=openrouter` → `openai.AsyncOpenAI` pointed at OpenRouter, model `deepseek/deepseek-v4-flash:free`.

### Pipeline driver

`src/main_pipeline.py` uses `argparse` flags rather than a step-number list:

```bash
python src/main_pipeline.py --all
python src/main_pipeline.py --fetch
python src/main_pipeline.py --filter
python src/main_pipeline.py --apply
python src/main_pipeline.py --fetch --engine brave --ai-provider openrouter
```

Each stage runs as its own subprocess (`fetch_urls.py`, `filter_jobs.py`, `enrich_jobs.py`, `filter_deep.py`, `apply_all.py`).

### `src/apply/` package (different shape from XING's)

Exports `tailor_documents, get_ai_answer, compile_pdf, apply_to_job, detect_cv_template, clean_filename` from `__init__.py`:

- **`ai_agent.py`**
  - `tailor_documents()` — returns **both** CV and cover-letter LaTeX from a single Gemini/OpenRouter call (two fenced ` ```latex ` blocks), post-processed by `clean_tex()` which auto-escapes stray `_`/`&`.
  - `answer_questions()` — the same "Smart Questions" form-filling agent as XING's, but built on the shared `ai_client` and `settings.SMART_QUESTIONS_PROMPT`.
  - `get_ai_answer()` — a generic short-answer helper using `settings.APPLY_PROMPT`.
- **`browser.py`** — `apply_to_job(page, url, cv_path, cl_path, job_desc)`:
  - Multilingual "Apply now" / "Bewerben" / "Postuler" button detection.
  - CV upload via direct `<input type=file>` first, file-chooser dialog as fallback.
  - A dedicated **cover-letter upload step** (join.com has one; XING doesn't), detected via a multilingual keyword scan of the page.
  - A `max_steps=6` loop combining Smart Questions answering with Continue-clicking until a Review page or Submit button appears.
  - Multilingual Submit click; detects "job no longer available" text and marks the job `"Expired"`.
- **`compiler.py`** — `compile_pdf(tex_content, output_dir, filename_base)` POSTs to the [`latex-self-hosted`](latex-self-hosted.md) compiler service (`LATEX_COMPILER_URL`, same as XING), and on failure saves the compiler's error response to `debug/<name>_compile_error.log`. (Previously shelled out to `docker run texlive/texlive:latest pdflatex` directly — replaced so the pipeline doesn't need Docker socket access, which is required for running it in Kubernetes.)
- **`utils.py`** — `detect_cv_template()` checks job URL/title against a large `settings.STUDENT_KEYWORDS` list; `clean_filename()` sanitizes filenames.

### Other differences

- **`src/apply_all.py`** — processes rows where `Filter Status == "Kept (Deep)"`, re-scrapes the live page for title/company/description, checks for "already applied" text, caches/recompiles PDFs by a filename convention (`{PDF_NAME_PREFIX}_CV.pdf` / `_CoverLetter.pdf`), then calls `apply_to_job` and records `Application Status`.
- **`src/login.py`** — uses **Firefox** (XING's uses Chromium), non-headless, with console/network error logging; saves `config/session.json`.
- **`src/dashboard.py`** — same Flask shape as XING's, but reads `settings.FILTERED_JOBS_FILE`, locates application folders by a `*_{company}_{job_id}` naming pattern, and adds `/favicon.ico` and `/meta.json` stub routes.

## Configuration (`join/config/settings.py`)

Path-based (`pathlib`) rather than string-based. Notable settings:

- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL`
- `GOOGLE_API_KEY` / `GOOGLE_SEARCH_API_KEY` / `SEARCH_ENGINE_ID`
- `PERPLEXITY_API_KEY`, `SERPAPI_KEY`, `BRAVE_API_KEY`, `SCRAPINGBEE_API_KEY`
- `AI_PROVIDER` (default `"gemini"`)
- `GEMINI_MODEL` / `GEMINI_MODEL_FILTER`
- `SEARCH_TIME_LIMIT` (default `"past_month"`)
- `DEFAULT_SEARCH_ENGINE` (default `"serpapi"`)
- `USER_PHONE`, `PDF_NAME_PREFIX = "Fathi_BELMKADEM"`, `STUDENT_KEYWORDS`
- `LATEX_COMPILER_URL` (defaults to `http://localhost:5000`)

`output/`, `debug/`, `My_Applications/`, and `prompts/` directories are auto-created on import. Prompts load as module-level strings from `config/prompts/{filter_prompt,apply_prompt,smart_questions_prompt,deep_filter_prompt,prompt}.txt`. `config/prompts/prompt.txt.old` is a superseded prior version kept for reference.

## External services

- **join.com** — target site.
- **Google Custom Search / Perplexity / SerpAPI / Brave Search / ScrapingBee** — pluggable job-discovery search engines.
- **Google Gemini and/or OpenRouter** — AI filtering and tailoring.
- **`latex-self-hosted`** — the compiler service used for CV/cover-letter PDF generation (see [latex-self-hosted.md](latex-self-hosted.md)).

## Environment variables

`GEMINI_API_KEY` / `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_SEARCH_API_KEY`, `SEARCH_ENGINE_ID`, `PERPLEXITY_API_KEY`, `SERPAPI_KEY`, `BRAVE_API_KEY`, `SCRAPINGBEE_API_KEY`, `AI_PROVIDER`, `LATEX_COMPILER_URL` (see `config/.env.example`)

## Running it

```bash
pip install -r requirements.txt
python -m playwright install chromium
python src/main_pipeline.py --all
```

A `latex-self-hosted` instance must be reachable at `LATEX_COMPILER_URL` for PDF compilation — see [latex-self-hosted.md](latex-self-hosted.md) to run one locally, or [deployment.md](deployment.md) for the Kubernetes deployment.

Requires Docker for PDF compilation.
