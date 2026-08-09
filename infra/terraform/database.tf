resource "aws_dynamodb_table" "shot_results" {
  name         = "${local.name_prefix}-shot-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "shot_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "shot_id"
    type = "S"
  }

  tags = local.common_tags
}

resource "aws_dynamodb_table" "equipment_profiles" {
  name         = "${local.name_prefix}-equipment-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "profile_type"
  range_key    = "profile_id"

  attribute {
    name = "profile_type"
    type = "S"
  }

  attribute {
    name = "profile_id"
    type = "S"
  }

  attribute {
    name = "slug"
    type = "S"
  }

  global_secondary_index {
    name            = "profile-slug-index"
    hash_key        = "profile_type"
    range_key       = "slug"
    projection_type = "ALL"
  }

  tags = local.common_tags
}

