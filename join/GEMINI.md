# Join.com Job Automation Pipeline

## Project Overview
This project is a Python-based automation tool designed to streamline the process of finding, filtering, and applying for jobs on Join.com. It leverages web scraping (Playwright) to find job postings, and Artificial Intelligence (Google Gemini/Perplexity) to filter jobs based on user preferences and generate tailored application materials (CVs and Cover Letters).

### Main Technologies
*   **Python:** The core programming language.
*   **Playwright:** Used for asynchronous web automation, navigating Join.com, and filling out application forms.
*   **Google Generative AI (Gemini):** Powers the job filtering logic and generates contextual answers for application form questions.
*   **Pandas:** Handles the structuring and export of job data into Excel files (`filtered_jobs.xlsx`).
*   **LaTeX:** Used for generating dynamic PDF CVs and Cover Letters from templates.

## Directory Structure
*   `config/`: Centralized configuration. Contains `settings.py` for global variables, `.env` for secrets, and a `prompts/` directory for LLM instructions.
*   `src/`: The source code containing the pipeline steps:
    *   `main_pipeline.py`: The entry point that orchestrates the workflow.
    *   `fetch_urls.py`: Gathers job URLs using search engines.
    *   `filter_jobs.py`: Uses AI to evaluate and filter the fetched job postings.
    *   `apply_all.py`: Automates the form-filling and document-generation process for the filtered jobs.
    *   `login.py`: Handles authentication.
*   `templates/`: LaTeX (`.tex`) templates for CVs (Full-time and Working Student) and Cover Letters.
*   `output/`: Stores the generated artifacts, including the `filtered_jobs.xlsx` sheet, URL lists, and a `My_Applications/` folder containing tailored CVs/Cover Letters for each job.
*   `debug/`: Used for storing debug logs and screenshots.

## Building and Running

Ensure you have the necessary dependencies installed. You can install them using:
```bash
pip install -r requirements.txt
python -m playwright install chromium
```
You will also need Docker installed on your system to compile the PDFs (or LaTeX if you modify the code).

The pipeline is executed via the `src/main_pipeline.py` script. It can be run entirely or step-by-step.

**Run the full pipeline:**
```bash
python src/main_pipeline.py --all
```

**Run specific stages:**
```bash
# Step 1: Fetch job URLs
python src/main_pipeline.py --fetch

# Step 2: Filter the fetched jobs using AI
python src/main_pipeline.py --filter

# Step 3: Apply to the filtered jobs
python src/main_pipeline.py --apply
```

**Options:**
*   `--engine <engine_name>`: Specify the search engine to use for fetching URLs (`google`, `perplexity`, `serpapi`, `brave`, or `scrapingbee`). Defaults to `serpapi`.
*   `--ai-provider <provider>`: Specify the AI provider to use (`gemini` or `openrouter`). Defaults to `gemini`.

## Development Conventions
*   **Centralized Settings:** All paths, constants, and API key references must be defined in `config/settings.py`. Do not hardcode paths in the `src/` files.
*   **Externalized Prompts:** Keep AI prompts in `config/prompts/` as `.txt` files rather than inline strings to make them easier to modify.
*   **Environment Variables:** Sensitive information like API keys should be stored in `config/.env` and loaded via `python-dotenv`.
