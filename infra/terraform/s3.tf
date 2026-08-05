resource "aws_s3_bucket" "dialchat_media" {
  bucket_prefix = "${local.name_prefix}-media-"
  force_destroy = var.force_destroy_media_bucket

  tags = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "dialchat_media" {
  bucket                  = aws_s3_bucket.dialchat_media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dialchat_media" {
  bucket = aws_s3_bucket.dialchat_media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "dialchat_media" {
  bucket = aws_s3_bucket.dialchat_media.id

  versioning_configuration {
    status = "Enabled"
  }
}


resource "aws_s3_bucket_cors_configuration" "dialchat_media" {
  bucket = aws_s3_bucket.dialchat_media.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT"]
    allowed_origins = var.allowed_media_upload_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
