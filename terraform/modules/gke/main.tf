terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

locals {
  required_apis = [
    "container.googleapis.com",
    "compute.googleapis.com",
  ]
}

resource "google_project_service" "required" {
  for_each = var.manage_apis ? toset(local.required_apis) : []

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Autopilot — Google manages nodes/scaling/security patching, which fits a
# project this size much better than hand-tuning a node pool.
resource "google_container_cluster" "this" {
  name     = var.cluster_name
  project  = var.project_id
  location = var.region

  enable_autopilot = true

  release_channel {
    channel = var.release_channel
  }

  resource_labels = {
    app         = "job-automation"
    environment = var.environment
    managed-by  = "terraform"
  }

  # Autopilot clusters manage their own default node pool; deleting the
  # placeholder default_node_pool block Terraform would otherwise expect
  # is unnecessary here since enable_autopilot handles that.

  deletion_protection = var.environment == "prod"

  depends_on = [google_project_service.required]
}
