resource "aws_cloudfront_origin_access_control" "dialchat_media" {
  count                             = var.enable_media_cdn ? 1 : 0
  name                              = "${local.name_prefix}-media"
  description                       = "CloudFront access to reviewed DialedIN machine images."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "reviewed_machine_images" {
  count   = var.enable_media_cdn ? 1 : 0
  name    = "${local.name_prefix}-reviewed-machine-images"
  runtime = "cloudfront-js-2.0"
  comment = "Only expose reviewed machine-photo objects through the media CDN."
  publish = true
  code    = <<-EOF_FUNCTION
function handler(event) {
  var request = event.request;
  var uri = request.uri || "/";
  if ((request.method !== "GET" && request.method !== "HEAD") || uri.indexOf("/machine_photo/") === -1) {
    return {
      statusCode: 403,
      statusDescription: "Forbidden",
      headers: { "cache-control": { "value": "no-store" } }
    };
  }
  return request;
}
EOF_FUNCTION
}

resource "aws_cloudfront_distribution" "dialchat_media" {
  count           = var.enable_media_cdn ? 1 : 0
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.name_prefix} reviewed machine images"

  origin {
    domain_name              = aws_s3_bucket.dialchat_media.bucket_regional_domain_name
    origin_id                = "dialchat-media-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.dialchat_media[0].id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "dialchat-media-s3"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.reviewed_machine_images[0].arn
    }
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate { cloudfront_default_certificate = true }
  tags = local.common_tags
}

data "aws_iam_policy_document" "dialchat_media_cloudfront" {
  count = var.enable_media_cdn ? 1 : 0

  statement {
    sid       = "AllowCloudFrontReadOfMedia"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.dialchat_media.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.dialchat_media[0].arn]
    }
  }
}

resource "aws_s3_bucket_policy" "dialchat_media_cloudfront" {
  count  = var.enable_media_cdn ? 1 : 0
  bucket = aws_s3_bucket.dialchat_media.id
  policy = data.aws_iam_policy_document.dialchat_media_cloudfront[0].json
}
