# Terraform — cluster infrastructure

This provisions the **Kubernetes cluster only**. Everything that runs on top of it (the three services, PVCs, CronJobs, Ingress) is deployed separately via the Helm chart at [`deploy/helm/job-automation/`](../deploy/helm/job-automation/) — that chart is already cloud-agnostic and doesn't change when the cluster's cloud changes. Terraform's job stops at "here's a working cluster and a way to get its kubeconfig."

## Layout

```
terraform/
├── modules/
│   └── gke/              # concrete, working GCP module
└── environments/
    └── gcp/               # root config that calls modules/gke
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        └── terraform.tfvars.example
```

Only GCP is implemented right now, matching the current target (you already have `gcloud` set up). Nothing here has been applied — this is prep, not a live cluster.

## The module contract — how a future cloud swap stays cheap

`modules/gke/outputs.tf` exposes four outputs: `cluster_name`, `endpoint`, `ca_certificate`, `location`. That's the contract. If you later move to AWS or Azure:

1. Create `modules/eks/` (or `modules/aks/`) exposing the **same four output names**, backed by that cloud's cluster resource (`aws_eks_cluster`, `azurerm_kubernetes_cluster`, ...).
2. Create `environments/aws/` (or `environments/azure/`) mirroring `environments/gcp/`'s structure — same `main.tf`/`variables.tf`/`outputs.tf` shape, just pointing at the new module and that cloud's provider block.
3. Nothing in the Helm chart, the CI/CD workflow's deploy steps, or `docs/deployment.md` needs to change — they all just need *a* kubeconfig pointed at *a* cluster; they don't care which cloud produced it.

Deliberately not building unused AWS/Azure modules now — untested infra code for a cloud you're not using is a maintenance liability, not preparation. The contract above is what makes adding one later a bounded, well-defined task instead of a redesign.

## Usage (when you're ready to move off minikube)

```bash
cd terraform/environments/gcp
cp terraform.tfvars.example terraform.tfvars   # fill in your project_id
terraform init
terraform plan
terraform apply
```

Then, to point `kubectl`/`helm` at the new cluster:

```bash
terraform output -raw get_credentials_command | bash
```

From there, follow [docs/deployment.md](../docs/deployment.md) starting at "Bootstrap secrets" — that part is identical regardless of which cloud the cluster came from.

## State

No remote backend is configured yet — Terraform state defaults to a local `terraform.tfstate` file (gitignored, never commit it). `main.tf` has a commented-out `backend "gcs"` block; uncomment and point it at a bucket before more than one person runs `terraform apply` against this, or state gets out of sync between machines.

## Cost note

The GKE module uses **Autopilot** — Google manages nodes/scaling, and you pay per-pod-resource rather than per-node, which is a better fit for a project this size than a manually-sized node pool. Still a real cost once applied (not free-tier) — nothing here runs or bills anything until you run `terraform apply`.
