output "control_plane_public_ip" {
  description = "Control-plane public IPv4 address"
  value       = aws_instance.control_plane.public_ip
}

output "control_plane_private_ip" {
  description = "Control-plane private IPv4 address"
  value       = aws_instance.control_plane.private_ip
}

output "control_plane_instance_id" {
  description = "Control-plane EC2 instance ID"
  value       = aws_instance.control_plane.id
}

output "control_plane_security_group_id" {
  description = "Control-plane security group ID"
  value       = aws_security_group.control_plane.id
}

output "worker_asg_name" {
  description = "Worker Auto Scaling Group name"
  value       = aws_autoscaling_group.workers.name
}

output "worker_security_group_id" {
  description = "Security group attached to worker nodes"
  value       = aws_security_group.worker.id
}

output "join_parameter_name" {
  description = "SSM parameter name containing the protected join command"
  value       = aws_ssm_parameter.kubeadm_join.name
}
