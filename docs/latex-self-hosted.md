# LaTeX Self-Hosted Compilation Service

Location: [`latex-self-hosted/`](../latex-self-hosted)

A minimal Flask microservice that compiles arbitrary LaTeX source to PDF. It exists so the n8n cloud workflow (which has no local Docker/TeX access) can offload PDF rendering, and it's packaged for deployment to Heroku and/or Google Cloud Run.

## How it works

- **`app.py`** — single route `POST /compile`, accepting `{"latex_code": "..."}` JSON.
  1. Writes the code to `/tmp/<uuid>/document.tex`.
  2. Copies `profile.jpg` into the working directory (referenced by the CV template).
  3. Runs `xelatex -interaction=nonstopmode document.tex` **twice**. The first pass's exit code is intentionally ignored — TikZ `remember picture`/`overlay` leaves unresolved coordinates that make pass 1 "fail" even though it's required to produce the `.aux` file the second pass consumes. Only the second pass's result is checked.
  4. Returns the compiled PDF via `send_file`, or a `422` with the last 3000 characters of the `.log` file on failure.
  5. Listens on `$PORT` (default `5000`), `host=0.0.0.0`.
- **`Dockerfile`** — `python:3.11-slim` base; installs `texlive-latex-base/extra`, `texlive-fonts-recommended/extra`, `texlive-xetex`, and `fontconfig`; bakes in the Raleway font family (`fonts/*.ttf`) via `fc-cache`; copies `app.py` + `profile.jpg`; runs `python app.py`.
- **`test.py`** — a standalone client script (not an automated test suite) that POSTs a sample LaTeX document to a **deployed Heroku instance** and saves the response as `cv_test_result.pdf` — this is literally how the `cv_test_result.pdf` file in this folder was produced.
- **`requirements.txt`** — `flask`, `gunicorn` (production server for Heroku).

## Deployment

This same `app.py` is deployed **twice**, under two different hosts, for two different document types consumed by the [`tailor cv+cover-letter__V2` n8n workflow](automated-workflows.md#tailor-cvcover-letterv2json):

| Deployment | Used for |
|---|---|
| Heroku (`fathi-cv-compiler-*.herokuapp.com`) | CV compilation |
| Google Cloud Run (`latex-compiler-*.europe-west1.run.app`) | Cover letter compilation |

## External services

None as a caller — this service is purely a callee. The only dependency is the Docker/TeX Live toolchain baked into its own image.

## Environment variables

- `PORT` (defaults to `5000`)

## Running it locally

```bash
docker build -t latex-compiler .
docker run -p 5000:5000 latex-compiler
```

```bash
curl -X POST http://localhost:5000/compile \
  -H "Content-Type: application/json" \
  -d '{"latex_code": "\\documentclass{article}\\begin{document}Hello\\end{document}"}' \
  --output test.pdf
```
