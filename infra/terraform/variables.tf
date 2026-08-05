variable "region" {
  description = "AWS region for DialedIN infrastructure."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.region))
    error_message = "The region must look like us-east-1."
  }
}

variable "owner" {
  description = "Owner prefix used in resource names and tags."
  type        = string
  default     = "ahmadry98"
}

variable "project_name" {
  description = "Short project name used in resource names."
  type        = string
  default     = "dialedin"
}

variable "force_destroy_media_bucket" {
  description = "Allow Terraform to delete non-empty dev media buckets. Keep false for production."
  type        = bool
  default     = false
}


variable "allowed_media_upload_origins" {
  description = "Browser origins allowed to PUT media through presigned S3 URLs. Keep this narrow in production."
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
  ]
}
