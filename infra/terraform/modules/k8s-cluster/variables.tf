variable "name_prefix" {
  description = "Prefix applied to cluster resource names"
  type        = string
}

variable "region" {
  description = "AWS region containing the cluster"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for cluster resources"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR permitted for internal cluster traffic"
  type        = string
}

variable "public_subnet_ids" {
  description = "Two public subnet IDs used by the control plane and workers"
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_ids) == 2
    error_message = "Exactly two public subnet IDs are required."
  }
}

variable "ubuntu_ami_id" {
  description = "Canonical Ubuntu 24.04 AMI ID for the selected region"
  type        = string
}

variable "kubernetes_minor_version" {
  description = "Kubernetes and CRI-O repository stream"
  type        = string
}

variable "pod_cidr" {
  description = "Kubernetes Pod network CIDR"
  type        = string
}

variable "control_plane_instance_type" {
  description = "EC2 type for the control plane"
  type        = string
}

variable "enable_cluster_autoscaler" {
  description = "Whether the worker role and ASG are configured for Cluster Autoscaler"
  type        = bool
  default     = false
}

variable "worker_instance_type" {
  description = "EC2 type for ASG workers"
  type        = string
}

variable "worker_desired_capacity" {
  description = "Desired ASG capacity from zero through three"
  type        = number

  validation {
    condition     = var.worker_desired_capacity >= 0 && var.worker_desired_capacity <= 3
    error_message = "Worker desired capacity must be between zero and three."
  }
}

variable "admin_ssh_cidr" {
  description = "Administrator CIDR permitted to SSH to the control plane"
  type        = string
}

variable "ssh_public_key" {
  description = "OpenSSH public key registered in EC2"
  type        = string
  sensitive   = true
}

variable "application_s3_bucket" {
  description = "S3 bucket used by DialedIN workloads"
  type        = string
}

variable "dynamodb_table_arns" {
  description = "DynamoDB tables used by DialedIN runtime workloads."
  type        = list(string)
  default     = []
}

variable "alert_sns_topic_arn" {
  description = "SNS topic to which Alertmanager may publish notifications"
  type        = string
}

variable "tags" {
  description = "Tags applied to module resources"
  type        = map(string)
  default     = {}
}
