# A random suffix keeps the bucket name unique without hard-coding one, since
# S3 bucket names share a single global namespace.
resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "homework" {
  bucket = "${var.bucket_prefix}-${random_id.suffix.hex}"

  tags = {
    Name = "${var.bucket_prefix}-${random_id.suffix.hex}"
  }
}

# Public access is blocked explicitly rather than relying on the account
# default, so the intent is recorded in code.
resource "aws_s3_bucket_public_access_block" "homework" {
  bucket = aws_s3_bucket.homework.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "homework" {
  bucket = aws_s3_bucket.homework.id

  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "homework" {
  bucket = aws_s3_bucket.homework.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "homework" {
  count = var.enable_lifecycle_rule ? 1 : 0

  bucket = aws_s3_bucket.homework.id

  # Versioning must exist before a rule can expire noncurrent versions, and
  # Terraform cannot infer that from the arguments alone.
  depends_on = [aws_s3_bucket_versioning.homework]

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# A small object so `terraform apply` produces something that can be read back
# and checked, rather than an empty bucket.
resource "aws_s3_object" "readme" {
  bucket       = aws_s3_bucket.homework.id
  key          = "README.txt"
  content      = <<-EOT
    Session 18 - Terraform and Infrastructure as Code
    Owner: ${var.owner}
    Bucket created and managed by Terraform.
  EOT
  content_type = "text/plain"
}
