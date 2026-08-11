locals {
  name_prefix = "${var.owner}-${var.project_name}-${terraform.workspace}"
  azs         = slice(data.aws_availability_zones.available.names, 0, 2)

  default_public_hostnames = {
    agent    = "api-${terraform.workspace}.${var.domain_name}"
    frontend = "ai-${terraform.workspace}.${var.domain_name}"
    landing  = "app-${terraform.workspace}.${var.domain_name}"
    grafana  = "grafana-${terraform.workspace}.${var.domain_name}"
  }

  public_hostnames = length(var.public_hostnames_override) > 0 ? var.public_hostnames_override : local.default_public_hostnames

  common_tags = {
    Project   = "DialedIN"
    Service   = "DialChat"
    ManagedBy = "Terraform"
    Owner     = var.owner
    Workspace = terraform.workspace
  }
}
