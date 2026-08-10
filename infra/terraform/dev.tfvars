region = "us-east-1"

force_destroy_media_bucket = true

allowed_media_upload_origins = [
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "http://192.168.68.101:3000",
  "https://app-dev.fursa.click",
  "https://ai-dev.fursa.click"
]


# Optional Checkpoint 25 EC2 Kubernetes cluster.
# enable_k8s_cluster   = true
# enable_public_ingress = false
# admin_ssh_cidr       = "YOUR_PUBLIC_IP/32"
# ssh_public_key        = "ssh-ed25519 ..."
