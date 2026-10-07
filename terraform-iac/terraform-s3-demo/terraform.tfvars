# Values used for the recorded homework run. These point at the local AWS
# emulator, so no real account and no credentials are involved.
aws_region         = "ap-south-1"
bucket_prefix      = "devops-homework"
owner              = "vibhuti-24bcs10288"
versioning_enabled = true

# See variables.tf: the lifecycle rule is applied against real AWS, but the
# provider cannot complete its consistency check against the local emulator.
enable_lifecycle_rule = false
localstack_endpoint   = "http://localhost:4566"
