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

output "certificate_validation_records" {
  description = "DNS records required to validate the ACM certificate when DNS is managed outside Route 53."
  value = var.enable_https ? [
    for option in aws_acm_certificate.main[0].domain_validation_options : {
      domain_name = option.domain_name
      name        = option.resource_record_name
      type        = option.resource_record_type
      value       = option.resource_record_value
    }
  ] : []
}
