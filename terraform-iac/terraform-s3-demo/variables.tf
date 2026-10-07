variable "aws_region" {
  description = "Region the bucket is created in."
  type        = string
  default     = "ap-south-1"
}

variable "bucket_prefix" {
  description = "Prefix for the bucket name; a random suffix makes it globally unique."
  type        = string
  default     = "devops-homework"

  validation {
    # S3 bucket names are DNS labels: lower case, digits and hyphens only.
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,40}$", var.bucket_prefix))
    error_message = "bucket_prefix must be lower case letters, digits or hyphens, 2-41 characters."
  }
}

variable "owner" {
  description = "Tag applied to every resource so ownership is obvious in the console."
  type        = string
  default     = "vibhuti-24bcs10288"
}

variable "versioning_enabled" {
  description = "Keep previous versions of every object."
  type        = bool
  default     = true
}

variable "noncurrent_version_expiration_days" {
  description = "How long superseded object versions are kept before they expire."
  type        = number
  default     = 30

  validation {
    condition     = var.noncurrent_version_expiration_days >= 1
    error_message = "noncurrent_version_expiration_days must be at least 1."
  }
}

variable "enable_lifecycle_rule" {
  description = <<-EOT
    Manage the bucket lifecycle rule.

    Left at true for a real AWS account. It is turned off for the recorded
    LocalStack run: the emulator creates the rule, but the AWS provider's
    post-create consistency poll never converges against it and the apply
    times out after three minutes. See the project README for the transcript.
  EOT
  type        = bool
  default     = true
}

variable "localstack_endpoint" {
  description = "AWS-compatible endpoint to target. Empty means a real AWS account."
  type        = string
  default     = ""
}
