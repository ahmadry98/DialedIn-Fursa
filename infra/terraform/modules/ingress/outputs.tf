output "load_balancer_dns_name" {
  description = "DNS name assigned to the public application load balancer"
  value       = aws_lb.main.dns_name
}
