# Terraform execution evidence

**Vibhuti Bhatnagar · 24BCS10288 · vibhuti.24bcs10288@sst.scaler.com**

Transcripts from [`scripts/run-terraform-labs.sh`](../../scripts/run-terraform-labs.sh), captured on
7 October 2026 against a local AWS-compatible emulator (LocalStack 3.8) on `127.0.0.1:4566`. **No
AWS account and no AWS credential is involved.** Each transcript ends with a `terraform destroy`.

| Transcript | What to inspect |
| --- | --- |
| [18-terraform-s3-demo.txt](18-terraform-s3-demo.txt) | The full workflow on the S3 project, the bucket read back through the AWS API, and the idempotence check. |
| [19-cloud-infrastructure.txt](19-cloud-infrastructure.txt) | 21 resources: VPC, subnets, routing, security groups, EC2, S3 — with the dependency order visible in the apply. |
| [21-final-project-infrastructure.txt](21-final-project-infrastructure.txt) | The final project's own cloud: node subnets, ingress security group, artifacts bucket. |

Two resources are planned but not applied, because the community edition of the emulator cannot
serve them. Both are behind a variable that defaults to the value a real AWS account needs, and both
appear in a `terraform plan` in the transcript:

| Resource | Reason |
| --- | --- |
| `aws_s3_bucket_lifecycle_configuration` | The emulator creates it, but the provider's post-create consistency poll never converges and the apply times out. |
| `aws_ecr_repository` | ECR is not implemented in the community edition. |
