# S3 — Simple Storage Service

Object storage. The service [the Session 18 Terraform project](../../terraform-s3-demo/) creates,
so every feature below has a corresponding resource in that configuration.

## What it is

Durable object storage reached over HTTP. Not a filesystem: there is no append, no partial write and
no rename. You `PUT` a whole object and `GET` a whole object (or a byte range of one).

AWS designs for 99.999999999% (eleven nines) durability by replicating across at least three
Availability Zones. Durability is not availability — the data is still there during an outage; you
may not be able to reach it.

## Buckets

A container for objects, created in one region.

- **The name is globally unique across all of AWS.** Not per account, not per region. This is why
  [the Terraform configuration](../../terraform-s3-demo/main.tf) appends a random suffix rather
  than hard-coding a name.
- The name must be a valid DNS label: lower case, digits, hyphens, 3–63 characters.
- Buckets are regional. A bucket in `ap-south-1` is reached from anywhere, but the data does not
  leave that region unless replication is configured.
- Default limit of 100 buckets per account, raisable. Buckets are a coarse unit; prefixes inside one
  bucket are the usual way to separate things.

## Objects

A key, a value (up to 5 TB), metadata, and a version ID if versioning is on.

The key looks like a path and is not one. `logs/2026/10/07/app.log` is a single flat string; the
slashes exist so the console can render a tree and so prefix listings work. There are no
directories, which is why "deleting a folder" is really deleting every object with that prefix.

Objects over 100 MB should use multipart upload — parallel parts, resumable, and each part retried
independently. An abandoned multipart upload leaves parts that bill until removed, which is what the
`abort_incomplete_multipart_upload` lifecycle rule in the Session 18 configuration is for.

## Storage classes

| Class | Retrieval | Minimum duration | Use |
| --- | --- | --- | --- |
| Standard | Instant | None | Active data. |
| Intelligent-Tiering | Instant | None | Unpredictable access. Moves objects automatically for a small monitoring fee. |
| Standard-IA | Instant | 30 days | Backups read occasionally. |
| One Zone-IA | Instant | 30 days | Re-creatable data. One AZ, so cheaper and less durable. |
| Glacier Instant Retrieval | Instant | 90 days | Archives that must still be read immediately. |
| Glacier Flexible Retrieval | Minutes to hours | 90 days | Classic archives. |
| Glacier Deep Archive | Up to 12 hours | 180 days | Compliance retention measured in years. |

The minimum duration is the catch. An object moved to Standard-IA and deleted a week later is still
billed for thirty days, so an aggressive lifecycle policy on short-lived objects costs more than
leaving them in Standard.

## Versioning

Off by default. Once enabled it can be suspended but never removed.

With versioning on, a `PUT` to an existing key creates a new version and keeps the old one. A
`DELETE` writes a **delete marker** — the object disappears from listings and nothing is actually
freed. That is the property that makes versioning the main defence against both accidental deletion
and ransomware, and the reason a bucket can keep growing after everything "was deleted".

Two things to enable alongside it:

- **MFA Delete**, which requires an MFA token to delete a version permanently.
- **A lifecycle rule expiring noncurrent versions**, or storage grows without limit. That is exactly
  the rule in the Session 18 configuration:

```hcl
noncurrent_version_expiration {
  noncurrent_days = 30
}
```

## Lifecycle policies

Rules that transition or expire objects by age, scoped by prefix, tag or size.

```text
day 0    Standard
day 30   Standard-IA
day 90   Glacier Flexible Retrieval
day 365  expire
```

Transitions are one-way down the hierarchy and each has a minimum age. Lifecycle is per bucket and
evaluated asynchronously once a day, so an object does not move at the exact minute it qualifies.

## Encryption

| Option | Key held by | When to use |
| --- | --- | --- |
| SSE-S3 (`AES256`) | AWS, invisible | The default. On for every new bucket since 2023. |
| SSE-KMS | A KMS key you control | When key access needs its own audit trail or its own policy. |
| SSE-C | You, supplied per request | Rare; you manage key distribution. |
| Client-side | You, before upload | When AWS must never see plaintext. |

The Session 18 configuration sets `AES256` explicitly rather than relying on the account default, so
the intent is recorded in code and a change of default cannot silently weaken it.

In transit, enforce TLS with a bucket policy condition on `aws:SecureTransport` — encryption at rest
says nothing about the connection.

## Bucket policies and access control

Four mechanisms can grant access to an object, which is why S3 permissions have a reputation:

1. **IAM identity policies** — what a principal may do.
2. **Bucket policies** — resource-based, the usual way to grant cross-account or public access.
3. **ACLs** — the legacy per-object mechanism. Disabled by default on new buckets (`Bucket owner
   enforced`) and best left that way.
4. **Block Public Access** — an override that wins over all of the above.

Block Public Access is the one to set first. All four flags on, at the account level and the bucket
level:

```hcl
resource "aws_s3_bucket_public_access_block" "homework" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

A static website that genuinely needs public reads should be served through CloudFront with an
Origin Access Control, leaving the bucket private.

## Common use cases

| Need | Approach |
| --- | --- |
| Static website | S3 + CloudFront + OAC. Bucket stays private. |
| Build artefacts | Versioning on, lifecycle expiring old versions. This is [the final project's artifacts bucket](../../../final-devops-project/terraform/main.tf). |
| Terraform remote state | Versioning on, encryption on, and native S3 state locking. |
| Data lake | Parquet under date prefixes, queried with Athena. |
| Backups with a retention requirement | Object Lock in compliance mode — not even the root user can delete before the retention date. |
| Log delivery | A bucket per account, lifecycle to Glacier after 90 days. |

## Interview answers worth having ready

**Is S3 a filesystem?** No. Flat key-value store; keys contain slashes for display purposes.

**What happens when you delete from a versioned bucket?** A delete marker is written. The data
remains and still bills until the version itself is deleted or expired by a lifecycle rule.

**How do you make a bucket genuinely private?** Block Public Access at account and bucket level,
ACLs disabled, a bucket policy denying `aws:SecureTransport: false`, and encryption enforced.

**Why is the bucket name globally unique?** Because the original addressing is virtual-hosted —
`bucket.s3.region.amazonaws.com` — so the name is part of a DNS name.
