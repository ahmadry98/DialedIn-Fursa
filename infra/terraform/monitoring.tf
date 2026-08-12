resource "aws_cloudwatch_metric_alarm" "ingress_target_5xx" {
  count = var.enable_k8s_cluster && var.enable_public_ingress ? 1 : 0

  alarm_name          = "${local.name_prefix}-ingress-target-5xx"
  alarm_description   = "DialedIN API target group is returning 5xx responses."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  threshold           = 5
  datapoints_to_alarm = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  ok_actions          = [aws_sns_topic.alerts[0].arn]

  dimensions = {
    LoadBalancer = module.ingress[0].load_balancer_arn_suffix
    TargetGroup  = module.ingress[0].target_group_arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "ingress_unhealthy_hosts" {
  count = var.enable_k8s_cluster && var.enable_public_ingress ? 1 : 0

  alarm_name          = "${local.name_prefix}-ingress-unhealthy-hosts"
  alarm_description   = "DialedIN ingress target group has unhealthy Kubernetes workers."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  threshold           = 1
  datapoints_to_alarm = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  ok_actions          = [aws_sns_topic.alerts[0].arn]

  dimensions = {
    LoadBalancer = module.ingress[0].load_balancer_arn_suffix
    TargetGroup  = module.ingress[0].target_group_arn_suffix
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "control_plane_cpu_high" {
  count = var.enable_k8s_cluster ? 1 : 0

  alarm_name          = "${local.name_prefix}-control-plane-cpu-high"
  alarm_description   = "DialedIN control plane CPU is high for several minutes."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  threshold           = 80
  datapoints_to_alarm = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  ok_actions          = [aws_sns_topic.alerts[0].arn]

  dimensions = {
    InstanceId = module.k8s_cluster[0].control_plane_instance_id
  }

  tags = local.common_tags
}
