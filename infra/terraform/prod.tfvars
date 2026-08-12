region       = "us-east-1"
owner        = "ahmadry98"
project_name = "dialedin"

# Production keeps its own media, profile, and shot-history resources through the prod workspace.
force_destroy_media_bucket    = false
force_delete_ecr_repositories = false

# ECR images are shared across environments; runtime data is not.
manage_ecr_repositories     = false
manage_github_oidc_provider = false
github_actions_role_name    = "DialedInGitHubActionsProdRole"

# GoDaddy manages dialedin.me DNS, so Terraform must not create Route 53 records.
domain_name                 = "dialedin.me"
enable_k8s_cluster          = true
enable_public_ingress       = true
public_ingress_manage_dns   = false
public_ingress_enable_https = true
# First apply creates the ACM certificate. Keep false until its GoDaddy CNAME validates.
public_ingress_enable_https_listener = true
public_hostnames_override = {
  agent    = "api.dialedin.me"
  frontend = "ai.dialedin.me"
}

# Deliberately separate network ranges from personal-dev.
vpc_cidr            = "10.30.0.0/16"
public_subnet_cidrs = ["10.30.1.0/24", "10.30.2.0/24"]
pod_cidr            = "192.169.0.0/16"

# Put personal-only access values in prod.local.tfvars (ignored by Git).
# admin_ssh_cidr = "YOUR_PUBLIC_IP/32"
# ssh_public_key  = "ssh-ed25519 ..."
alert_email = "support@dialedin.me"

allowed_media_upload_origins = ["https://ai.dialedin.me"]
