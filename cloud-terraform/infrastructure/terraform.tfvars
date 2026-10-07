# Values used for the recorded homework run, against the local AWS emulator.
project             = "devops-homework"
environment         = "dev"
owner               = "vibhuti-24bcs10288"
aws_region          = "ap-south-1"
vpc_cidr            = "10.20.0.0/16"
availability_zones  = ["ap-south-1a", "ap-south-1b"]
instance_type       = "t3.micro"
ssh_ingress_cidr    = "10.20.0.0/16"
localstack_endpoint = "http://localhost:4566"
