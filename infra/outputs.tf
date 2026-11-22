output "registry_name" {
  description = "Name of the container registry for vendor images"
  value       = azurerm_container_registry.vendors.name
}

output "registry_login_server" {
  description = "Address used to push and pull images"
  value       = azurerm_container_registry.vendors.login_server
}

output "portal_url" {
  description = "Public URL of the admissions portal"
  value       = module.portal.url
}


output "admin_token" {
  description = "Admin token shared by the vendor apps (for testing)"
  value       = random_password.admin_token.result
  sensitive   = true
}

output "ucas_url" {
  value = module.ucas.url
}

output "payments_url" {
  value = module.payments.url
}

output "events_url" {
  value = module.events.url
}
