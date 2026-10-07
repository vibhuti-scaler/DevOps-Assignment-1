# Recorded run targets the local AWS emulator; no real account is involved.
project            = "notes"
environment        = "prod"
owner              = "vibhuti-24bcs10288"
aws_region         = "ap-south-1"
vpc_cidr           = "10.30.0.0/16"
availability_zones = ["ap-south-1a", "ap-south-1b"]
# See variables.tf: ECR is not available in the community edition of the
# local emulator, so the registry is planned but not applied here.
create_ecr_repository = false
localstack_endpoint   = "http://localhost:4566"
