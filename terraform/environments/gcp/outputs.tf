output "cluster_name" {
  value = module.gke.cluster_name
}

output "location" {
  value = module.gke.location
}

output "get_credentials_command" {
  value = module.gke.get_credentials_command
}
