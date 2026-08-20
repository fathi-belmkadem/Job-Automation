terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Uncomment and fill in once you have a GCS bucket for state — a local
  # backend is fine to start, but a shared/"small team" target should not
  # keep Terraform state only on one person's machine.
  # backend "gcs" {
  #   bucket = "CHANGEME-job-automation-tfstate"
  #   prefix = "gcp/job-automation"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "gke" {
  source = "../../modules/gke"

  project_id      = var.project_id
  region          = var.region
  cluster_name    = var.cluster_name
  environment     = var.environment
  release_channel = var.release_channel
}
