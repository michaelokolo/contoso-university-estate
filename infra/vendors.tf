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
