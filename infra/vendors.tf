locals {
  location = "uksouth"

  tags = {
    project    = "contoso-estate"
    zone       = "vendors"
    managed_by = "terraform"
  }
}

resource "azurerm_resource_group" "vendors" {
  name     = "rg-contoso-vendors"
  location = local.location
  tags     = local.tags
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_container_registry" "vendors" {
  name                = "acrcontoso${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.vendors.name
  location            = azurerm_resource_group.vendors.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.tags
}

resource "azurerm_log_analytics_workspace" "vendors" {
  name                = "log-contoso-vendors"
  location            = azurerm_resource_group.vendors.location
  resource_group_name = azurerm_resource_group.vendors.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_container_app_environment" "vendors" {
  name                       = "cae-contoso-vendors"
  location                   = azurerm_resource_group.vendors.location
  resource_group_name        = azurerm_resource_group.vendors.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.vendors.id
  tags                       = local.tags
}
