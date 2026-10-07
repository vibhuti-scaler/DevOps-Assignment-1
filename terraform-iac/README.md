# Session 18: Terraform & Infrastructure as Code

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Batch:** B

A Terraform project that creates an S3 bucket, and written notes on five AWS services. The complete
workflow — `init`, `fmt`, `validate`, `plan`, `apply`, `output`, `state list`, `destroy` — was run
end to end against a local AWS emulator. Transcript:
[18-terraform-s3-demo.txt](../evidence/terraform/18-terraform-s3-demo.txt).

```bash
docker run -d --name devops-localstack -p 4566:4566 \
  -e SERVICES=s3,ec2,ecr,sts,iam localstack/localstack:3.8
bash scripts/run-terraform-labs.sh
```

## Where this runs, and why that is stated up front

There is no AWS account behind this homework and no credential on this machine. The target is
[LocalStack](https://localstack.cloud/), an AWS-API-compatible server in a container. The same
configuration targets a real account by emptying one variable:

```hcl
localstack_endpoint = "http://localhost:4566"   # the emulator
localstack_endpoint = ""                        # a real AWS account
```

[`provider.tf`](terraform-s3-demo/provider.tf) uses that one value to decide whether to set the
service endpoints, skip the credential and account pre-flight calls, and use path-style S3 URLs.
Nothing else in the configuration differs between the two, which is the point: the resources,
variables and outputs are real Terraform that would apply unchanged.

## Project layout

```text
terraform-s3-demo/
├── versions.tf       required_version and pinned provider versions
├── provider.tf       the AWS provider, endpoints and default tags
├── variables.tf      inputs, each with a type, a description and validation
├── main.tf           the bucket and everything attached to it
├── outputs.tf        what the configuration publishes
├── terraform.tfvars  the values used for the recorded run
└── .gitignore        state and .terraform/ are not committed
```

`.terraform.lock.hcl` **is** committed, deliberately. It pins the exact provider build and its
checksum, so a later run cannot silently pick up a different provider. State and `.terraform/` are
ignored because state contains every resource attribute, which for many resource types includes
secrets.

## What the configuration creates

| Resource | Why |
| --- | --- |
| `random_id.suffix` | S3 bucket names share one global namespace. A random suffix makes the name unique without hard-coding one. |
| `aws_s3_bucket.homework` | The bucket. |
| `aws_s3_bucket_public_access_block` | All four blocks on. Stated in code rather than relying on an account default. |
| `aws_s3_bucket_versioning` | Keeps previous versions of every object. |
| `aws_s3_bucket_server_side_encryption_configuration` | AES256 at rest. |
| `aws_s3_bucket_lifecycle_configuration` | Expires superseded versions after 30 days; aborts incomplete multipart uploads after 7. |
| `aws_s3_object.readme` | A small object, so `apply` produces something that can be read back. |

Variables carry validation rather than just a type:

```hcl
validation {
  condition     = can(regex("^[a-z0-9][a-z0-9-]{1,40}$", var.bucket_prefix))
  error_message = "bucket_prefix must be lower case letters, digits or hyphens, 2-41 characters."
}
```

S3 bucket names are DNS labels. Catching that at plan time beats a provider error forty seconds into
an apply.

## The workflow, command by command

### `terraform init`

Downloads the providers, writes the lock file, and prepares the working directory. It is the only
command that touches the network for anything other than the target API.

### `terraform fmt -check -recursive`

```text
PASS: terraform fmt -check (every file already canonical)
```

Exit code 0 means every file is already in canonical form. In CI this is the cheapest possible check
and it removes an entire category of review comment.

### `terraform validate`

```text
Success! The configuration is valid.
```

Syntax, types, and references — without contacting AWS. It would not notice a bucket name already
taken by someone else; that is `plan`'s job, and sometimes `apply`'s.

### `terraform plan -out=tfplan`

```text
Plan: 6 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + bucket_arn        = (known after apply)
  + bucket_name       = (known after apply)
  …
```

`-out` saves the plan so that `apply` executes exactly what was reviewed. Without it, `apply`
re-plans, and the thing that runs is not necessarily the thing that was approved.

### `terraform apply tfplan`

```text
Apply complete! Resources: 6 added, 0 changed, 0 destroyed.
```

### `terraform output` and `terraform state list`

```text
bucket_arn = "arn:aws:s3:::devops-homework-e5aa2e2c"
bucket_name = "devops-homework-e5aa2e2c"
bucket_region = "ap-south-1"
object_key = "README.txt"
versioning_status = "Enabled"
```

```text
aws_s3_bucket.homework
aws_s3_bucket_public_access_block.homework
aws_s3_bucket_server_side_encryption_configuration.homework
aws_s3_bucket_versioning.homework
aws_s3_object.readme
random_id.suffix
```

Outputs are the configuration's public interface — the values another configuration or a pipeline
consumes. State is the private record of what exists.

### Reading the result back, independently of Terraform

Terraform reporting success is not the same as the bucket being configured correctly. The transcript
therefore checks through the AWS API directly:

```bash
aws --endpoint-url http://localhost:4566 s3api get-bucket-versioning --bucket "$bucket"
aws --endpoint-url http://localhost:4566 s3api get-bucket-encryption --bucket "$bucket"
aws --endpoint-url http://localhost:4566 s3api get-public-access-block --bucket "$bucket"
aws --endpoint-url http://localhost:4566 s3 cp "s3://$bucket/README.txt" -
```

```text
{"Status": "Enabled"}
{"SSEAlgorithm": "AES256"}
{"BlockPublicAcls": true, "BlockPublicPolicy": true, "IgnorePublicAcls": true, "RestrictPublicBuckets": true}
Session 18 - Terraform and Infrastructure as Code
Owner: vibhuti-24bcs10288
Bucket created and managed by Terraform.
```

### Idempotence

```bash
terraform plan -detailed-exitcode
```

```text
No changes. Your infrastructure matches the configuration.
PASS: the configuration is idempotent (exit 0, no changes)
```

`-detailed-exitcode` returns 0 for no changes, 2 for a diff, 1 for an error. It is what turns
"declarative" into something a pipeline can check: a drift detection job is this command on a
schedule.

### `terraform destroy`

```text
Destroy complete! Resources: 6 destroyed.
```

```text
$ aws s3api head-bucket --bucket devops-homework-e5aa2e2c
An error occurred (404) when calling the HeadBucket operation: Not Found
```

The error is the evidence. Destroy is recorded as well as apply, because leaving infrastructure
behind is how coursework becomes a bill.

## One thing that did not work, and how it was handled

The lifecycle configuration **is created** in the emulator — the AWS CLI reads the rule back — but
the AWS provider's post-create consistency poll never converges against it, and the apply fails
after its three-minute timeout:

```text
Error: creating S3 Bucket (…) Lifecycle Configuration
While waiting: timeout while waiting for state to become 'true'
```

The provider repeatedly re-reads the configuration until it matches what it sent; LocalStack's
eventual-consistency emulation does not satisfy that loop. Worse, the failed apply leaves the
resource out of state, so the next `plan` wants to create it again — the idempotence check caught
that as drift.

Rather than delete the resource or pretend it passed, it is behind a variable:

```hcl
variable "enable_lifecycle_rule" {
  description = "…True for a real AWS account. Turned off for the recorded LocalStack run…"
  type        = bool
  default     = true
}
```

The default is `true`, which is correct for AWS. The recorded run sets it to `false` and the
transcript still shows the resource in a plan, so the code is visibly real:

```text
$ terraform plan -var enable_lifecycle_rule=true -target=aws_s3_bucket_lifecycle_configuration.homework
  + resource "aws_s3_bucket_lifecycle_configuration" "homework" {
      + rule {
          + id     = "expire-old-versions"
          + noncurrent_version_expiration { + noncurrent_days = 30 }
          + abort_incomplete_multipart_upload { + days_after_initiation = 7 }
```

## Task 2: AWS services

| Service | Notes |
| --- | --- |
| IAM — governance | [aws-services/01-iam/README.md](aws-services/01-iam/README.md) |
| EC2 — compute | [aws-services/02-ec2/README.md](aws-services/02-ec2/README.md) |
| S3 — storage | [aws-services/03-s3/README.md](aws-services/03-s3/README.md) |
| VPC — networking | [aws-services/04-vpc/README.md](aws-services/04-vpc/README.md) |
| DynamoDB and RDS — databases | [aws-services/05-dynamodb-rds/README.md](aws-services/05-dynamodb-rds/README.md) |

[Session 19](../cloud-terraform/README.md) builds the VPC, subnets, route tables, security groups,
EC2 instance and bucket those notes describe.

## Cleanup

`terraform destroy` runs at the end of the lab. The emulator holds nothing afterwards:

```bash
docker rm -f devops-localstack
```
