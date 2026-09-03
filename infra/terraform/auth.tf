resource "aws_cognito_user_pool" "dialedin" {
  count = var.enable_cognito_auth ? 1 : 0
  name  = "${local.name_prefix}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = false
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  tags = local.common_tags
}

resource "aws_cognito_user_pool_client" "mobile" {
  count        = var.enable_cognito_auth ? 1 : 0
  name         = "${local.name_prefix}-mobile"
  user_pool_id = aws_cognito_user_pool.dialedin[0].id

  generate_secret               = false
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true
  supported_identity_providers  = ["COGNITO"]
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  access_token_validity         = 1
  id_token_validity             = 1
  refresh_token_validity        = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}
