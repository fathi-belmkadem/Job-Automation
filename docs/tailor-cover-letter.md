# Tailor Cover Letter — On-Demand Trigger UI

Location: [`tailor cover letter/index.html`](../tailor%20cover%20letter/index.html)

A single static HTML page (Tailwind via CDN, vanilla JS, no build step) that acts as the front-end for the [`tailor cv+cover-letter__V2` n8n webhook workflow](automated-workflows.md#tailor-cvcover-letterv2json). It is not itself a tailoring engine — it just collects a job URL, authenticates the request, sends it to the workflow, and renders the results.

## How it works

1. **JWT generation (`generateJWT(payload)`)** — builds an HS256 JWT entirely client-side using the browser's native `window.crypto.subtle` HMAC-SHA256, signed with a hardcoded secret, with `iat`/`exp` (1 hour) claims and `role: "admin"`.
2. **Submit (`handleApply(event)`)** — on form submit, generates the JWT and POSTs `{ job_url }` as a Bearer-authenticated JSON request to the n8n webhook (`https://n8n.kinetrack.app/webhook/auto-apply-v2`).
3. **Results (`displaySuccess(data)`)** — on a 2xx response, populates a results panel:
   - status message and company/job-title summary,
   - "Cover Letter" and "Tailored CV" download buttons, linked to `data.cover_letter.drive_link` / `data.cv.drive_link` (Google Drive links produced by the workflow's "Format Response" node),
   - a "Hiring Email" text block (`data.hiring_message`) with a copy-to-clipboard button.

The rest is presentational: Tailwind utility classes, inline SVG icons, a CSS fade-in-up animation.

## External services

Only the n8n webhook at `n8n.kinetrack.app`. No direct AI or Google API calls happen from this page.

## ⚠️ Known hardening item

The JWT-signing secret is embedded in plaintext in this file's JavaScript, viewable by anyone who loads the page or its source. The exact same secret is duplicated server-side in the `tailor cv+cover-letter__V2.json` workflow's "Verify JWT" node — meaning this page is effectively both the client *and* the API key for that webhook. Anyone who reads the page source can forge valid tokens and call the webhook directly, bypassing the UI entirely.

This has not been fixed as part of this documentation pass — flagging it here as something to address (e.g. move JWT issuance to a small server-side endpoint, or gate the page itself behind auth) rather than leaving the shared secret in client-visible code.
