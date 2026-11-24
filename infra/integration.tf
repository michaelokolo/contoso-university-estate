# Integration zone: messaging between vendors and university systems

locals {
  integration_tags = merge(local.tags, { zone = "integration" })
}

resource "azurerm_resource_group" "integration" {
  name     = "rg-contoso-integration"
  location = local.location
  tags     = local.integration_tags
}

resource "azurerm_servicebus_namespace" "integration" {
  name                = "sb-contoso-${random_string.suffix.result}"
  location            = azurerm_resource_group.integration.location
  resource_group_name = azurerm_resource_group.integration.name
  sku                 = "Standard"
  local_auth_enabled  = false
  minimum_tls_version = "1.2"
  tags                = local.integration_tags
}

resource "azurerm_servicebus_queue" "portal_applications" {
  name         = "portal-applications"
  namespace_id = azurerm_servicebus_namespace.integration.id

  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "P1D"

  lock_duration                        = "PT1M"
  max_delivery_count                   = 10
  dead_lettering_on_message_expiration = true
}
