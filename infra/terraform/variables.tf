variable "region" {
  description = "AWS region for DialedIN infrastructure."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.region))
    error_message = "The region must look like us-east-1."
  }
}

variable "owner" {
  description = "Owner prefix used in resource names and tags."
  type        = string
  default     = "ahmadry98"
}

variable "project_name" {
  description = "Short project name used in resource names."
  type        = string
  default     = "dialedin"
}

variable "force_destroy_media_bucket" {
  description = "Allow Terraform to delete non-empty dev media buckets. Keep false for production."
  type        = bool
  default     = false
}

variable "ecr_repository_names" {
  description = "ECR repositories created for DialedIN Docker images."
  type        = list(string)
  default = [
    "dialedin-fursa-agent",
    "dialedin-fursa-espresso-mcp",
    "dialedin-fursa-frontend",
    "dialedin-backend",
    "dialedin-landing"
  ]
}

variable "force_delete_ecr_repositories" {
  description = "Allow Terraform to delete non-empty ECR repositories. Keep false for production."
  type        = bool
  default     = false
}

variable "manage_ecr_repositories" {
  description = "Whether this workspace creates ECR repositories. Production reuses the reviewed repositories created by dev."
  type        = bool
  default     = true
}



variable "manage_github_oidc_provider" {
  description = "Whether this workspace creates the account-level GitHub Actions OIDC provider. Only one provider can exist per AWS account."
  type        = bool
  default     = true
}

variable "github_actions_role_name" {
  description = "IAM role name assumed by GitHub Actions through OIDC."
  type        = string
  default     = "DialedInGitHubActionsRole"
}

variable "github_actions_repositories" {
  description = "GitHub repositories allowed to assume the GitHub Actions OIDC role on main/dev branches."
  type        = list(string)
  default = [
    "ahmadry98/DialedIn-Fursa",
    "ahmadry98/dialin-app",
    "ahmadry98/dialedin-landing"
  ]
}

variable "allowed_media_upload_origins" {
  description = "Browser origins allowed to PUT media through presigned S3 URLs. Keep this narrow in production."
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
  ]
}


variable "enable_k8s_cluster" {
  description = "Create the EC2 kubeadm Kubernetes cluster. Keep false for normal storage-only applies."
  type        = bool
  default     = false
}

variable "enable_public_ingress" {
  description = "Create Route 53, ACM, and ALB ingress for the Kubernetes cluster. Requires enable_k8s_cluster."
  type        = bool
  default     = false
}

variable "public_ingress_manage_dns" {
  description = "Create Route 53 DNS and ACM validation records for public ingress. Disable when the domain is managed outside Route 53."
  type        = bool
  default     = true
}

variable "public_ingress_enable_https" {
  description = "Create an HTTPS ALB listener with ACM. Disable for external-DNS dev smoke tests until a certificate is validated."
  type        = bool
  default     = true
}

variable "public_ingress_enable_https_listener" {
  description = "Whether the HTTPS listener is enabled. Set false for the first external-DNS apply, validate ACM, then set true."
  type        = bool
  default     = true
}

variable "domain_name" {
  description = "Existing public Route 53 hosted zone used for public Kubernetes endpoints."
  type        = string
  default     = "fursa.click"
}

variable "public_hostnames_override" {
  description = "Optional explicit public hostnames keyed by service name, for example { agent = \"api-dev.dialedin.me\" }."
  type        = map(string)
  default     = {}
}

variable "vpc_cidr" {
  description = "IPv4 CIDR for the optional Kubernetes VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Two public subnet CIDRs in separate Availability Zones for the optional Kubernetes cluster."
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly two public subnet CIDRs are required."
  }
}

variable "pod_cidr" {
  description = "Kubernetes Pod network CIDR passed to kubeadm and Calico."
  type        = string
  default     = "192.168.0.0/16"
}

variable "kubernetes_minor_version" {
  description = "Pinned Kubernetes and CRI-O minor repository stream."
  type        = string
  default     = "v1.35"
}

variable "control_plane_instance_type" {
  description = "EC2 instance type for the kubeadm control plane."
  type        = string
  default     = "t3.medium"
}

variable "worker_instance_type" {
  description = "EC2 instance type used by the worker launch template."
  type        = string
  default     = "t3.medium"
}

variable "worker_desired_capacity" {
  description = "Desired number of worker instances; zero enables idle mode."
  type        = number
  default     = 1

  validation {
    condition     = var.worker_desired_capacity >= 0 && var.worker_desired_capacity <= 3
    error_message = "Worker desired capacity must be between 0 and 3."
  }
}

variable "admin_ssh_cidr" {
  description = "Administrator IPv4 CIDR allowed to SSH to the control plane when Kubernetes is enabled."
  type        = string
  default     = "127.0.0.1/32"

  validation {
    condition     = can(cidrhost(var.admin_ssh_cidr, 0))
    error_message = "admin_ssh_cidr must be a valid IPv4 CIDR."
  }
}

variable "ssh_public_key" {
  description = "OpenSSH public key registered as the cluster EC2 key pair when Kubernetes is enabled."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition     = !var.enable_k8s_cluster || startswith(var.ssh_public_key, "ssh-")
    error_message = "ssh_public_key must be an OpenSSH public key when enable_k8s_cluster is true."
  }
}

variable "alert_email" {
  description = "Email address subscribed to optional infrastructure alerts."
  type        = string
  default     = "support@dialedin.me"

  validation {
    condition     = can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}

variable "enable_cluster_autoscaler" {
  description = "Whether to configure the worker ASG for the optional Cluster Autoscaler."
  type        = bool
  default     = false
}

variable "ingress_http_node_port" {
  description = "Fixed ingress-nginx HTTP NodePort targeted by the ALB."
  type        = number
  default     = 30080

  validation {
    condition     = var.ingress_http_node_port >= 30000 && var.ingress_http_node_port <= 32767
    error_message = "ingress_http_node_port must be within the Kubernetes NodePort range."
  }
}
