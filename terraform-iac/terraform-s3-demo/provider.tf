# One provider definition serves both targets.
#
#   localstack_endpoint = "http://localhost:4566"  -> the local AWS emulator
#   localstack_endpoint = ""                       -> a real AWS account
#
# Nothing else in the configuration changes between the two, which is the
# point: the same code describes the infrastructure either way.
provider "aws" {
  region = var.aws_region

  # LocalStack has no real IAM, so the usual pre-flight calls must be skipped
  # and S3 must be addressed with path-style URLs.
  skip_credentials_validation = local.use_localstack
  skip_requesting_account_id  = local.use_localstack
  skip_metadata_api_check     = local.use_localstack
  skip_region_validation      = local.use_localstack
  s3_use_path_style           = local.use_localstack

  access_key = local.use_localstack ? "test" : null
  secret_key = local.use_localstack ? "test" : null

  dynamic "endpoints" {
    for_each = local.use_localstack ? [1] : []
    content {
      s3  = var.localstack_endpoint
      sts = var.localstack_endpoint
      iam = var.localstack_endpoint
    }
  }

  default_tags {
    tags = local.common_tags
  }
}

locals {
  use_localstack = var.localstack_endpoint != ""

  common_tags = {
    Project   = "devops-homework"
    Session   = "18-terraform-iac"
    Owner     = var.owner
    ManagedBy = "terraform"
  }
}
