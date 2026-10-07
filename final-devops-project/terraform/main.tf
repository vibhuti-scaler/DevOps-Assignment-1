# ---------------------------------------------------------------------------
# Network the Kubernetes nodes would run in
# ---------------------------------------------------------------------------
resource "aws_vpc" "cluster" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${local.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "cluster" {
  vpc_id = aws_vpc.cluster.id

  tags = { Name = "${local.name_prefix}-igw" }
}

resource "aws_subnet" "nodes" {
  for_each = { for index, zone in var.availability_zones : zone => index }

  vpc_id                  = aws_vpc.cluster.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value)
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name_prefix}-nodes-${each.key}"
    # The tag a managed Kubernetes service uses to find subnets it may place
    # public load balancers in.
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_route_table" "nodes" {
  vpc_id = aws_vpc.cluster.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.cluster.id
  }

  tags = { Name = "${local.name_prefix}-nodes-rt" }
}

resource "aws_route_table_association" "nodes" {
  for_each = aws_subnet.nodes

  subnet_id      = each.value.id
  route_table_id = aws_route_table.nodes.id
}

resource "aws_security_group" "ingress" {
  name        = "${local.name_prefix}-ingress"
  description = "Public HTTP and HTTPS into the ingress controller"
  vpc_id      = aws_vpc.cluster.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-ingress-sg" }
}

# ---------------------------------------------------------------------------
# Registry for the application image
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "notes" {
  count = var.create_ecr_repository ? 1 : 0

  name                 = "${local.name_prefix}/notes"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    # Every pushed image is scanned by the registry as well as in the
    # pipeline, so a vulnerability disclosed after the push is still found.
    scan_on_push = true
  }

  tags = { Name = "${local.name_prefix}-notes" }
}

# ---------------------------------------------------------------------------
# Build artifacts
# ---------------------------------------------------------------------------
resource "random_id" "artifacts" {
  byte_length = 4
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.name_prefix}-artifacts-${random_id.artifacts.hex}"

  tags = { Name = "${local.name_prefix}-artifacts" }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
