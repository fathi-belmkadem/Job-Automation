# Deployment Runbook — Kubernetes

Covers the three services now containerized and chart-managed: `XING/` (dashboard + pipeline), `join/` (dashboard + pipeline), and `latex-self-hosted/` (shared PDF compiler). `scrapers/startups.nrw` and the static `tailor cover letter/` page are not part of this yet — see [README.md](README.md) for what's deferred and why.

## Prerequisites

- Docker
- `kubectl`
- `helm` v3
- A Kubernetes cluster — `minikube` or [`kind`](https://kind.sigs.k8s.io/) for local validation; a real managed cluster (currently: GKE via [`terraform/`](../terraform/README.md)) once you're past that
- An `nginx-ingress` controller installed in the target cluster (only needed if `ingress.enabled: true`)
- A container registry the cluster can pull from — these instructions assume GHCR (`ghcr.io/<your-github-username>/job-automation-*`)

## 1. Local validation with `minikube`

```bash
minikube start

docker build -t job-automation-xing:dev ./XING
docker build -t job-automation-join:dev ./join
docker build -t job-automation-latex-compiler:dev ./latex-self-hosted

minikube image load job-automation-xing:dev
minikube image load job-automation-join:dev
minikube image load job-automation-latex-compiler:dev
```

(Using `kind` instead: `kind create cluster` then `kind load docker-image <image> --name kind` for each image.)

Bootstrap the secrets (see step 2), then:

```bash
helm install job-automation ./deploy/helm/job-automation \
  --set imageRegistry="" \
  --set xing.image.repository=job-automation-xing \
  --set join.image.repository=job-automation-join \
  --set latexCompiler.image.repository=job-automation-latex-compiler \
  --set imageTag=dev \
  -n job-automation --create-namespace

kubectl get pods -n job-automation -w
```

Once pods are `Running`:

```bash
kubectl port-forward -n job-automation svc/xing-dashboard 5000:5000
curl http://localhost:5000/healthz
```

## 2. Bootstrap secrets (per namespace, before first `helm install`)

None of these are created by the chart — Secrets are never templated from `values.yaml` so real credentials never land in a chart values file or git.

```bash
NS=job-automation   # or job-automation-staging / job-automation-prod
kubectl create namespace $NS --dry-run=client -o yaml | kubectl apply -f -

# API keys — copy XING/config/.env.example -> XING/config/.env, fill it in, then:
kubectl create secret generic xing-secrets --from-env-file=XING/config/.env -n $NS
kubectl create secret generic join-secrets --from-env-file=join/config/.env -n $NS

# Playwright login state — must be captured interactively (may involve
# solving a CAPTCHA/2FA), so this can't be automated in CI:
python XING/src/login.py    # writes XING/config/session.json
python join/src/login.py    # writes join/config/session.json
kubectl create secret generic xing-session --from-file=session.json=XING/config/session.json -n $NS
kubectl create secret generic join-session --from-file=session.json=join/config/session.json -n $NS

# Personal info (PII used to answer application form questions) — kept as a
# Secret rather than baked into the image or committed to git:
kubectl create secret generic xing-personal-info --from-file=personal_info.txt=XING/config/personal_info.txt -n $NS
kubectl create secret generic join-personal-info --from-file=personal_info.txt=join/config/personal_info.txt -n $NS

# Only needed if ingress.enabled: true — gates the dashboards, which have no
# authentication of their own, behind HTTP basic auth at the Ingress layer:
htpasswd -c auth <username>
kubectl create secret generic dashboard-basic-auth --from-file=auth -n $NS
```

`LATEX_COMPILER_URL` in a `.env` file you use for `--from-env-file` will typically say `http://localhost:5000` (the local-dev default) — this is harmless, the Deployment templates set `LATEX_COMPILER_URL=http://latex-compiler:5000` explicitly in-cluster and it overrides whatever the Secret contains.

## 2.5. Moving off minikube to a real cluster

Once local validation looks good, [`terraform/`](../terraform/README.md) provisions an actual GKE cluster (Autopilot). Nothing there has been applied — it's prep. When ready:

```bash
cd terraform/environments/gcp
cp terraform.tfvars.example terraform.tfvars   # fill in your project_id
terraform init && terraform apply
terraform output -raw get_credentials_command | bash   # points kubectl/helm at the new cluster
```

Then repeat steps 2 and 3 below against that cluster instead of minikube. The Terraform module is written so a future move to a different cloud only means adding a new module + environment there — see that README for the contract.

## 3. Deploy

```bash
# Staging
helm upgrade --install job-automation ./deploy/helm/job-automation \
  -f deploy/helm/job-automation/values.yaml \
  -f deploy/helm/job-automation/values-staging.yaml \
  -n job-automation-staging --create-namespace

# Prod
helm upgrade --install job-automation ./deploy/helm/job-automation \
  -f deploy/helm/job-automation/values.yaml \
  -f deploy/helm/job-automation/values-prod.yaml \
  -n job-automation-prod --create-namespace
```

Update `imageRegistry` in `values.yaml` (currently `ghcr.io/CHANGEME`) and the `*.ingress.host` placeholders in `values-staging.yaml`/`values-prod.yaml` before a real deploy.

## 4. CI/CD

[`​.github/workflows/ci-cd.yml`](../.github/workflows/ci-cd.yml) builds and Trivy-scans all three images on every push/PR, then:

- pushes to GHCR and deploys to `job-automation-staging` on push to `main`,
- pushes and deploys to `job-automation-prod` on a `v*` tag, gated by a GitHub **Environment** named `production` — configure required reviewers on that Environment in repo Settings → Environments so prod deploys need manual approval.

**`deploy-staging`/`deploy-prod` are currently skipped, not failed.** No cluster exists yet (still on minikube locally, per this doc), so each deploy job's `if:` checks whether its kubeconfig secret is actually set (`secrets.KUBECONFIG_STAGING != ''` / `secrets.KUBECONFIG_PROD != ''`) and no-ops otherwise. Add the secret when a real cluster exists (see [terraform/README.md](../terraform/README.md)) and the job starts running on its own — no workflow edit needed.

Required repo secrets, once ready: `KUBECONFIG_STAGING` and `KUBECONFIG_PROD` (base64-encoded kubeconfig for each cluster/context — `cat ~/.kube/config | base64` scoped to a service account with access to just that namespace, ideally). `GITHUB_TOKEN` is provided automatically for the GHCR push.

## Known limitations of this phase

- **Dashboard config edits don't persist in-cluster.** Locally, the dashboard's "Configuration Manager" writes `keywords.json`/prompts/`personal_info.txt` straight to disk. In the cluster, `keywords.json` and the prompt templates are baked into the image (config-as-code — edit the file, commit, redeploy), and `personal_info.txt` is a read-only Secret mount. Only `output/` (the job database and generated application PDFs) persists across pod restarts, via a PVC. If live-editable prompts/keywords matter in production, that needs a follow-up: point the dashboard's settings-write endpoint at the Kubernetes API (ConfigMap/Secret patch) instead of a local file write.
- **No cloud secrets manager yet.** Secrets are plain Kubernetes Secrets (base64, not encrypted unless the cluster has etcd encryption configured). Fine as a baseline; revisit with an External Secrets Operator + your cloud's secret manager once a provider is chosen.
- **`tailor cover letter/index.html`'s JWT secret is still hardcoded client-side** (flagged in [tailor-cover-letter.md](tailor-cover-letter.md)) — unrelated to this deployment work, still open.
- **Scrapers and the static tailoring page aren't containerized yet** — low-risk, deferred, same pattern applies whenever you want them added.
