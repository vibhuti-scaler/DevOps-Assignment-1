variable "project" {
  description = "Project name used as the prefix for every resource."
  type        = string
  default     = "notes"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "owner" {
  description = "Owner tag applied to every resource."
  type        = string
  default     = "vibhuti-24bcs10288"
}

variable "aws_region" {
  description = "Region the infrastructure is created in."
  type        = string
  default     = "ap-south-1"
}

variable "vpc_cidr" {
  description = "Address range of the cluster VPC."
  type        = string
  default     = "10.30.0.0/16"
}

variable "availability_zones" {
  description = "Availability Zones the node subnets are spread across."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "artifact_retention_days" {
  description = "How long build artifacts are kept in the artifacts bucket."
  type        = number
  default     = 30
}

variable "create_ecr_repository" {
  description = <<-EOT
    Create the container registry for the application image.

    True for a real AWS account. It is turned off for the recorded run because
    ECR is not implemented in the community edition of the local AWS emulator,
    so there is nothing for the provider to call. The resource still appears in
    `terraform plan`; see the project README.
  EOT
  type        = bool
  default     = true
}

variable "localstack_endpoint" {
  description = "AWS-compatible endpoint. Empty means a real AWS account."
  type        = string
  default     = ""
}
