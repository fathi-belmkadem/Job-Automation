# --- Module contract ---
# Any future cloud module (modules/eks/, modules/aks/, ...) should expose
# these same four outputs, named identically, so environments/<cloud>/outputs.tf
# and the CI/CD deploy step don't need to change shape when the cloud changes —
# only which module gets called does. See terraform/README.md.

output "cluster_name" {
  value = google_container_cluster.this.name
}

output "endpoint" {
  description = "Cluster API server endpoint."
  value       = google_container_cluster.this.endpoint
  sensitive   = true
}

output "ca_certificate" {
  description = "Base64-encoded cluster CA certificate."
  value       = google_container_cluster.this.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "location" {
  value = google_container_cluster.this.location
}

# GCP-specific convenience output — not part of the cross-cloud contract above,
# just the simplest way to actually get a working kubeconfig for this cloud.
output "get_credentials_command" {
  description = "Run this to populate your local kubeconfig for this cluster."
  value       = "gcloud container clusters get-credentials ${google_container_cluster.this.name} --region ${google_container_cluster.this.location} --project ${var.project_id}"
}
