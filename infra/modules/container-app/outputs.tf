output "fqdn" {
  description = "Public hostname of the container app"
  value       = azurerm_container_app.this.ingress[0].fqdn
}

output "url" {
  description = "Public HTTPS URL of the container app"
  value       = "https://${azurerm_container_app.this.ingress[0].fqdn}"
}

output "identity_principal_id" {
  description = "Principal ID of the app's managed identity, for granting it roles"
  value       = azurerm_user_assigned_identity.this.principal_id
}


