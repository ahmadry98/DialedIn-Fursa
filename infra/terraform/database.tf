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
