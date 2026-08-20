variable "project_id" {
  description = "GCP project ID the cluster is created in."
  type        = string
}

variable "region" {
  description = "GCP region for the cluster (Autopilot clusters are regional)."
  type        = string
  default     = "europe-west3" # Frankfurt — closest to the DACH-region job targets in this project's prompts
}

variable "cluster_name" {
  description = "Name of the GKE cluster."
  type        = string
  default     = "job-automation"
}

variable "environment" {
  description = "Environment label (staging | prod) — applied as a resource label, not a separate cluster by default."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "environment must be \"staging\" or \"prod\"."
  }
}

variable "release_channel" {
  description = "GKE release channel."
  type        = string
  default     = "REGULAR"
}

variable "manage_apis" {
  description = "Whether this module should enable the required GCP APIs itself. Set false if your project already has them enabled and this identity lacks Service Usage Admin."
  type        = bool
  default     = true
}

