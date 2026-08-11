enable_k8s_cluster    = true
enable_public_ingress = false

# Replace with your current public IP, for example: "203.0.113.10/32".
admin_ssh_cidr = "YOUR_PUBLIC_IP/32"

# Use your public SSH key only. Never put a private key here.
ssh_public_key = "ssh-ed25519 ..."

control_plane_instance_type = "t3.medium"
worker_instance_type        = "t3.medium"
worker_desired_capacity     = 1
