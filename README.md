# Job-Automation

![CI/CD](https://github.com/fathi-belmkadem/Job-Automation/actions/workflows/ci-cd.yml/badge.svg)

An end-to-end automated job-search system: AI-driven pipelines that discover, filter, and apply to jobs on XING and join.com, a shared LaTeX PDF-compiler service, n8n workflows for cold-outreach (contact discovery, cleanup, cold email), and a Kubernetes deployment (Helm + Terraform + GitHub Actions CI/CD) for running it all as a real service instead of local scripts.

## What's in here

| Piece | What it does |
|---|---|
| [`XING/`](XING) | Harvest → AI-filter → enrich → classify → apply pipeline for XING.com, with a Flask dashboard |
| [`join/`](join) | Same idea for join.com — search-engine-based discovery, multi-AI-provider support |
| [`latex-self-hosted/`](latex-self-hosted) | Shared Flask/TeX Live service that compiles tailored CVs and cover letters to PDF |
| [`Automated workflows/`](Automated%20workflows) | n8n workflows: company/contact discovery, bounce cleanup, cold-email sending, on-demand CV+cover-letter tailoring |
| [`scrapers/startups.nrw/`](scrapers/startups.nrw) | Contact-harvesting scraper feeding the cold-outreach workflows |
| [`tailor cover letter/`](tailor%20cover%20letter) | Static front-end for the on-demand tailoring webhook |
| [`deploy/helm/job-automation/`](deploy/helm/job-automation) | Kubernetes Helm chart for the three containerized services |
| [`terraform/`](terraform) | GKE cluster provisioning (prep only — nothing applied yet) |
| [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) | Build → security-scan → push → deploy pipeline |

## Documentation

- **[docs/README.md](docs/README.md)** — documentation index, with a diagram of how every piece connects
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — full technical deep-dive: every technology in the stack, the AI integration, containerization and Kubernetes design, CI/CD, and the security posture
- **[docs/deployment.md](docs/deployment.md)** — step-by-step deployment runbook (local → staging → prod)
- Per-module docs: [xing.md](docs/xing.md) · [join.md](docs/join.md) · [latex-self-hosted.md](docs/latex-self-hosted.md) · [scrapers.md](docs/scrapers.md) · [tailor-cover-letter.md](docs/tailor-cover-letter.md) · [automated-workflows.md](docs/automated-workflows.md)
- **[terraform/README.md](terraform/README.md)** — cluster provisioning and the multi-cloud module pattern

## Quick start

Each Python pipeline is self-contained — see its own doc for setup. The short version:

```bash
# XING pipeline
cd XING && pip install -r requirements.txt && playwright install chromium
python src/main_pipeline.py

# join.com pipeline
cd join && pip install -r requirements.txt && python -m playwright install chromium
python src/main_pipeline.py --all

# LaTeX compiler service (required by both pipelines)
cd latex-self-hosted && docker build -t latex-compiler . && docker run -p 5000:5000 latex-compiler
```

Both pipelines need a `config/.env` (see each module's `.env.example`) and Docker running for the LaTeX service — locally, or already deployed and pointed at via `LATEX_COMPILER_URL`.

For the Kubernetes path (local `minikube` validation up through a real cluster), start with [docs/deployment.md](docs/deployment.md).

## Status

Personal project, active development. Currently runs on local `minikube` for K8s validation — no cloud cluster is provisioned yet (Terraform is prepared but not applied). CI builds, security-scans, and pushes all three service images on every push to `main`; deployment jobs are wired up and will start running automatically once a real cluster and its kubeconfig secret exist.

**Known open item:** the JWT secret used by [`tailor cover letter/index.html`](tailor%20cover%20letter/index.html) is currently hardcoded client-side — see [docs/tailor-cover-letter.md](docs/tailor-cover-letter.md) for details.
