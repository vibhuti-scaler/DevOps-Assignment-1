variable "project" {
  description = "Short project name used as a prefix on every resource."
  type        = string
  default     = "devops-homework"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

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
  description = "Region to build the network in."
  type        = string
  default     = "ap-south-1"
}

variable "vpc_cidr" {
  description = "Address range of the VPC."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "availability_zones" {
  description = "Availability Zones to spread the subnets across."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least two Availability Zones are needed for a highly available subnet layout."
  }
}

variable "instance_type" {
  description = "EC2 instance type for the web server."
  type        = string
  default     = "t3.micro"
}

variable "ssh_ingress_cidr" {
  description = "Range allowed to reach SSH. Narrow this to an office or VPN range in a real account."
  type        = string
  default     = "10.20.0.0/16"
}

variable "localstack_endpoint" {
  description = "AWS-compatible endpoint. Empty means a real AWS account."
  type        = string
  default     = ""
}
