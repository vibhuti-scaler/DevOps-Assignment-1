#!/usr/bin/env bash
# Drives the Session 18 and Session 19 Terraform projects end to end against a
# local AWS emulator (LocalStack), and records every command and its output in
# evidence/terraform/. Nothing here touches a real AWS account: the provider
# endpoint comes from terraform.tfvars and points at 127.0.0.1:4566.
set -uo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
terraform_bin="$repo_dir/.lab/bin/terraform"
out="$repo_dir/evidence/terraform"
mkdir -p "$out"

endpoint="http://localhost:4566"

if ! curl -fsS --max-time 5 "$endpoint/_localstack/health" >/dev/null; then
  echo "LocalStack is not answering on $endpoint." >&2
  echo "Start it with:" >&2
  echo "  docker run -d --name devops-localstack -p 4566:4566 -e SERVICES=s3,ec2,sts,iam localstack/localstack:3.8" >&2
  exit 1
fi

transcript=""
log() { printf '%s\n' "$*" | tee -a "$transcript"; }

tf() {
  log ""
  log "\$ terraform $*"
  (cd "$project" && "$terraform_bin" "$@" -no-color) 2>&1 | tee -a "$transcript"
  return "${PIPESTATUS[0]}"
}

note() {
  log ""
  log "\$ $*"
  "$@" 2>&1 | tee -a "$transcript"
}

section() {
  transcript="$out/$1.txt"
  : > "$transcript"
  log "Vibhuti Bhatnagar | 24BCS10288 | vibhuti.24bcs10288@sst.scaler.com"
  log "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $1"
  log "Target: LocalStack at $endpoint (no real AWS account is involved)"
}

failures=0
check() {
  if [ "$1" -eq 0 ]; then log ""; log "PASS: $2"; else log ""; log "FAIL: $2 (exit $1)"; failures=$((failures + 1)); fi
}

awslocal() {
  AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=ap-south-1 \
    aws --endpoint-url "$endpoint" "$@"
}

# ----------------------------------------------------- Session 18: S3 project
project="$repo_dir/terraform-iac/terraform-s3-demo"
section "18-terraform-s3-demo"
note "$terraform_bin" version
tf init -upgrade;              check $? "terraform init"
tf fmt -check -recursive;      check $? "terraform fmt -check (every file already canonical)"
tf validate;                   check $? "terraform validate"
log ""
log "The lifecycle rule is valid Terraform and appears in the plan. It is left"
log "out of the applied run because the AWS provider's post-create consistency"
log "poll never converges against the emulator; see the project README."
tf plan -var enable_lifecycle_rule=true -target=aws_s3_bucket_lifecycle_configuration.homework
tf plan -out=tfplan;           check $? "terraform plan"
tf apply -auto-approve tfplan; check $? "terraform apply"
tf output;                     check $? "terraform output"
tf state list;                 check $? "terraform state list"

bucket="$(cd "$project" && "$terraform_bin" output -raw bucket_name)"
log ""
log "Reading the bucket back through the AWS API, independently of Terraform:"
note awslocal s3api head-bucket --bucket "$bucket"
note awslocal s3api get-bucket-versioning --bucket "$bucket"
note awslocal s3api get-bucket-encryption --bucket "$bucket"
note awslocal s3api get-public-access-block --bucket "$bucket"
note awslocal s3 ls "s3://$bucket"
note awslocal s3 cp "s3://$bucket/README.txt" -

log ""
log "A second plan with no source change must report no differences:"
tf plan -detailed-exitcode
case "${PIPESTATUS[0]}" in
  0) log ""; log "PASS: the configuration is idempotent (exit 0, no changes)" ;;
  2) log ""; log "FAIL: drift detected (exit 2)"; failures=$((failures + 1)) ;;
  *) log ""; log "FAIL: terraform plan errored"; failures=$((failures + 1)) ;;
esac

tf destroy -auto-approve; check $? "terraform destroy"
log ""
log "The bucket is gone after destroy (an error here is the expected result):"
note awslocal s3api head-bucket --bucket "$bucket" || true
rm -f "$project/tfplan"

# --------------------------------------------- Session 19: full network stack
project="$repo_dir/cloud-terraform/infrastructure"
section "19-cloud-infrastructure"
tf init -upgrade;              check $? "terraform init"
tf fmt -check -recursive;      check $? "terraform fmt -check"
tf validate;                   check $? "terraform validate"
tf plan -out=tfplan;           check $? "terraform plan"
tf apply -auto-approve tfplan; check $? "terraform apply"
tf output;                     check $? "terraform output"
tf state list;                 check $? "terraform state list"

log ""
log "Dependency graph recorded by Terraform for the EC2 instance:"
tf state show aws_instance.web

vpc="$(cd "$project" && "$terraform_bin" output -raw vpc_id)"
bucket="$(cd "$project" && "$terraform_bin" output -raw assets_bucket)"
log ""
log "Reading the created resources back through the AWS API:"
note awslocal ec2 describe-vpcs --vpc-ids "$vpc" --query 'Vpcs[0].{Id:VpcId,Cidr:CidrBlock,Tags:Tags}'
note awslocal ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" \
  --query 'Subnets[].{Id:SubnetId,Cidr:CidrBlock,Az:AvailabilityZone,Public:MapPublicIpOnLaunch}'
note awslocal ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc" \
  --query 'RouteTables[].{Id:RouteTableId,Routes:Routes[].{Dest:DestinationCidrBlock,Gw:GatewayId}}'
note awslocal ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vpc" \
  --query 'InternetGateways[].{Id:InternetGatewayId,State:Attachments[0].State}'
note awslocal ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc" \
  --query 'SecurityGroups[].{Name:GroupName,Ingress:IpPermissions}'
note awslocal ec2 describe-instances --filters "Name=vpc-id,Values=$vpc" \
  --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,State:State.Name,Subnet:SubnetId,PrivateIp:PrivateIpAddress}'
note awslocal s3 ls "s3://$bucket"

log ""
log "Inspecting Terraform state directly:"
note "$terraform_bin" -chdir="$project" state list
log ""
log "Resource count recorded in state: $(cd "$project" && "$terraform_bin" state list | wc -l | tr -d ' ')"

tf destroy -auto-approve; check $? "terraform destroy"
note awslocal ec2 describe-vpcs --vpc-ids "$vpc" || true
rm -f "$project/tfplan"

# ------------------------------------ Session 21: the final project's own cloud
project="$repo_dir/final-devops-project/terraform"
section "21-final-project-infrastructure"
tf init -upgrade;              check $? "terraform init"
tf fmt -check -recursive;      check $? "terraform fmt -check"
tf validate;                   check $? "terraform validate"
log ""
log "The container registry is valid Terraform and appears in the plan below."
log "It is left out of the applied run because ECR is not implemented in the"
log "community edition of the emulator; see the project README."
tf plan -var create_ecr_repository=true -target=aws_ecr_repository.notes
tf plan -out=tfplan;           check $? "terraform plan"
tf apply -auto-approve tfplan; check $? "terraform apply"
tf output;                     check $? "terraform output"
tf state list;                 check $? "terraform state list"

vpc="$(cd "$project" && "$terraform_bin" output -raw vpc_id)"
bucket="$(cd "$project" && "$terraform_bin" output -raw artifacts_bucket)"
log ""
log "Reading the created resources back through the AWS API:"
note awslocal ec2 describe-vpcs --vpc-ids "$vpc" --query 'Vpcs[0].{Id:VpcId,Cidr:CidrBlock}'
note awslocal ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" \
  --query 'Subnets[].{Id:SubnetId,Cidr:CidrBlock,Az:AvailabilityZone,Tags:Tags[?Key==`kubernetes.io/role/elb`]}'
note awslocal ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc" \
  --query 'SecurityGroups[?GroupName!=`default`].{Name:GroupName,Ingress:IpPermissions[].{From:FromPort,To:ToPort}}'
note awslocal s3api get-bucket-versioning --bucket "$bucket"
note awslocal s3api get-bucket-encryption --bucket "$bucket"

log ""
log "A second plan with no source change must report no differences:"
tf plan -detailed-exitcode
case "${PIPESTATUS[0]}" in
  0) log ""; log "PASS: the configuration is idempotent (exit 0, no changes)" ;;
  2) log ""; log "FAIL: drift detected (exit 2)"; failures=$((failures + 1)) ;;
  *) log ""; log "FAIL: terraform plan errored"; failures=$((failures + 1)) ;;
esac

tf destroy -auto-approve; check $? "terraform destroy"
rm -f "$project/tfplan"

echo ""
echo "Stages that reported a failure: $failures"
exit "$failures"
