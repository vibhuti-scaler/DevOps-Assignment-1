# IAM — Identity and Access Management

AWS's governance layer. Every API call in an AWS account is authenticated and authorised by IAM,
including calls Terraform makes.

## What it is

IAM answers one question for every request: **is this principal allowed to perform this action on
this resource, under these conditions?** It is global — not regional — and free.

The evaluation order matters more than the vocabulary:

1. An explicit **Deny** anywhere wins. Nothing overrides it.
2. Otherwise an explicit **Allow** in any applicable policy grants the request.
3. Otherwise the request is denied. **Default deny** is the starting point.

## Users

A long-lived identity for a human or an application, with either a console password or an access
key pair.

The practical guidance is to create as few as possible. A user's access key is a static credential
that lives until someone rotates it, and static credentials are how accounts get compromised. For
humans, federate through an identity provider or AWS IAM Identity Center. For workloads, use a role.

## Groups

A container for users, carrying policies. Users inherit every policy attached to every group they
belong to.

A group is a *permission set*, not an org chart. `Developers`, `BillingReadOnly`, `DatabaseAdmins`.
Groups cannot be nested and cannot be a principal in a policy — you cannot say "allow the Developers
group to assume this role"; you attach a policy to the group instead.

## Roles

An identity with permissions and **no credentials of its own**. A principal *assumes* a role and
receives temporary credentials that expire, usually within an hour.

A role has two policies, and conflating them causes most IAM confusion:

| | What it controls |
| --- | --- |
| **Trust policy** (assume-role policy) | *Who may assume the role.* An EC2 service principal, a Lambda, a user in another account, a GitHub Actions workflow via OIDC. |
| **Permissions policy** | *What the role may do once assumed.* |

Roles are the answer to almost every "how do I give X access to Y" question:

- An EC2 instance needs S3 — attach an **instance profile**, never bake a key into the AMI.
- A pod in EKS needs DynamoDB — IAM Roles for Service Accounts.
- A GitHub Actions workflow needs to push to ECR — an OIDC trust policy, so the repository holds no
  AWS key at all. This is the AWS equivalent of what `secrets.GITHUB_TOKEN` does in
  [the Session 17 pipeline](../../../devsecops/README.md).

## Policies

JSON documents listing statements. Each statement has an `Effect`, one or more `Action`s, a
`Resource`, and optionally a `Condition`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOneBucket",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::devops-homework-artifacts",
        "arn:aws:s3:::devops-homework-artifacts/*"
      ],
      "Condition": { "Bool": { "aws:SecureTransport": "true" } }
    }
  ]
}
```

Two details that trip people up: bucket-level actions such as `s3:ListBucket` take the bucket ARN,
while object-level actions take `bucket/*` — both are usually needed. And `"Version":
"2012-10-17"` is a policy-language version, not a date you may change.

| Policy type | Attached to | Typical use |
| --- | --- | --- |
| AWS managed | Users, groups, roles | Quick start. Usually far broader than needed. |
| Customer managed | Users, groups, roles | The normal choice: reusable and versioned. |
| Inline | One identity | A permission that must never be reused elsewhere. |
| Resource-based | The resource (bucket policy, KMS key policy) | Cross-account access, or allowing a service to reach the resource. |
| Permissions boundary | A user or role | A ceiling. The identity can never exceed it, however generous its own policies. |
| Service control policy (SCP) | An Organizations OU or account | An account-wide ceiling, e.g. "no region outside ap-south-1". |

## Permissions and least privilege

Least privilege means granting the narrowest set of actions on the narrowest set of resources that
lets the job succeed — and then narrowing again when usage data shows what is actually used.

A workable method:

1. Start from deny. Add actions as they fail, reading the exact action name from the error.
2. Scope `Resource` to specific ARNs. `"Resource": "*"` is acceptable for a handful of actions that
   genuinely have no resource, and suspicious otherwise.
3. Add `Condition` keys: source IP, MFA presence, `aws:RequestedRegion`, resource tags.
4. Review IAM Access Analyzer's findings and the last-accessed data, then remove what is unused.

## Best practices

- **No root for daily work.** Lock the root user with a hardware MFA device and use it only for the
  handful of tasks that require it.
- **MFA everywhere**, and `aws:MultiFactorAuthPresent` as a condition on anything destructive.
- **Roles over users** for workloads. Temporary credentials expire; access keys do not.
- **Rotate what you cannot eliminate.** Any remaining access key needs a rotation schedule.
- **Permissions boundaries** when delegating IAM itself, so a team can create roles without being
  able to create a role more powerful than their own.
- **CloudTrail on, in every region.** IAM tells you what is allowed; CloudTrail tells you what
  happened.
- **Tag everything** and use tag-based conditions (`aws:ResourceTag/Environment`) so one policy can
  separate dev from prod.

## Common use cases

| Need | Mechanism |
| --- | --- |
| An EC2 instance reads a bucket | Instance profile with a role scoped to that bucket. |
| A CI pipeline deploys to AWS | OIDC trust policy to the identity provider. No stored keys. |
| A vendor needs read-only access | A role with a trust policy naming their account and an `ExternalId` condition. |
| A developer may use dev but not prod | Tag-based conditions, or separate accounts with SCPs. |
| Stop anyone deleting the audit bucket | An explicit `Deny` on `s3:DeleteBucket` in an SCP. |

## Interview answers worth having ready

**Role vs user:** a user has permanent credentials and represents a specific identity; a role has no
credentials and is assumed temporarily by whoever its trust policy allows.

**Identity-based vs resource-based policy:** identity-based says "this principal may do X";
resource-based says "this resource may be acted on by Y". Cross-account access usually needs both.

**Why an explicit Deny cannot be overridden:** so a guardrail written once — in an SCP or a
boundary — cannot be undone by a permissive policy added later.
