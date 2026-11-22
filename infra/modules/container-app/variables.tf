variable "name" {
  description = "Short name of the app, e.g. portal"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to create the app in"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "environment_id" {
  description = "ID of the Container Apps environment"
  type        = string
}

variable "registry_id" {
  description = "ID of the container registry (for the AcrPull role)"
  type        = string
}

variable "registry_login_server" {
  description = "Registry address, e.g. acrcontoso3isekg.azurecr.io"
  type        = string
}

variable "image" {
  description = "Image name and tag in the registry, e.g. portal:v1"
  type        = string
}

variable "secrets" {
  description = "Secret values, keyed by secret name"
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "env" {
  description = "Plain environment variables, keyed by variable name"
  type        = map(string)
  default     = {}
}

variable "secret_env" {
  description = "Environment variables that come from secrets: variable name => secret name"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags for every resource"
  type        = map(string)
  default     = {}
}
