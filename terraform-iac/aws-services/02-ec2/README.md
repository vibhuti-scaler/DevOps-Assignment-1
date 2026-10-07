# EC2 — Elastic Compute Cloud

Virtual machines. The service most other AWS compute is measured against, and the one
[Session 19](../../../cloud-terraform/README.md) provisions with Terraform.

## What it is

Rentable virtual servers inside a VPC. You choose the image, the size, the network placement and the
firewall rules; AWS provides the hypervisor, the hardware and the physical network.

The interesting part is that an instance is not one object. It is an AMI plus an instance type plus
a subnet plus security groups plus EBS volumes plus (optionally) an IAM role — and getting any one
of them wrong is a different failure mode.

## AMI — Amazon Machine Image

The template an instance boots from: a root volume snapshot, plus the block device mapping and
launch permissions.

Two things follow from how AMIs work:

- **An AMI ID is region-specific.** `ami-0abc...` in `ap-south-1` is a different image, or nothing
  at all, in `us-east-1`. Hard-coding one is the most common reason a Terraform configuration works
  in one region and fails in another. [The Session 19 configuration](../../../cloud-terraform/infrastructure/compute.tf)
  therefore uses a `data "aws_ami"` lookup with a name filter and `most_recent = true`.
- **AMIs go stale.** A new one is published whenever the base OS is patched. Baking your own
  (with Packer) gives reproducible launches at the cost of owning the patching schedule.

## Instance types

A family, a generation and a size: `t3.micro`, `m6i.large`, `c7g.xlarge`.

| Family | Optimised for | Typical use |
| --- | --- | --- |
| `t` | Burstable | Dev boxes, low-traffic services. CPU credits accrue when idle and are spent when busy. |
| `m` | Balanced | General-purpose application servers. |
| `c` | Compute | Batch processing, CI runners, game servers. |
| `r`, `x` | Memory | Caches, in-memory databases. |
| `i`, `d` | Storage | Local NVMe for high IOPS. |
| `g`, `p` | Accelerated | GPU workloads. |

A `g` suffix in the generation (`c7g`) means AWS Graviton — Arm. Cheaper per unit of work, and it
requires Arm builds of everything, which is a real constraint if any dependency ships amd64 only.

The `t` family's credit model deserves attention: a `t3.micro` under sustained load exhausts its
credits and is throttled to its baseline, which looks like a mysterious performance cliff hours
after a deployment.

## Key pairs

An SSH public/private key pair. AWS keeps the public key and injects it into the instance at first
boot; **the private key is downloadable exactly once**, at creation.

Modern practice is to avoid them entirely. AWS Systems Manager Session Manager gives shell access
through the SSM agent and IAM, which means no key to lose, no port 22 open, and every session
logged to CloudTrail.

## Security groups

A stateful virtual firewall attached to a network interface.

- **Stateful**: allow an inbound connection and its replies are allowed out automatically. There is
  no need for a matching egress rule.
- **Allow-only**: there is no deny rule. Anything not allowed is denied.
- **Default egress is all traffic**; default ingress is nothing.
- Up to five per instance, evaluated as a union.

The most useful property is that a rule's source can be **another security group** rather than a
CIDR. [The Session 19 app tier](../../../cloud-terraform/infrastructure/network.tf) allows port 8000
only from the web tier's security group, so the rule keeps working when instance addresses change
and no address list has to be maintained.

Security groups vs network ACLs: see [the VPC notes](../04-vpc/README.md).

## EBS — Elastic Block Store

Network-attached block storage, independent of the instance's lifecycle.

| Type | Characteristics | Use |
| --- | --- | --- |
| `gp3` | 3,000 IOPS and 125 MB/s baseline, throughput configurable separately from size | The sensible default. |
| `gp2` | IOPS tied to volume size | Legacy; `gp3` is cheaper and faster. |
| `io1`/`io2` | Provisioned IOPS, `io2 Block Express` for the highest | Databases with a hard latency requirement. |
| `st1`/`sc1` | HDD, throughput-optimised or cold | Large sequential reads, logs, archives. |

Points worth knowing: a volume lives in one Availability Zone and can only attach to an instance in
that zone; snapshots are incremental and stored in S3; encryption is set at creation and cannot be
toggled afterwards (you snapshot, copy with encryption, restore); and `delete_on_termination`
defaults to `true` for the root volume and `false` for additional ones — which is the cause of both
"my data vanished" and "why am I paying for 40 orphaned volumes".

Instance store is the other option: physical NVMe on the host, very fast, and **erased when the
instance stops**. Caches and scratch space only.

## Public vs private IP

| | Private IP | Public IP | Elastic IP |
| --- | --- | --- | --- |
| Where it comes from | The subnet's CIDR | AWS's pool | Allocated to your account |
| Stable across stop/start | Yes | **No** | Yes |
| Visible inside the OS | Yes | No — NAT is done by the network | No |
| Cost | Free | Small hourly charge | Charged when not attached |

The row that surprises people: `ip addr` inside the instance shows only the private address. The
public address is translated by the VPC network, which is why software that binds to its "public IP"
fails.

An instance gets a public IP only if its subnet has `map_public_ip_on_launch` set (or it is
requested at launch) **and** the subnet's route table sends `0.0.0.0/0` to an Internet Gateway.
Without the route, the address exists and reaches nothing.

## Instance lifecycle

```text
pending ──▶ running ──┬──▶ stopping ──▶ stopped ──▶ (start) ──▶ pending
                      ├──▶ rebooting ──▶ running
                      └──▶ shutting-down ──▶ terminated
```

| Transition | What happens |
| --- | --- |
| **Stop** | The instance is deallocated from its host. EBS volumes survive; instance store is lost; the public IP is released unless it is an Elastic IP. No compute charge; storage still bills. |
| **Start** | It may land on a different host. New public IP. |
| **Reboot** | Stays on the same host; nothing is lost. |
| **Terminate** | Gone. Root volume deleted unless `delete_on_termination` is false. |
| **Hibernate** | RAM is written to the encrypted root volume and restored on start. Requires opt-in at launch. |

`disable_api_termination` is worth setting on anything that matters.

## Common use cases

| Need | Approach |
| --- | --- |
| Web servers behind a load balancer | Auto Scaling group across two or more Availability Zones, in private subnets, with an ALB in public ones. |
| Batch processing | Spot instances, up to ~90% cheaper, with checkpointing because they can be reclaimed on two minutes' notice. |
| A bastion | Replace it with Session Manager. |
| Legacy software needing a fixed address | Elastic IP, or better, a Network Load Balancer in front. |
| Kubernetes nodes | EKS managed node groups, which are Auto Scaling groups with the bootstrap handled. |

## Interview answers worth having ready

**Stop vs terminate:** stop deallocates compute and keeps EBS; terminate destroys the instance and,
by default, its root volume.

**Security group vs NACL:** security groups are stateful, allow-only, and attached to interfaces;
NACLs are stateless, support deny, and attached to subnets.

**Why does my instance have no internet access?** In order: does the subnet's route table have a
`0.0.0.0/0` route; does it point at an Internet Gateway (public) or a NAT Gateway (private); does
the instance have a public IP; does the security group allow the egress; does the NACL allow the
return traffic on ephemeral ports.
