# Automated Workflows (n8n)

Location: [`Automated workflows/`](../Automated%20workflows)

Four n8n workflow exports (JSON) covering cold-outreach (discovery, cleanup, sending) and an on-demand CV/cover-letter tailoring backend. They share a single Google Sheet as their contacts database (doc id `1j1dL0GossVgv64vc34tc-z3fqokruUui3SAd1qJuFeQ`, referred to internally as "test-sheet"), with tabs `Feuille 7` (Company Discovery output), `startups-nrw` (fed by [`scrapers/startups.nrw`](scrapers.md)), `munich-startups`, and `Scraped`.

## `Company Discovery.json`

**Workflow name:** "Company Discovery +" · **Trigger:** cron, every 2 hours (`0 */2 * * *`), or manual.

Continuously discovers German companies and verified **human** (not role-based) contact emails for cold outreach, dedupes against the Google Sheet, and appends new rows.

1. **Set Search Parameters** — hardcoded targeting: HR/recruiting/engineering leadership roles (Head of People, CTO, Founder, etc.), company sizes (scale-up, Series A, GmbH...), industry ("all companies with an IT department"), German locations (Berlin, Munich, Regensburg, Nuremberg, Passau, Bavaria), `results_limit=50`.
2. **Message a model** (Gemini `gemini-3-pro-preview`) — prompted as a B2B research specialist with strict rules: only personally-identifiable emails (`firstname.lastname@company.de`), explicitly forbidding generic inboxes (`info@`, `hr@`, `careers@`), requiring verification via LinkedIn/Impressum/Handelsregister. Returns a JSON array of `{company, email, contact_name, job_title, website, source}`.
3. **Parse & Validate** (Code) — regex-validates emails, rejects free-mail domains (gmail/yahoo/hotmail/outlook).
4. **Google Sheets - Check Existing** + **Deduplicate** (Code) — reads the `Feuille 7` tab and filters out already-known emails.
5. **Loop Over Items** → **Message a model1** (Gemini `gemini-2.5-flash`) — generates a 2–3 sentence executive-style description per company.
6. **Final Row Formatter** → **Google Sheets - Append Row** — writes `Email, Company, Full Name, Company_description, Website, Source, Date_Added`, with `Wait` nodes throughout for rate-limit protection.

## `Remove-Bounced-Email.json`

**Workflow name:** "Bounced Email - Update Sheets account 2" · **Trigger:** schedule (interval) or manual, `active: true`.

Keeps the outreach contact list clean by detecting bounced emails and marking the corresponding rows.

1. **Gmail - Get Bounced Emails** — searches Gmail for `from:mailer-daemon@googlemail.com`.
2. **Extract Bounced Emails** (Code) — parses Mail Delivery Subsystem messages (handles base64-decoded MIME parts), regex-extracts the bounced recipient's address, and classifies the bounce reason (Address not found, User does not exist, Mailbox full, Blocked/Rejected as spam, Invalid recipient, Domain does not exist, Unknown delivery failure).
3. **Filter - Only Bounced** → reads the `startups-nrw`, `munich-startups`, and `Scraped` sheet tabs in parallel, filtered by the bounced email.
4. **Search and Match Emails** (Code) — cross-references bounced addresses against all three sheets.
5. **Google Sheets - Update Output Column** — writes `Output = "not found"` back to whichever sheet contained the row.
6. **Delete a message** — deletes the bounce notification from Gmail after processing, then loops.

## `mail-sender.json`

**Workflow name:** "Startups-nrw" · **Trigger:** cron, 3×/day (`40 2,10,18 * * *`), or manual.

Sends personalized cold "Initiativbewerbung" (spontaneous application) emails to the startups scraped/discovered above, with a hardcoded CV inline, rate-limited to avoid spam flags.

1. **Extract CV Text** (Code) — contains the candidate's full CV as an inline template string.
2. **Google Sheets - Read Companies** (`startups-nrw` tab) → **Filter1** (Status ≠ "sent email") → **Limit** (max 30/run) → **Loop Over Items** → **Filter Not Sent** (double-check).
3. **Wait** (random 5–45 min jitter, plus a per-item wait).
4. **Generate email content** (Gemini `gemini-3-pro-preview`) — enforces: exactly one job title in the subject line (<60 chars), no placeholder brackets in the salutation ("Dear Hiring Team," if no contact name), ≤150-word conversational body avoiding AI-sounding phrases ("leverage", "synergy", "I am excited to").
5. **Parse Email Content** (Code) — parses the JSON `{subject, body}`.
6. **Download file** (Google Drive) — downloads a fixed CV PDF (`Fathi-BELMKADEM-CV-5.pdf`).
7. **Gmail - Send Email** (with the CV attached) → **Google Sheets - Update Status** (`Status = "sent email"`) → **Wait Between Emails** (15 min) → loops.

## `tailor cv+cover-letter__V2.json`

**Workflow name:** "Job Application Automator V2 (CV + Cover Letter)" · **Trigger:** webhook (`POST /webhook/auto-apply-v2`).

The backend for [`tailor cover letter/index.html`](tailor-cover-letter.md). Given a single job URL, scrapes the posting, generates a tailored CV and cover letter, compiles both to PDF via the [`latex-self-hosted`](latex-self-hosted.md) service, uploads them to Google Drive, and returns download links plus a suggested hiring-manager email. Unlike the other three workflows, this one is synchronous, single-job, and on-demand rather than batch/scheduled.

1. **Webhook Trigger** → **Verify JWT** (Code, Node `crypto`, HS256, hardcoded secret matching `index.html` — see the [hardening note](tailor-cover-letter.md#-known-hardening-item)) → **Is Authenticated?** → `401 Unauthorized` on failure, else continue.
2. **USER CONFIG** (Set) — the candidate's full resume text inline, `target_folder_id` (Google Drive), and `job_url` from the request body (with a `job_url_test` fallback for manual testing).
3. **Scrape Job (Jina)** — fetches the job page through `https://r.jina.ai/<job_url>` (Jina AI's read-and-clean scraping proxy, which converts pages to LLM-friendly markdown) → **Clean Scraped Data** (Code, regex-extracts title/company/markdown body) → guard nodes stop the run on a scrape failure.
4. **CV branch:**
   - **Get CV Template** (downloads `CV-Template.tex` from Drive) → extract/clean.
   - **Gemini - Tailor CV** (`gemini-3-pro-preview`) — a heavily constrained prompt: max 3 experience entries, 2 projects, 2 education lines, mandatory quantified metrics, XeLaTeX-safe rules, forbidden packages, output wrapped in `<<<LATEX_START>>>...<<<LATEX_END>>>` delimiters.
   - **Extract CV Code** (Code) — a LaTeX sanitizer: strips forbidden packages, force-replaces the header/preamble with a known-good hardcoded version regardless of what the AI produced, escapes `%`/`&`, clamps `\vspace`, normalizes quotes.
   - **Compile CV PDF** — HTTP POST to the Heroku `latex-self-hosted` deployment.
5. **Cover-letter branch (parallel):**
   - Get/extract/clean the cover-letter template.
   - **Message a model** (`gemini-3-pro-preview`) — fills the template and extracts a hiring-manager email, using `[LATEX_START]`/`[HIRING_EMAIL_START]` tagged output.
   - **Inject Content** (Code) — extracts LaTeX + hiring email from tags, repairs brackets/line breaks.
   - **Compile PDF** — HTTP POST to the Cloud Run `latex-self-hosted` deployment (a second deployment of the same service used for the CV).
6. **Merge & respond:** **Create Folder** (Google Drive, named `"{company} - {role}"`) → **Upload Cover Letter** + **Upload CV** → **Merge Uploads** → **Format Response** (Code — assembles `{status, message, folder_link, cover_letter: {drive_link, ...}, cv: {drive_link, ...}, hiring_message}`, optionally embedding base64 PDF content) → **Success Response** (`respondToWebhook`, JSON) — this exact shape is what `displaySuccess()` in `index.html` consumes.

## Notes

- `Automated workflows/~$German-Contacts.xlsx` is a Microsoft Office lock/temp file for a `German-Contacts.xlsx` that isn't checked into this snapshot — indicates that file is normally open/edited alongside these workflows.
- The root-level `client_secret_2_*.apps.googleusercontent.com.json` file is Google OAuth 2.0 client credentials, almost certainly backing the `googleSheetsOAuth2Api` / `googleDriveOAuth2Api` / `gmailOAuth2` credentials these workflows reference (Sheets, Drive, Gmail nodes) — not used by the Python pipelines, which authenticate via plain API keys instead.
