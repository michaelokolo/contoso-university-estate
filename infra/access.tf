# People who run integrations locally (DefaultAzureCredential signs in as them)

locals {
  developers = {
    michael = "e2dce1de-b959-4296-bd88-22ff79009709"
  }
}

resource "azurerm_role_assignment" "developer_sb_sender" {
  for_each = local.developers

  scope                = azurerm_servicebus_queue.portal_applications.id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = each.value
  principal_type       = "User"
}
