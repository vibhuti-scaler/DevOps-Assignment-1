# VPC — Virtual Private Cloud

The network every other resource sits in. [Session 19](../../../cloud-terraform/README.md) builds
one with Terraform, so the objects below map directly onto that configuration.

## What it is

A logically isolated network inside a region: your own address range, your own subnets, your own
routing and your own firewalls. Nothing reaches a VPC from outside unless a path is created
explicitly.

A VPC spans every Availability Zone in its region. A *subnet* belongs to exactly one.

## CIDR

The address range, written as `10.20.0.0/16`: the prefix length says how many leading bits are
fixed, so `/16` fixes 16 bits and leaves 65,536 addresses.

| Block | Addresses | Typical use |
| --- | --- | --- |
| `/16` | 65,536 | A whole VPC. |
| `/20` | 4,096 | A large subnet. |
| `/24` | 256 | A normal subnet. |
| `/28` | 16 | The smallest AWS allows. |

AWS reserves **five addresses in every subnet**: network, VPC router, DNS, future use, and
broadcast. A `/28` therefore gives 11 usable addresses, not 16 — which matters when sizing subnets
for a Kubernetes cluster where every Pod may take an address.

Two rules worth internalising:

- **Plan for peering.** Two VPCs with overlapping CIDRs can never be peered or joined by a Transit
  Gateway. The 10.0.0.0/8 space is large; spending it carefully at the start is free.
- **A VPC CIDR cannot shrink.** It can be extended with additional blocks; the primary cannot change.

Terraform's `cidrsubnet()` does the arithmetic rather than leaving magic numbers in the code:

```hcl
cidr_block = cidrsubnet(var.vpc_cidr, 8, each.value)       # 10.20.0.0/24, 10.20.1.0/24 …
cidr_block = cidrsubnet(var.vpc_cidr, 8, each.value + 10)  # 10.20.10.0/24, 10.20.11.0/24 …
```

## Subnets

A slice of the VPC CIDR, bound to one Availability Zone.

**There is no "public subnet" setting.** A subnet is public if, and only if, its route table sends
`0.0.0.0/0` to an Internet Gateway. Everything else is a consequence of that one fact. The
`map_public_ip_on_launch` flag only decides whether instances get a public address; without the
route, that address reaches nothing.

The conventional layout, and the one Session 19 builds:

```text
VPC 10.20.0.0/16
├── public  10.20.0.0/24   ap-south-1a   route: 0.0.0.0/0 → Internet Gateway
├── public  10.20.1.0/24   ap-south-1b   route: 0.0.0.0/0 → Internet Gateway
├── private 10.20.10.0/24  ap-south-1a   route: local only
└── private 10.20.11.0/24  ap-south-1b   route: local only
```

Two Availability Zones minimum, because a load balancer and most managed services require subnets in
at least two.

## Route tables

A list of destination CIDRs and targets. Every subnet is associated with exactly one; a route table
can serve many subnets.

Every route table has an implicit `local` route for the VPC CIDR which cannot be removed — that is
why any two instances in a VPC can reach each other regardless of routing, and why security groups
rather than routes are the tool for separating tiers.

Routes are matched most-specific-first: `10.20.5.0/24 → peering` wins over `0.0.0.0/0 → igw`.

## Internet Gateway

A horizontally scaled, highly available component attached to the VPC. One per VPC.

It does two things: routes traffic between the VPC and the internet, and performs one-to-one NAT
between an instance's private address and its public address. That NAT is why the OS only ever sees
the private address.

An IGW does nothing on its own. It needs a route table entry pointing at it, and the instance needs
a public address.

## NAT Gateway

Lets instances in **private** subnets reach the internet outbound, while nothing can initiate a
connection inbound.

| | Internet Gateway | NAT Gateway |
| --- | --- | --- |
| Direction | Both ways | Outbound only |
| Placed in | The VPC | A **public** subnet |
| Cost | Free | Hourly charge plus per-GB processing |
| Needs | A public IP on the instance | An Elastic IP on the gateway |

Two things catch people out. The NAT Gateway lives in a *public* subnet and is referenced by the
*private* subnet's route table — putting it in the private subnet produces a quiet, total failure.
And it is zonal: one per Availability Zone for real resilience, which multiplies the cost. Session
19 leaves it out and says so, because it bills hourly whether or not anything uses it, and a VPC
Endpoint is often the cheaper answer for the specific case of reaching S3 or DynamoDB.

## Security groups

Stateful, allow-only firewalls attached to network interfaces. Covered in detail in
[the EC2 notes](../02-ec2/README.md).

The property that matters most in a VPC design: a rule's source can be another security group. That
replaces address management with intent — "the app tier accepts traffic from the web tier" survives
every scaling event and every instance replacement.

## Network ACLs

Stateless packet filters attached to **subnets**.

| | Security group | Network ACL |
| --- | --- | --- |
| Attached to | A network interface | A subnet |
| State | Stateful — replies are automatic | Stateless — return traffic needs its own rule |
| Rules | Allow only | Allow **and** deny |
| Evaluation | All rules, as a union | In number order, first match wins |
| Default | Deny inbound, allow outbound | Allow everything |

Stateless is the part that bites. Allowing inbound 443 without a matching outbound rule for
ephemeral ports (1024–65535) produces a connection that establishes and then hangs.

In practice: use security groups for everything, and reach for a NACL only to block something at the
subnet edge — a specific address range, say — because security groups cannot express deny.

## Public vs private subnet, summarised

| | Public | Private |
| --- | --- | --- |
| Route for `0.0.0.0/0` | Internet Gateway | NAT Gateway, or nothing |
| Reachable from the internet | Yes, if a security group allows it | No |
| Can reach the internet | Yes | Only through a NAT Gateway |
| What belongs there | Load balancers, NAT Gateways, bastions | Application servers, databases, Kubernetes nodes |

The rule of thumb: if something does not need to be reached from the internet, it belongs in a
private subnet. A load balancer in public subnets with every instance private is the standard shape,
and it is what [the final project's Terraform](../../../final-devops-project/terraform/main.tf) tags
its subnets for.

## Interview answers worth having ready

**What makes a subnet public?** A route to an Internet Gateway. Nothing else.

**Security group vs NACL?** Stateful per-interface allow-lists versus stateless per-subnet rules
that can also deny.

**Why can't these two VPCs be peered?** Overlapping CIDRs. Peering also does not transit: A–B and
B–C does not give A–C.

**Why does my private instance have no outbound internet?** Either no NAT Gateway, or the NAT
Gateway is in the wrong subnet, or the private route table does not point at it.

**How many usable addresses in a /24?** 251. AWS reserves five.
