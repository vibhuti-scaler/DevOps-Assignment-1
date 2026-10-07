# Session 19: Cloud & Terraform in Action

- **Name:** Vibhuti Bhatnagar
- **Roll no:** 24BCS10288
- **Email:** vibhuti.24bcs10288@sst.scaler.com
- **Batch:** B

One Terraform project that builds a complete small cloud environment: a VPC, public and private
subnets across two Availability Zones, routing, two security groups, an EC2 instance and an S3
bucket. Twenty-one resources, applied and destroyed. Transcript:
[19-cloud-infrastructure.txt](../evidence/terraform/19-cloud-infrastructure.txt).

```bash
docker run -d --name devops-localstack -p 4566:4566 \
  -e SERVICES=s3,ec2,ecr,sts,iam localstack/localstack:3.8
bash scripts/run-terraform-labs.sh
```

As in [Session 18](../terraform-iac/README.md), the target is a local AWS-compatible emulator, not a
real account. Emptying `localstack_endpoint` points the same configuration at AWS.

## Architecture

```text
                              Internet
                                  │
                        ┌─────────┴──────────┐
                        │  Internet Gateway  │
                        └─────────┬──────────┘
                                  │
   ┌──────────────────────────────┴──────────────────────────────┐
   │ VPC  10.20.0.0/16   DNS support + DNS hostnames enabled     │
   │                                                             │
   │  public route table: 0.0.0.0/0 → igw                        │
   │  ┌───────────────────────┐   ┌───────────────────────┐      │
   │  │ public 10.20.0.0/24   │   │ public 10.20.1.0/24   │      │
   │  │ ap-south-1a           │   │ ap-south-1b           │      │
   │  │   ┌───────────────┐   │   │                       │      │
   │  │   │ EC2  t3.micro │   │   │                       │      │
   │  │   │ sg: web       │◀──┼───┼── HTTP 80 from 0.0.0.0/0    │
   │  │   │               │   │   │   SSH 22 from 10.20.0.0/16  │
   │  │   └───────┬───────┘   │   │                       │      │
   │  └───────────┼───────────┘   └───────────────────────┘      │
   │              │ sg reference, not a CIDR                     │
   │              ▼ app tier accepts 8000 from sg: web           │
   │  private route table: local only                            │
   │  ┌───────────────────────┐   ┌───────────────────────┐      │
   │  │ private 10.20.10.0/24 │   │ private 10.20.11.0/24 │      │
   │  │ ap-south-1a           │   │ ap-south-1b           │      │
   │  └───────────────────────┘   └───────────────────────┘      │
   └─────────────────────────────────────────────────────────────┘

   S3 bucket  devops-homework-dev-assets-<random>
   versioning on · AES256 · all public access blocked
```

## The files

```text
infrastructure/
├── versions.tf       required_version and pinned providers
├── provider.tf       AWS provider, endpoint switch, default tags, locals
├── variables.tf      inputs with types, descriptions and validation
├── network.tf        VPC, IGW, subnets, route tables, security groups
├── compute.tf        the AMI lookup and the EC2 instance
├── storage.tf        the S3 bucket and its settings
├── outputs.tf        IDs and addresses other configurations would consume
└── terraform.tfvars  the values used for the recorded run
```

Splitting by concern rather than by Terraform block type is the part worth copying. `network.tf`
holds everything about the network; when a subnet changes, there is one file to read.

## Providers

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.80" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
```

`~> 5.80` accepts 5.81 and refuses 6.0 — patches arrive, breaking changes do not. The exact build is
recorded in `.terraform.lock.hcl`, which is committed.

`default_tags` on the provider applies `Project`, `Environment`, `Session`, `Owner` and `ManagedBy`
to every taggable resource without repeating them. Resource-level `tags` add `Name` on top.

## Variables

Every variable has a type and a description; the ones with a failure mode have validation:

```hcl
variable "environment" {
  type    = string
  default = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "availability_zones" {
  type    = list(string)
  default = ["ap-south-1a", "ap-south-1b"]
  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least two Availability Zones are needed for a highly available subnet layout."
  }
}
```

The second one encodes a design decision as a constraint. Someone reducing the list to one zone gets
told why that is wrong at plan time, rather than finding out when a load balancer refuses to create.

## Resources

Subnets are created with `for_each` over the Availability Zone list, so adding a zone adds a subnet
pair and nothing else changes:

```hcl
resource "aws_subnet" "public" {
  for_each = { for index, zone in var.availability_zones : zone => index }

  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value)
  map_public_ip_on_launch = true
}
```

`for_each` rather than `count` is deliberate. With `count`, removing the first zone from the list
renumbers every subsequent subnet and Terraform destroys and recreates them. With `for_each` the
address is `aws_subnet.public["ap-south-1a"]`, which is stable.

Private subnets start at index + 10, so the two groups never overlap as the list grows.

## Dependencies

Terraform builds the graph from references; there is no `depends_on` anywhere in this project.

```text
aws_vpc.main
 ├─▶ aws_internet_gateway.main
 │     └─▶ aws_route_table.public ─▶ aws_route_table_association.public
 ├─▶ aws_subnet.public[*] ─────────▶ aws_route_table_association.public
 ├─▶ aws_subnet.private[*]
 └─▶ aws_security_group.web ─▶ aws_security_group.app
                           └─▶ aws_instance.web ◀── data.aws_ami.amazon_linux
```

Two of those edges are worth naming. `aws_security_group.app` references `aws_security_group.web.id`
in a rule, which both creates the ordering *and* expresses the intent: "the app tier accepts traffic
from the web tier" rather than "from 10.20.0.0/24". And `aws_instance.web` depends on a subnet and a
security group purely because it reads their IDs.

The transcript shows the order Terraform derived:

```text
aws_vpc.main: Creation complete after 0s
aws_internet_gateway.main: Creating...
aws_subnet.public["ap-south-1a"]: Creating...
aws_security_group.web: Creating...
aws_security_group.app: Creating...     ← after web, because it references it
aws_instance.web: Creating...           ← after the subnet and the security group
```

## The AMI lookup

```hcl
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  filter { name = "name"  values = ["al2023-ami-2023.*-x86_64"] }
  filter { name = "state" values = ["available"] }
}
```

An AMI ID is region-specific and goes stale whenever a new image is published. Looking it up keeps
the configuration portable across regions, at the cost of `most_recent` meaning an apply months apart
may select a different image — in production you would pin the result in a variable after testing it.

## The workflow

```text
init → fmt -check → validate → plan -out → apply → output → state list → plan (idempotence) → destroy
```

```text
Plan: 21 to add, 0 to change, 0 to destroy.
Apply complete! Resources: 21 added, 0 changed, 0 destroyed.
```

Outputs:

```text
assets_bucket = "devops-homework-dev-assets-c3ac92a9"
internet_gateway_id = "igw-2b9f8092"
private_subnet_ids = { "ap-south-1a" = "subnet-…", "ap-south-1b" = "subnet-…" }
public_subnet_ids  = { "ap-south-1a" = "subnet-a544dc2b", "ap-south-1b" = "subnet-5e46ce62" }
vpc_cidr = "10.20.0.0/16"
vpc_id = "vpc-c386e983"
web_instance_id = "i-f335ebe4f44f15b19"
web_private_ip = "10.20.0.x"
web_security_group_id = "sg-96104ef8609798fb1"
```

Returning the subnet IDs as a **map keyed by Availability Zone** rather than a list means a consumer
can ask for the subnet in a specific zone, instead of relying on list position.

## Verifying through the AWS API

Terraform reporting success only means the API accepted the calls. The transcript reads the result
back independently:

```bash
aws --endpoint-url http://localhost:4566 ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" \
  --query 'Subnets[].{Id:SubnetId,Cidr:CidrBlock,Az:AvailabilityZone,Public:MapPublicIpOnLaunch}'
aws --endpoint-url http://localhost:4566 ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc" \
  --query 'RouteTables[].{Id:RouteTableId,Routes:Routes[].{Dest:DestinationCidrBlock,Gw:GatewayId}}'
aws --endpoint-url http://localhost:4566 ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc"
aws --endpoint-url http://localhost:4566 ec2 describe-instances --filters "Name=vpc-id,Values=$vpc"
```

The route tables are the interesting output: the public table has `0.0.0.0/0 → igw-…` and the
private table has only the implicit local route. That one difference is the entire definition of
"public subnet".

## Terraform state

```bash
terraform state list
terraform state show aws_instance.web
```

State maps configuration addresses to real resource IDs. Without it, Terraform cannot tell "create
this" from "this already exists".

What this project does, and what a shared project would do differently:

| | Here | A team project |
| --- | --- | --- |
| Backend | Local file, gitignored | S3 with native state locking, versioning on |
| Locking | Not needed, single user | Required — two concurrent applies corrupt state |
| Secrets in state | Avoided by not creating any | Encrypted at rest; access restricted |
| Drift detection | `terraform plan -detailed-exitcode` by hand | The same command on a schedule in CI |

State is never edited by hand. `terraform state mv` renames, `terraform state rm` forgets without
destroying, and `terraform import` adopts something that already exists.

## Idempotence and destroy

```text
No changes. Your infrastructure matches the configuration.
PASS: the configuration is idempotent (exit 0, no changes)

Destroy complete! Resources: 21 destroyed.
```

```text
$ aws ec2 describe-vpcs --vpc-ids vpc-c386e983
An error occurred (InvalidVpcID.NotFound): VpcID {'vpc-c386e983'} does not exist.
```

Destroy is recorded as deliberately as apply. The reverse order is visible in the transcript — the
instance goes before its subnet, the subnets before the VPC — which is the dependency graph walked
backwards.

## What is deliberately not here

- **A NAT Gateway.** The private subnets have no outbound route. A NAT Gateway bills hourly per
  Availability Zone whether or not anything uses it, and for the common case of reaching S3 or
  DynamoDB a VPC Endpoint is both cheaper and more private.
- **A load balancer.** It would add little beyond what the security group rules already demonstrate.
- **SSH open to the world.** `ssh_ingress_cidr` defaults to the VPC's own range. Session Manager is
  the better answer and needs no inbound rule at all.

## Background notes

| Topic | Notes |
| --- | --- |
| Cloud service models | [docs/01-cloud-service-models.md](docs/01-cloud-service-models.md) |
| Regions and Availability Zones | [docs/02-regions-and-availability-zones.md](docs/02-regions-and-availability-zones.md) |
| VPC, subnets, routing, security groups | [Session 18 VPC notes](../terraform-iac/aws-services/04-vpc/README.md) |
| EC2 | [Session 18 EC2 notes](../terraform-iac/aws-services/02-ec2/README.md) |
| S3 | [Session 18 S3 notes](../terraform-iac/aws-services/03-s3/README.md) |
