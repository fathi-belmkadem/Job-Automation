variable "project_id" {
  description = "GCP project ID to deploy into. No default — set this in terraform.tfvars."
  type        = string
}

variable "region" {
  type    = string
  default = "europe-west3"
}

variable "cluster_name" {
  type    = string
  default = "job-automation"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "release_channel" {
  type    = string
  default = "REGULAR"
}
