output "load_balancer_dns_name" {
  description = "DNS name assigned to the public application load balancer"
  value       = aws_lb.main.dns_name
}

output "load_balancer_arn_suffix" {
  description = "CloudWatch metric ARN suffix for the public application load balancer."
  value       = aws_lb.main.arn_suffix
}

output "target_group_arn_suffix" {
  description = "CloudWatch metric ARN suffix for the ingress target group."
  value       = aws_lb_target_group.ingress.arn_suffix
}

