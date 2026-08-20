# XING Job Automation Agent

An end-to-end automated pipeline for discovering, filtering, and applying to jobs on XING. It uses AI (Google Gemini) for tailoring applications and Playwright for browser automation.

## Project Overview

This project automates the entire job application lifecycle on XING:
1.  **Harvesting:** Scrapes job listings based on keywords defined in `config/keywords.json`.
2.  **Filtering & Selection:** Uses Gemini AI to filter out irrelevant jobs and select those that match the user's profile.
3.  **Enrichment:** Scrapes full job descriptions for selected postings.
4.  **Classification:** Categorizes jobs as "Student/Intern" or "Full-Time" to select the appropriate CV template.
5.  **Tailoring & Application:**
    *   Generates a tailored CV and Cover Letter (LaTeX) using Gemini AI based on the job description.
    *   Compiles LaTeX to PDF using a Dockerized TeX Live environment.
    *   Automatically applies to the job on XING, uploading the custom documents and filling in basic details.

## Core Technologies

*   **Language:** Python 3.x
*   **Browser Automation:** Playwright
*   **AI Engine:** Google Gemini (Generative AI)
*   **Data Management:** Pandas, Excel (openpyxl)
*   **Document Generation:** LaTeX, Docker (`texlive/texlive`)
*   **Environment Management:** `python-dotenv`

## Directory Structure

*   `src/`: Main source code.
    *   `main_pipeline.py`: The master script that orchestrates all steps.
    *   `harvest.py`: Scraping logic for discovering new jobs.
    *   `filters.py`: AI-driven filtering of harvested jobs.
    *   `enrich_jobs.py`: Scrapes full descriptions for selected jobs.
    *   `application_manager.py`: Handles job classification and status updates.
    *   `apply_all.py`: Core logic for tailoring CVs, compiling PDFs, and submitting applications.
*   `config/`: Configuration and prompt templates.
    *   `.env`: API keys and sensitive configuration (must be created from a template).
    *   `keywords.json`: Keywords used for harvesting.
    *   `settings.py`: Centralized path and configuration management.
    *   `prompts/`: Text templates for Gemini AI instructions (CV tailoring, Cover Letter, etc.).
*   `templates/`: LaTeX `.tex` templates for CVs and Cover Letters.
*   `output/`: Data storage and application logs.
    *   `My_Applications/`: Contains a folder for every job application, including tailored `.tex` and `.pdf` files.
    *   `final_jobs_auto.xlsx`: The main database of jobs and their application status.
*   `debug/`: Scripts for verifying the environment and debugging specific components (LaTeX, API, etc.).

## Setup & Usage

### Prerequisites

1.  **Python 3.10+**
2.  **Docker:** Required for LaTeX compilation.
3.  **Gemini API Key:** Obtain from [Google AI Studio](https://aistudio.google.com/).

### Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```
3.  Configure environment variables:
    Create a `config/.env` file with:
    ```env
    GEMINI_API_KEY=your_api_key_here
    ```
4.  Update `config/keywords.json` with your desired job search terms.

### Running the Pipeline

To run the complete automated process:
```bash
python src/main_pipeline.py
```

To run individual steps:
*   **Harvesting:** `python src/harvest.py`
*   **Apply to all pending:** `python src/apply_all.py`

## Development Conventions

*   **Paths:** Always use `config/settings.py` to reference file paths to ensure cross-platform compatibility and centralized management.
*   **Data Storage:** Jobs are tracked in `output/final_jobs_auto.xlsx`. The `Status` column reflects the current state (e.g., "Skipped", "Failed", or a timestamp of submission).
*   **AI Tailoring:** Prompts are stored in `config/prompts/`. Any changes to tailoring logic should be made there first.
*   **LaTeX Compilation:** The system uses `pdflatex` inside a Docker container (`texlive/texlive:latest`) to avoid local TeX installation overhead.
