output "dialchat_media_bucket" {
  description = "S3 bucket for DialChat raw videos, extracted audio, and analysis artifacts."
  value       = aws_s3_bucket.dialchat_media.bucket
}

output "shot_results_table_name" {
  description = "DynamoDB table for persisted shot analysis history."
  value       = aws_dynamodb_table.shot_results.name
}

output "equipment_profiles_table_name" {
  description = "DynamoDB table for trusted machine and grinder profiles when profile repository storage is enabled."
  value       = aws_dynamodb_table.equipment_profiles.name
}



output "vpc_id" {
  description = "ID of the optional Kubernetes VPC, when enabled."
  value       = try(module.vpc[0].vpc_id, null)
}

output "public_subnet_ids" {
  description = "IDs of the optional Kubernetes public subnets, when enabled."
  value       = try(module.vpc[0].public_subnets, null)
}

output "control_plane_public_ip" {
  description = "Public IPv4 address of the optional kubeadm control plane."
  value       = try(module.k8s_cluster[0].control_plane_public_ip, null)
}

output "control_plane_private_ip" {
  description = "Private IPv4 address advertised by kubeadm, when enabled."
  value       = try(module.k8s_cluster[0].control_plane_private_ip, null)
}

output "control_plane_instance_id" {
  description = "EC2 instance ID of the optional control plane."
  value       = try(module.k8s_cluster[0].control_plane_instance_id, null)
}

output "control_plane_security_group_id" {
  description = "Security group for the optional control plane."
  value       = try(module.k8s_cluster[0].control_plane_security_group_id, null)
}

output "worker_asg_name" {
  description = "Name of the optional worker Auto Scaling Group."
  value       = try(module.k8s_cluster[0].worker_asg_name, null)
}

output "ssh_command" {
  description = "Example SSH command for the optional control plane."
  value       = try("ssh ubuntu@${module.k8s_cluster[0].control_plane_public_ip}", null)
}

output "alert_sns_topic_arn" {
  description = "SNS topic ARN used by optional infrastructure alerts."
  value       = try(aws_sns_topic.alerts[0].arn, null)
}

output "application_urls" {
  description = "Public HTTPS URLs exposed through the optional application load balancer."
  value = var.enable_k8s_cluster && var.enable_public_ingress ? {
    for name, hostname in local.public_hostnames : name => "${var.public_ingress_enable_https ? "https" : "http"}://${hostname}"
  } : {}
}

output "load_balancer_dns_name" {
  description = "DNS name of the optional public application load balancer."
  value       = try(module.ingress[0].load_balancer_dns_name, null)
}

output "ecr_repository_urls" {
  description = "ECR repository URLs keyed by repository name."
  value = {
    for name, repo in aws_ecr_repository.app : name => repo.repository_url
  }
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC builds/deploys."
  value       = aws_iam_role.github_actions.arn
}
