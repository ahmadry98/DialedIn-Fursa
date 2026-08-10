locals {
  join_parameter_name = "/dialedin/${var.name_prefix}/kubeadm-join"
  worker_min_size     = var.enable_cluster_autoscaler || var.worker_desired_capacity == 0 ? 0 : 1
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "aws_key_pair" "cluster" {
  key_name   = "${var.name_prefix}-key"
  public_key = var.ssh_public_key

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-key"
  })
}

# The control plane writes a non-expiring kubeadm join command to this encrypted
# SSM parameter. ASG workers poll the parameter during boot, allowing replacement
# instances to join the cluster automatically without storing the token in Git.
resource "aws_ssm_parameter" "kubeadm_join" {
  name        = local.join_parameter_name
  description = "Encrypted kubeadm join command written by the control plane"
  type        = "SecureString"
  value       = "pending-control-plane-initialization"

  lifecycle {
    ignore_changes = [value]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-kubeadm-join"
  })
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "control_plane" {
  name               = "${var.name_prefix}-control-plane"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "control_plane_required" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
  ])

  role       = aws_iam_role.control_plane.name
  policy_arn = each.value
}

data "aws_iam_policy_document" "control_plane_ssm" {
  statement {
    sid       = "WriteJoinParameter"
    effect    = "Allow"
    actions   = ["ssm:PutParameter"]
    resources = [aws_ssm_parameter.kubeadm_join.arn]
  }
}

resource "aws_iam_role_policy" "control_plane_ssm" {
  name   = "write-kubeadm-join"
  role   = aws_iam_role.control_plane.id
  policy = data.aws_iam_policy_document.control_plane_ssm.json
}

resource "aws_iam_instance_profile" "control_plane" {
  name = "${var.name_prefix}-control-plane"
  role = aws_iam_role.control_plane.name
}

resource "aws_iam_role" "worker" {
  name               = "${var.name_prefix}-worker"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "worker_ecr" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "worker_ebs_csi" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

data "aws_iam_policy_document" "worker_runtime" {
  statement {
    sid       = "ReadJoinParameter"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.kubeadm_join.arn]
  }

  statement {
    sid    = "UseApplicationBucket"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["arn:aws:s3:::${var.application_s3_bucket}/*"]
  }

  statement {
    sid       = "ListApplicationBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.application_s3_bucket}"]
  }

  dynamic "statement" {
    for_each = length(var.dynamodb_table_arns) > 0 ? [1] : []

    content {
      sid    = "UseDialedINDynamoDBTables"
      effect = "Allow"
      actions = [
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:DeleteItem",
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem",
      ]
      resources = concat(
        var.dynamodb_table_arns,
        [for arn in var.dynamodb_table_arns : "${arn}/index/*"]
      )
    }
  }

  statement {
    sid    = "InvokeBedrockModels"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "PublishAlertNotifications"
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [var.alert_sns_topic_arn]
  }

  dynamic "statement" {
    for_each = var.enable_cluster_autoscaler ? [1] : []

    content {
      sid    = "DescribeAutoscalingResources"
      effect = "Allow"
      actions = [
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeAutoScalingInstances",
        "autoscaling:DescribeLaunchConfigurations",
        "autoscaling:DescribeScalingActivities",
        "autoscaling:DescribeTags",
        "ec2:DescribeImages",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeLaunchTemplateVersions",
        "ec2:GetInstanceTypesFromInstanceRequirements",
      ]
      resources = ["*"]
    }
  }

  dynamic "statement" {
    for_each = var.enable_cluster_autoscaler ? [1] : []

    content {
      sid    = "ScaleWorkerGroup"
      effect = "Allow"
      actions = [
        "autoscaling:SetDesiredCapacity",
        "autoscaling:TerminateInstanceInAutoScalingGroup",
      ]
      resources = [
        "arn:${data.aws_partition.current.partition}:autoscaling:${var.region}:${data.aws_caller_identity.current.account_id}:autoScalingGroup:*:autoScalingGroupName/${var.name_prefix}-workers",
      ]
    }
  }
}

resource "aws_iam_role_policy" "worker_runtime" {
  name   = "dialedin-worker-runtime"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker_runtime.json
}

resource "aws_iam_instance_profile" "worker" {
  name = "${var.name_prefix}-worker"
  role = aws_iam_role.worker.name
}

resource "aws_security_group" "control_plane" {
  name        = "${var.name_prefix}-control-plane"
  description = "Kubernetes control-plane traffic"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-control-plane"
  })
}

resource "aws_vpc_security_group_ingress_rule" "control_plane_ssh" {
  security_group_id = aws_security_group.control_plane.id
  description       = "SSH from the administrator CIDR"
  cidr_ipv4         = var.admin_ssh_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "control_plane_api_admin" {
  security_group_id = aws_security_group.control_plane.id
  description       = "Kubernetes API from the administrator CIDR"
  cidr_ipv4         = var.admin_ssh_cidr
  from_port         = 6443
  to_port           = 6443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "control_plane_internal" {
  security_group_id = aws_security_group.control_plane.id
  description       = "All intra-VPC cluster traffic"
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_egress_rule" "control_plane_all" {
  security_group_id = aws_security_group.control_plane.id
  description       = "Outbound package, registry, and AWS API access"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "worker" {
  name        = "${var.name_prefix}-worker"
  description = "Kubernetes worker traffic"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-worker"
  })
}

resource "aws_vpc_security_group_ingress_rule" "worker_internal" {
  security_group_id = aws_security_group.worker.id
  description       = "All intra-VPC cluster traffic"
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_egress_rule" "worker_all" {
  security_group_id = aws_security_group.worker.id
  description       = "Outbound package, registry, and AWS API access"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_instance" "control_plane" {
  ami                         = var.ubuntu_ami_id
  instance_type               = var.control_plane_instance_type
  subnet_id                   = var.public_subnet_ids[0]
  associate_public_ip_address = true
  key_name                    = aws_key_pair.cluster.key_name
  vpc_security_group_ids      = [aws_security_group.control_plane.id]
  iam_instance_profile        = aws_iam_instance_profile.control_plane.name

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    encrypted   = true
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = templatefile(
    "${path.module}/control-plane-user-data.sh.tftpl",
    {
      kubernetes_minor_version = var.kubernetes_minor_version
      pod_cidr                 = var.pod_cidr
      region                   = var.region
      join_parameter_name      = aws_ssm_parameter.kubeadm_join.name
    }
  )

  user_data_replace_on_change = true

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-control-plane"
    Role = "control-plane"
  })

  depends_on = [
    aws_iam_role_policy.control_plane_ssm,
    aws_iam_role_policy_attachment.control_plane_required,
  ]
}

resource "aws_launch_template" "worker" {
  name_prefix   = "${var.name_prefix}-worker-"
  image_id      = var.ubuntu_ami_id
  instance_type = var.worker_instance_type
  key_name      = aws_key_pair.cluster.key_name

  iam_instance_profile {
    name = aws_iam_instance_profile.worker.name
  }

  network_interfaces {
    associate_public_ip_address = true
    delete_on_termination       = true
    device_index                = 0
    security_groups             = [aws_security_group.worker.id]
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  block_device_mappings {
    device_name = "/dev/sda1"

    ebs {
      encrypted             = true
      volume_size           = 20
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  user_data = base64encode(templatefile(
    "${path.module}/worker-user-data.sh.tftpl",
    {
      kubernetes_minor_version = var.kubernetes_minor_version
      region                   = var.region
      join_parameter_name      = aws_ssm_parameter.kubeadm_join.name
    }
  ))

  tag_specifications {
    resource_type = "instance"

    tags = merge(var.tags, {
      Name = "${var.name_prefix}-worker"
      Role = "worker"
    })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = var.tags
  }

  depends_on = [
    aws_iam_role_policy.worker_runtime,
    aws_iam_role_policy_attachment.worker_ebs_csi,
    aws_iam_role_policy_attachment.worker_ecr,
  ]
}

resource "aws_autoscaling_group" "workers" {
  name                = "${var.name_prefix}-workers"
  min_size            = local.worker_min_size
  max_size            = 3
  desired_capacity    = var.worker_desired_capacity
  vpc_zone_identifier = var.public_subnet_ids
  health_check_type   = "EC2"

  launch_template {
    id      = aws_launch_template.worker.id
    version = aws_launch_template.worker.latest_version
  }

  instance_refresh {
    strategy = "Rolling"

    preferences {
      min_healthy_percentage = 0
    }
  }

  dynamic "tag" {
    for_each = merge(
      var.tags,
      {
        Name = "${var.name_prefix}-worker"
        Role = "worker"
      },
      var.enable_cluster_autoscaler ? {
        "k8s.io/cluster-autoscaler/enabled"            = "true"
        "k8s.io/cluster-autoscaler/${var.name_prefix}" = "owned"
      } : {}
    )

    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}
