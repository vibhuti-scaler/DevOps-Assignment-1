# Regions and Availability Zones

## Region

A geographic area — `ap-south-1` (Mumbai), `eu-west-1` (Ireland) — containing several isolated
Availability Zones. Regions are independent of each other by design: an outage in one does not
propagate, and data does not move between them unless something is configured to move it.

Choosing one is four trade-offs:

| Factor | Why it matters |
| --- | --- |
| Latency | Physics. Mumbai to Ireland is ~120 ms round trip and nothing changes that. |
| Data residency | Many jurisdictions require data to stay in-country. |
| Price | The same instance costs noticeably different amounts in different regions. |
| Service availability | New services reach `us-east-1` first and some never reach smaller regions. |

A few services are global: IAM, Route 53, CloudFront, and S3 bucket *names*. Everything else is
regional, which includes the AMI IDs that make a hard-coded one unportable.

## Availability Zone

One or more discrete datacentres within a region, with independent power, cooling and networking,
connected to the other zones by low-latency private links — single-digit milliseconds, which is
close enough for synchronous replication.

The zone letter is **per account**. `ap-south-1a` in one account is not necessarily the same physical
zone as `ap-south-1a` in another; AWS randomises the mapping so that everyone does not crowd into
"a". The stable identifier is the AZ ID (`aps1-az1`), which is what to use when two accounts must
agree.

## Why two zones, minimum

[The Session 19 configuration](../infrastructure/variables.tf) refuses to run with fewer:

```hcl
validation {
  condition     = length(var.availability_zones) >= 2
  error_message = "At least two Availability Zones are needed for a highly available subnet layout."
}
```

Three reasons, in order of how soon they bite:

1. **Managed services require it.** An Application Load Balancer needs subnets in at least two
   zones. So does an RDS Multi-AZ deployment. A one-zone VPC simply cannot host them.
2. **A zone is a realistic failure unit.** Zone-wide outages happen; region-wide outages are rare.
3. **It forces the right design early.** Retrofitting a second zone into a running system means
   renumbering subnets, which is exactly the change `for_each` was chosen to make survivable.

## What spans what

```text
Region  ap-south-1
├── AZ ap-south-1a ── subnet 10.20.0.0/24 (public), 10.20.10.0/24 (private)
├── AZ ap-south-1b ── subnet 10.20.1.0/24 (public), 10.20.11.0/24 (private)
└── AZ ap-south-1c
```

| Resource | Scope |
| --- | --- |
| VPC, route tables, security groups, S3 bucket | Region |
| Subnet, EC2 instance, EBS volume, NAT Gateway, RDS instance | One Availability Zone |
| Internet Gateway, Application Load Balancer | Region, operating across zones |
| IAM, Route 53, CloudFront | Global |

Two consequences follow directly from that table. An EBS volume can only attach to an instance in
its own zone, which is the same constraint as a `ReadWriteOnce` PersistentVolumeClaim in Kubernetes
and for the same reason. And a NAT Gateway is zonal, so a genuinely resilient design needs one per
zone — which is why [Session 19](../README.md) leaves it out and says so rather than deploying one
and calling the result highly available.

## Beyond zones

- **Local Zones** place compute closer to a metro area for latency-sensitive workloads.
- **Wavelength Zones** sit inside mobile operator networks.
- **Outposts** are AWS hardware in your own datacentre, managed through the same APIs.

## Multi-region

Only when there is a reason, because the cost is high: cross-region replication charges, data
transfer, and the hard part — deciding what happens to writes during a failover. Most systems that
claim multi-region are really single-region with a cross-region backup, which is a legitimate design
and should be described as such.
