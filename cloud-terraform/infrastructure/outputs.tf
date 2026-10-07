output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "Address range of the VPC."
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs, keyed by Availability Zone."
  value       = { for zone, subnet in aws_subnet.public : zone => subnet.id }
}

output "private_subnet_ids" {
  description = "Private subnet IDs, keyed by Availability Zone."
  value       = { for zone, subnet in aws_subnet.private : zone => subnet.id }
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway attached to the VPC."
  value       = aws_internet_gateway.main.id
}

output "web_security_group_id" {
  description = "Security group applied to the web instance."
  value       = aws_security_group.web.id
}

output "web_instance_id" {
  description = "ID of the EC2 instance."
  value       = aws_instance.web.id
}

output "web_private_ip" {
  description = "Private address of the EC2 instance."
  value       = aws_instance.web.private_ip
}

output "assets_bucket" {
  description = "Name of the S3 bucket holding static assets."
  value       = aws_s3_bucket.assets.id
}
