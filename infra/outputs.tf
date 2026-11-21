output "registry_name" {
  description = "Name of the container registry for vendor images"
  value       = azurerm_container_registry.vendors.name
}

output "registry_login_server" {
  description = "Address used to push and pull images"
  value       = azurerm_container_registry.vendors.login_server
}
