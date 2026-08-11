# Copy this file to personal-dev.tfvars and fill values for Ahmad's own AWS account.
# Do not commit personal-dev.tfvars if it contains private or account-specific secrets.

region       = "us-east-1"
owner        = "ahmadry98"
project_name = "dialin"

# Safe for a dev account where media can be recreated. Keep false for prod.
force_destroy_media_bucket    = true
force_delete_ecr_repositories = false

allowed_media_upload_origins = [
  "http://localhost:3000",
  "http://127.0.0.1:3000"
  # Add personal-dev web/mobile origins after the domain/API is chosen.
]

# Start with storage/ECR only. Enable Kubernetes after S3/DynamoDB/ECR work.
enable_k8s_cluster    = false
enable_public_ingress = false

# Required only when enable_k8s_cluster=true.
# admin_ssh_cidr = "YOUR_PUBLIC_IP/32"
# ssh_public_key = "ssh-ed25519 ..."

# Optional if you use a different domain in your personal account.
# domain_name = "example.com"
