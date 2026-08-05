locals {
  name_prefix = "${var.owner}-${var.project_name}-${terraform.workspace}"

  common_tags = {
    Project   = "DialedIN"
    Service   = "DialChat"
    ManagedBy = "Terraform"
    Owner     = var.owner
    Workspace = terraform.workspace
  }
}
