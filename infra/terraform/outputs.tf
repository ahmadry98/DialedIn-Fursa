output "dialchat_media_bucket" {
  description = "S3 bucket for DialChat raw videos, extracted audio, and analysis artifacts."
  value       = aws_s3_bucket.dialchat_media.bucket
}

output "shot_results_table_name" {
  description = "DynamoDB table for persisted shot analysis history."
  value       = aws_dynamodb_table.shot_results.name
}
