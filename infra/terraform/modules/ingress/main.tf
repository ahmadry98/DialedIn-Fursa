resource "aws_acm_certificate" "main" {
  count             = var.enable_https ? 1 : 0
  domain_name       = "*.${var.domain_name}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_route53_record" "certificate_validation" {
  for_each = var.enable_https && var.manage_dns ? {
    for option in aws_acm_certificate.main[0].domain_validation_options :
    option.domain_name => {
      name   = option.resource_record_name
      record = option.resource_record_value
      type   = option.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.hosted_zone_id
}

resource "aws_acm_certificate_validation" "main" {
  count                   = var.enable_https && var.manage_dns ? 1 : 0
  certificate_arn         = aws_acm_certificate.main[0].arn
  validation_record_fqdns = [for record in aws_route53_record.certificate_validation : record.fqdn]
}

resource "aws_security_group" "load_balancer" {
  name        = "${var.name_prefix}-alb"
  description = "Public HTTPS access to the DialedIN ingress"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb"
  })
}

resource "aws_vpc_security_group_ingress_rule" "load_balancer_https" {
  count             = var.enable_https ? 1 : 0
  security_group_id = aws_security_group.load_balancer.id
  description       = "Public HTTPS traffic"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "load_balancer_http" {
  count             = var.enable_https || !var.enable_https_listener ? 0 : 1
  security_group_id = aws_security_group.load_balancer.id
  description       = "Public HTTP traffic for dev ingress"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "load_balancer_ingress" {
  security_group_id            = aws_security_group.load_balancer.id
  description                  = "Forward traffic to ingress-nginx workers"
  referenced_security_group_id = var.worker_security_group_id
  from_port                    = var.http_node_port
  to_port                      = var.http_node_port
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "worker_ingress" {
  security_group_id            = var.worker_security_group_id
  description                  = "Ingress traffic from the application load balancer"
  referenced_security_group_id = aws_security_group.load_balancer.id
  from_port                    = var.http_node_port
  to_port                      = var.http_node_port
  ip_protocol                  = "tcp"
}

resource "aws_lb" "main" {
  name               = substr("${var.name_prefix}-alb", 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.load_balancer.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false

  tags = var.tags
}

resource "aws_lb_target_group" "ingress" {
  name        = substr("${var.name_prefix}-ingress", 0, 32)
  port        = var.http_node_port
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = var.vpc_id

  deregistration_delay = 30

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 15
    matcher             = "200-499"
    path                = "/healthz"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }

  tags = var.tags
}

resource "aws_autoscaling_attachment" "ingress" {
  autoscaling_group_name = var.worker_asg_name
  lb_target_group_arn    = aws_lb_target_group.ingress.arn
}

resource "aws_lb_listener" "https" {
  count             = var.enable_https && var.enable_https_listener ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.manage_dns ? aws_acm_certificate_validation.main[0].certificate_arn : aws_acm_certificate.main[0].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ingress.arn
  }
}

resource "aws_lb_listener" "http" {
  count             = var.enable_https ? 0 : 1
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ingress.arn
  }
}

resource "aws_route53_record" "application" {
  for_each = var.manage_dns ? var.public_hostnames : {}

  allow_overwrite = true
  name            = each.value
  type            = "A"
  zone_id         = var.hosted_zone_id

  alias {
    evaluate_target_health = true
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
  }
}
