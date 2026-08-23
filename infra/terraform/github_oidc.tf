data "aws_caller_identity" "current" {}

locals {
  github_actions_oidc_provider_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "github_actions_oidc_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_actions_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = concat(
        flatten([
          for repo in var.github_actions_repositories : [
            "repo:${repo}:ref:refs/heads/main",
            "repo:${repo}:ref:refs/heads/dev",
            "repo:${repo}:environment:dev",
            "repo:${repo}:environment:production"
          ]
        ]),
        [
          "repo:ahmadry98@100522503/DialedIn-Fursa@1311859286:ref:refs/heads/main",
          "repo:ahmadry98@100522503/DialedIn-Fursa@1311859286:ref:refs/heads/dev",
          "repo:ahmadry98@100522503/DialedIn-Fursa@1311859286:environment:dev",
          "repo:ahmadry98@100522503/DialedIn-Fursa@1311859286:environment:production"
        ]
      )
    }
  }
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  count = var.manage_github_oidc_provider ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-github-actions-oidc"
  })
}

resource "aws_iam_role" "github_actions" {
  name               = var.github_actions_role_name
  assume_role_policy = data.aws_iam_policy_document.github_actions_oidc_assume_role.json

  tags = merge(local.common_tags, {
    Name = var.github_actions_role_name
  })
}

data "aws_iam_policy_document" "github_actions_ecr" {
  statement {
    sid = "GetEcrAuthorizationToken"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = ["*"]
  }

  statement {
    sid = "PushAndReadDialedInImages"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:PutImage",
      "ecr:UploadLayerPart"
    ]
    resources = [
      for repository_name in var.ecr_repository_names :
      "arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/${repository_name}"
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_ecr" {
  name   = "${var.github_actions_role_name}-ecr"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_ecr.json
}


data "aws_iam_policy_document" "github_actions_k8s_deploy" {
  statement {
    sid = "DiscoverControlPlaneSecurityGroup"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeSecurityGroups"
    ]
    resources = ["*"]
  }

  statement {
    sid = "TemporarilyAllowGitHubRunnerKubernetesApi"
    actions = [
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:RevokeSecurityGroupIngress"
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Project"
      values   = [local.common_tags.Project]
    }
  }
}

resource "aws_iam_role_policy" "github_actions_k8s_deploy" {
  name   = "${var.github_actions_role_name}-k8s-deploy"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_k8s_deploy.json
}
