# The AMI is looked up rather than hard-coded, because an AMI ID is specific to
# one region and goes stale the moment a new image is published.
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = var.instance_type
  # Terraform works the dependency order out from these references: the subnet
  # and security group are created before the instance, with no depends_on.
  subnet_id              = aws_subnet.public[var.availability_zones[0]].id
  vpc_security_group_ids = [aws_security_group.web.id]

  user_data = <<-EOT
    #!/bin/bash
    dnf install -y nginx
    echo "<h1>${local.name_prefix} web tier</h1>" > /usr/share/nginx/html/index.html
    systemctl enable --now nginx
  EOT

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "${local.name_prefix}-web" }
}
