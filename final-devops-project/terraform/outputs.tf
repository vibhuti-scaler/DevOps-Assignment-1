output "vpc_id" {
  description = "ID of the cluster VPC."
  value       = aws_vpc.cluster.id
}

output "node_subnet_ids" {
  description = "Subnet IDs the nodes would be placed in, keyed by Availability Zone."
  value       = { for zone, subnet in aws_subnet.nodes : zone => subnet.id }
}

output "ingress_security_group_id" {
  description = "Security group for public ingress."
  value       = aws_security_group.ingress.id
}

output "ecr_repository_url" {
  description = "Registry URL the CI pipeline pushes the application image to."
  value       = try(aws_ecr_repository.notes[0].repository_url, "not created in this run")
}

output "artifacts_bucket" {
  description = "Bucket holding build artifacts."
  value       = aws_s3_bucket.artifacts.id
}
