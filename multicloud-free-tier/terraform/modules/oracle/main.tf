terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }
}

# Stub module: Oracle Cloud provisioning is not yet enabled in the API allowlist.
variable "shape" {
  type    = string
  default = "VM.Standard.E2.1.Micro"
}

variable "region" {
  type    = string
  default = "us-ashburn-1"
}
