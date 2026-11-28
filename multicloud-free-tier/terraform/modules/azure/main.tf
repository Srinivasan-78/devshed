terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.15"
    }
  }
}

# Stub module: Azure provisioning is not yet enabled in the API allowlist.
variable "vm_size" {
  type    = string
  default = "Standard_B1s"
}

variable "location" {
  type    = string
  default = "eastus"
}
