provider "aws" {
  region = var.aws_region

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
      ec2 = var.localstack_endpoint
      ecr = var.localstack_endpoint
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
  name_prefix    = "${var.project}-${var.environment}"

  common_tags = {
    Project     = var.project
    Environment = var.environment
    Session     = "21-final-devops-project"
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}
