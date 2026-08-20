# 🚀 AI Job Application Agent Architecture
*A highly resilient, end-to-end automated pipeline for discovering, evaluating, and applying to jobs via Applicant Tracking Systems (ATS).*

## 📖 Overview
This project is a fully autonomous AI agent designed to handle the entire job application lifecycle. Originally built for **XING**, the architecture is designed to be modular and resilient, making it a blueprint for automating applications on other ATS platforms (like LinkedIn, Join, StepStone, etc.).

It utilizes **Playwright** for robust browser automation, **Google Gemini 2.5 Flash** for intelligent decision-making and document tailoring, and **Dockerized LaTeX** for compiling pixel-perfect, tailored PDFs on the fly.

---

## ⚙️ Core Pipeline Architecture

The system is orchestrated by a master pipeline (`main_pipeline.py`) that executes distinct, independent steps. Data is passed between steps using local Excel/CSV databases, ensuring state preservation and crash recovery.

### Step 1: Harvester (`src/harvest.py`)
**Goal:** Discover and extract raw job listings based on configuration.
*   **Approach:** 
    *   Injects a saved authentication session (`session.json`) into Playwright.
    *   Iterates through search terms defined in `config/keywords.json`.
    *   Handles dynamic pagination (e.g., automatically clicking "Show more" buttons) to scrape maximum results.
    *   Extracts shallow data (Title, Company, Location, URL) and saves it to an initial database.

### Step 2: AI Filter (`src/filters.py`)
**Goal:** Ruthlessly eliminate irrelevant jobs to save API tokens and time.
*   **Approach:**
    *   **Pre-Filter (Regex):** Locally discards obvious mismatches (e.g., hardcoded blocklists, completely unrelated senior titles).
    *   **Deep AI Analysis:** Batches jobs and sends them to Gemini. 
    *   **Structured Output:** Forces Gemini to return a strict JSON array containing a boolean (`keep/reject`), an `AI Score (0-100)`, and an `AI Reason`.
    *   *Portability Note:* This step prevents the system from wasting time scraping full descriptions for garbage jobs.

### Step 3: Job Enrichment (`src/enrich_jobs.py`)
**Goal:** Fetch the full context for jobs that passed the AI filter.
*   **Approach:**
    *   Visits the dedicated URL of every kept job.
    *   Extracts the full HTML/Text job description.
    *   **Resilience Check:** Parses the DOM to verify if the job allows "Easy Apply" or redirects to an external company site. It specifically scans button text arrays to avoid false positives (e.g., clicking icon-only share buttons).

### Step 4: Classification (`src/classify.py`)
**Goal:** Determine the nature of the role to select the correct base document template.
*   **Approach:**
    *   Passes the full job description to Gemini to categorize the role (e.g., "Student/Intern" vs "Full-Time").
    *   This classification directly dictates whether `CV_TEMPLATE_STUDENT` or `CV_TEMPLATE_FULLTIME` is injected into the next stage.

### Step 5: Auto-Apply Engine (`src/apply_all.py` & `src/apply/`)
**Goal:** Generate hyper-targeted documents and navigate complex multi-step application forms.
*This module is heavily decomposed into smaller services for maintainability.*

#### A. AI Tailoring (`src/apply/ai_agent.py`)
*   Reads strict constraints from `config/prompts/prompt.txt`.
*   Modifies the user's base LaTeX CV. **Critical Constraints:** Limits to max 1 page, max 4 projects, and forces 1-line bullet points to prevent LaTeX compilation overflows.
*   Generates a highly personalized Cover Letter using the same context.

#### B. Document Compilation (`src/apply/compiler.py`)
*   Uses a **Dockerized TeX Live container** (`texlive/texlive`) to run `pdflatex`.
*   This isolates the compilation process, removing the need for massive local LaTeX installations and ensuring consistent PDF generation across all operating systems.

#### C. Browser Automation & Smart Forms (`src/apply/browser.py`)
*   **Multi-Step Navigation:** Uses a robust retry loop to click "Next/Continue" buttons, handling dynamic form lengths.
*   **Stateful Document Management:** Actively looks for "Remove Document" buttons to delete old CVs from the ATS before uploading the newly generated tailored PDF.
*   **The "Smart Questions" Agent:**
    *   *Problem:* ATS platforms ask unpredictable custom questions (salary expectations, visa status, start dates).
    *   *Solution:* Injects a custom JavaScript block to extract all unanswered form fields (`input`, `select`, `checkbox`, `radio`), capturing their labels and options.
    *   Sends this JSON payload, along with the user's `config/personal_info.txt`, to Gemini in a single batch.
    *   *Resilience:* Uses a fast-fail Playwright `select_option` combined with a JS "fuzzy text match" fallback to guarantee dropdowns are selected even if the AI slightly hallucinates the option text.

---

## 🖥️ Command Center (Dashboard)
To monitor and control the pipeline, the system features a Flask-based Single Page Application (SPA) at `src/dashboard.py`.
*   **Terminal Streaming:** Background processes are triggered via `subprocess` and their outputs are piped to a log file, which is streamed to a live terminal UI in the browser.
*   **Configuration Manager:** Allows direct editing of JSON keywords, AI prompts, and Personal Information Context via the UI.
*   **Data Visibility:** Exposes the `AI Score` and `AI Reason` directly in the database table so the user understands the AI's decision-making process.

---

## 🛠️ How to Port this to a New ATS (e.g., Join, StepStone)
To adapt this architecture to a new platform, you only need to modify the Playwright DOM selectors. The core logic remains identical.

1.  **Update `harvest.py`:** Change the URL structure and the CSS selectors for the job feed cards.
2.  **Update `enrich_jobs.py`:** Change the selector used to extract the `<div class="job-description">`.
3.  **Update `apply/browser.py`:**
    *   Update the "Easy Apply" button selector.
    *   Update the "Remove Document" / "Upload Document" button selectors.
    *   *The Smart Questions Agent (JS extraction) is largely platform-agnostic* because it targets generic HTML tags (`input`, `select`, `textarea`). It will likely work out-of-the-box on a new ATS.

---

## 🧠 Technical Optimizations & Design Choices
The workflow is explicitly designed to handle the unreliability of web scraping and LLM hallucinations. Here is the rationale behind the technical approaches:

### 1. State-Driven, Decoupled Pipeline
Instead of running a single monolithic script that goes from scraping to applying in memory, the pipeline uses **local Excel databases as state stores** between steps.
*   **Why:** Browser automation is inherently fragile due to timeouts, UI updates, and network errors. By decoupling the steps, if the `apply` script crashes on job #40, jobs 1-39 are safely saved. The user can simply restart the pipeline and it resumes precisely from job #40.

### 2. Two-Pass Filtering Strategy
*   **Why:** Sending thousands of scraped jobs to a Large Language Model is expensive and triggers rate-limit blockages (HTTP 429).
*   **Optimization:** We use a lightweight, local Regex "Pre-Filter" to instantly discard completely irrelevant jobs (e.g., senior roles or blacklisted companies) for free. Only the borderline/good jobs are sent to Gemini for the expensive "Deep Analysis" pass.

### 3. Batch Processing & Structured JSON
*   **Why:** Making an individual API call for every single custom application question (or every single job filter) is drastically slow.
*   **Optimization:** The "Smart Questions" agent uses injected JavaScript (`page.evaluate()`) to extract the entire DOM state of the form in under 50ms. It sends all fields in a single batch to Gemini, enforcing a strict `application/json` schema output. This ensures high speed and prevents the LLM from responding with conversational fluff.

### 4. Dockerized Document Generation
*   **Why:** LaTeX distributions (like TeX Live) are massive (upwards of 4GB) and notoriously difficult to configure consistently across Windows, Mac, and Linux.
*   **Optimization:** The pipeline calls a lightweight Docker container (`texlive/texlive`) to compile the PDFs. This makes the project portable, reproducible, and ready for deployment on remote cloud servers without complex dependency management.

### 5. Resilient "Fuzzy" UI Fallbacks
*   **Why:** LLMs sometimes hallucinate slightly incorrect strings (e.g., generating "Yes" instead of "Yes, I require sponsorship" for a dropdown option). Standard Playwright locators freeze the script for 30 seconds when an exact match fails.
*   **Optimization:** The `apply/browser.py` uses aggressive short timeouts (2 seconds) for exact matches, instantly falling back to a custom JavaScript function that performs "fuzzy substring matching" on the dropdown options. If that also fails, it blindly selects the second option to force the application to proceed, prioritizing completion over perfection.
