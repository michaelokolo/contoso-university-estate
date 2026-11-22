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

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}


# Secrets: generated once by Terraform, stored in state, reused on every apply

resource "random_password" "admin_token" {
  length  = 32
  special = false
}

resource "random_password" "webhook_secret" {
  length  = 32
  special = false
}

resource "random_password" "portal_api_key" {
  length  = 32
  special = false
}

resource "random_password" "ucas_provider_key" {
  length  = 32
  special = false
}

resource "random_password" "payments_secret_key" {
  length  = 32
  special = false
}

resource "random_password" "events_client_secret" {
  length  = 32
  special = false
}

# Vendor apps

module "portal" {
  source = "./modules/container-app"

  name                  = "portal"
  resource_group_name   = azurerm_resource_group.vendors.name
  location              = azurerm_resource_group.vendors.location
  environment_id        = azurerm_container_app_environment.vendors.id
  registry_id           = azurerm_container_registry.vendors.id
  registry_login_server = azurerm_container_registry.vendors.login_server
  image                 = "portal:v1"
  tags                  = local.tags

  secrets = {
    "api-key"        = random_password.portal_api_key.result
    "admin-token"    = random_password.admin_token.result
    "webhook-secret" = "whsec_${random_password.webhook_secret.result}"
  }

  secret_env = {
    PORTAL_API_KEY = "api-key"
    ADMIN_TOKEN    = "admin-token"
    WEBHOOK_SECRET = "webhook-secret"
  }
}


module "ucas" {
  source = "./modules/container-app"

  name                  = "ucas"
  resource_group_name   = azurerm_resource_group.vendors.name
  location              = azurerm_resource_group.vendors.location
  environment_id        = azurerm_container_app_environment.vendors.id
  registry_id           = azurerm_container_registry.vendors.id
  registry_login_server = azurerm_container_registry.vendors.login_server
  image                 = "ucas:v1"
  tags                  = local.tags

  secrets = {
    "provider-key" = random_password.ucas_provider_key.result
    "admin-token"  = random_password.admin_token.result
  }

  secret_env = {
    UCAS_PROVIDER_KEY = "provider-key"
    ADMIN_TOKEN       = "admin-token"
  }
}

module "payments" {
  source = "./modules/container-app"

  name                  = "payments"
  resource_group_name   = azurerm_resource_group.vendors.name
  location              = azurerm_resource_group.vendors.location
  environment_id        = azurerm_container_app_environment.vendors.id
  registry_id           = azurerm_container_registry.vendors.id
  registry_login_server = azurerm_container_registry.vendors.login_server
  image                 = "payments:v1"
  tags                  = local.tags

  env = {
    PUBLIC_URL = "https://ca-payments.${azurerm_container_app_environment.vendors.default_domain}"
  }

  secrets = {
    "secret-key"     = "sk_test_${random_password.payments_secret_key.result}"
    "admin-token"    = random_password.admin_token.result
    "webhook-secret" = "whsec_${random_password.webhook_secret.result}"
  }

  secret_env = {
    PAYMENTS_SECRET_KEY = "secret-key"
    ADMIN_TOKEN         = "admin-token"
    WEBHOOK_SECRET      = "webhook-secret"
  }
}

module "events" {
  source = "./modules/container-app"

  name                  = "events"
  resource_group_name   = azurerm_resource_group.vendors.name
  location              = azurerm_resource_group.vendors.location
  environment_id        = azurerm_container_app_environment.vendors.id
  registry_id           = azurerm_container_registry.vendors.id
  registry_login_server = azurerm_container_registry.vendors.login_server
  image                 = "events:v1"
  tags                  = local.tags

  env = {
    EVENTS_CLIENT_ID = "contoso-university"
  }

  secrets = {
    "client-secret"  = random_password.events_client_secret.result
    "admin-token"    = random_password.admin_token.result
    "webhook-secret" = "whsec_${random_password.webhook_secret.result}"
  }

  secret_env = {
    EVENTS_CLIENT_SECRET = "client-secret"
    ADMIN_TOKEN          = "admin-token"
    WEBHOOK_SECRET       = "webhook-secret"
  }
}
