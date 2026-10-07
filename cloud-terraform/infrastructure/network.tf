# ---------------------------------------------------------------------------
# VPC, subnets, routing
# ---------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block         = var.vpc_cidr
  enable_dns_support = true
  # Without DNS hostnames an instance in a public subnet gets a public IP but
  # no public DNS name, which quietly breaks a lot of tooling.
  enable_dns_hostnames = true

  tags = { Name = "${local.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-igw" }
}

# /24s carved out of the VPC range: public subnets take the low indexes,
# private subnets start at index 10, so the two groups never overlap as the
# list of Availability Zones grows.
resource "aws_subnet" "public" {
  for_each = { for index, zone in var.availability_zones : zone => index }

  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value)
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name_prefix}-public-${each.key}"
    Tier = "public"
  }
}

resource "aws_subnet" "private" {
  for_each = { for index, zone in var.availability_zones : zone => index }

  vpc_id            = aws_vpc.main.id
  availability_zone = each.key
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, each.value + 10)

  tags = {
    Name = "${local.name_prefix}-private-${each.key}"
    Tier = "private"
  }
}

# A subnet is "public" only because its route table sends 0.0.0.0/0 to an
# Internet Gateway. Nothing else about the subnet makes it public.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${local.name_prefix}-public-rt" }
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# The private route table carries only the implicit local route, so these
# subnets have no path to the internet at all. A NAT Gateway would be added
# here to allow outbound-only access; it is left out because it bills hourly.
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-private-rt" }
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

# ---------------------------------------------------------------------------
# Security groups
# ---------------------------------------------------------------------------
resource "aws_security_group" "web" {
  name        = "${local.name_prefix}-web"
  description = "HTTP from anywhere, SSH from the trusted range only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH from the trusted range"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_ingress_cidr]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-web-sg" }
}

resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-app"
  description = "Reachable only from the web tier"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Application port from the web security group"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    # Referencing the other security group rather than a CIDR means the rule
    # keeps working when instance addresses change.
    security_groups = [aws_security_group.web.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-app-sg" }
}
