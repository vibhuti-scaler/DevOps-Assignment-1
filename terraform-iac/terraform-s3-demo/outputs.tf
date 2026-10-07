output "bucket_name" {
  description = "Name of the bucket Terraform created."
  value       = aws_s3_bucket.homework.id
}

output "bucket_arn" {
  description = "ARN of the bucket."
  value       = aws_s3_bucket.homework.arn
}

output "bucket_region" {
  description = "Region the bucket lives in."
  value       = aws_s3_bucket.homework.region
}

output "versioning_status" {
  description = "Whether object versioning is enabled."
  value       = aws_s3_bucket_versioning.homework.versioning_configuration[0].status
}

output "object_key" {
  description = "Key of the object uploaded by this configuration."
  value       = aws_s3_object.readme.key
}
