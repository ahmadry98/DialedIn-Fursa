variable "domain_name" {
  description = "Public DNS suffix covered by the ingress certificate"
  type        = string
}

variable "enable_https" {
  description = "Whether to create an HTTPS listener and ACM certificate."
  type        = bool
  default     = true
}

variable "enable_https_listener" {
  description = "Whether to expose the HTTPS listener after the certificate is validated."
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "Optional existing ACM certificate ARN for the HTTPS listener."
  type        = string
  default     = null
}

variable "manage_dns" {
  description = "Whether Terraform manages Route 53 records for hostnames and ACM validation."
  type        = bool
  default     = true
}

variable "hosted_zone_id" {
  description = "ID of the existing Route 53 hosted zone"
  type        = string
  default     = null
}

variable "http_node_port" {
  description = "Fixed ingress-nginx HTTP NodePort"
  type        = number
}

variable "name_prefix" {
  description = "Prefix applied to ingress infrastructure resource names"
  type        = string
}

variable "public_hostnames" {
  description = "Public DNS names routed to the application load balancer"
  type        = map(string)
}

variable "public_subnet_ids" {
  description = "Public subnets in which the application load balancer is created"
  type        = list(string)
}

variable "tags" {
  description = "Tags applied to ingress infrastructure resources"
  type        = map(string)
  default     = {}
}

variable "vpc_id" {
  description = "VPC containing the cluster workers"
  type        = string
}

variable "worker_asg_name" {
  description = "Worker Auto Scaling Group attached to the target group"
  type        = string
}

variable "worker_security_group_id" {
  description = "Security group attached to worker instances"
  type        = string
}
