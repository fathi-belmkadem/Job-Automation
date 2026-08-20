# Scrapers — NRW Startup Directory

Location: [`scrapers/startups.nrw/`](../scrapers/startups.nrw)

A one-off Playwright scraper that harvests company/contact data from [startups.nrw](https://www.startups.nrw/organizations/startups), a directory of NRW-region (North Rhine-Westphalia, Germany) startups. Its output feeds the cold-outreach side of this project: the column shape (Company Name, Description, Email, Website) matches exactly what the [`Remove-Bounced-Email`](automated-workflows.md#remove-bounced-emailjson) and [`mail-sender`](automated-workflows.md#mail-senderjson) n8n workflows read from the `startups-nrw` Google Sheet tab.

## How it works

`startup_scraper/scraper.py` (synchronous Playwright, `headless=False`):

- **`scrape_list(page)`** — navigates to the listing page, dismisses the cookie banner ("Accept All"), infinite-scrolls until page height stops growing (capped at 1,000,000px), and collects every detail-page link (`a.flex.flex-col.p-5.w-full`).
- **`scrape_details(page, url)`** — for each startup's detail page, extracts:
  - Company Name (`span.font-semibold.text-gray-700`, falling back to a `p` tag)
  - Description (joins all `span.font-normal.text-gray-500...` text nodes)
  - Email (`a[href^="mailto:"]`)
  - Website (first external link that isn't a social/media/maps domain)
  - Contact Name — left blank; the site's markup for this field is inconsistent enough that it wasn't reliably scrapable.
- **`main()`** — orchestrates the list scrape, loops through detail scraping, and writes everything to `startups_nrw.csv`.

## Files

- `startup_scraper/scraper.py` — the scraper itself.
- `startups-urls.txt` — 31 pre-collected detail-page URLs (a manual seed list or leftover from a partial run).
- `startups_nrw.csv` — scrape output: ~1,847 companies with Company Name / Description / Email / Website columns (Contact Name present but empty in sampled rows).
- `startup_scraper/requirements.txt` — `playwright`, `pandas`.

## External services

startups.nrw (target site) only — no AI/API calls.

## Running it

```bash
pip install -r requirements.txt
playwright install chromium
python scraper.py
```
