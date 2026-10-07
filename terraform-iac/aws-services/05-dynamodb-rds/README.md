# DynamoDB and RDS — database services

AWS's two main managed database answers. They are not alternatives so much as different starting
assumptions: RDS gives you a relational database you already know how to use; DynamoDB gives you
predictable latency at any scale, provided the access pattern is known in advance.

---

# DynamoDB

## NoSQL

A managed key-value and document store. No servers, no version upgrades, no connection pool, and
single-digit-millisecond reads at effectively any volume.

The trade is real. There are no joins, no `GROUP BY`, and a query must specify a partition key.
Anything else is a full table scan, which is slow and expensive. The data model is designed around
the queries, not the entities — the opposite of normalising first and querying later.

## Tables

A table holds items and has no fixed schema beyond its key. Capacity comes in two modes:

| Mode | Billing | Use |
| --- | --- | --- |
| On-demand | Per request | Unpredictable or spiky traffic; nothing to tune. |
| Provisioned | Per reserved capacity unit per hour | Steady, predictable traffic. Cheaper, with auto-scaling available. |

## Items and attributes

An **item** is a row: one JSON-like document, at most 400 KB. An **attribute** is a field. Items in
the same table need not have the same attributes — only the key is mandatory. Types include scalars,
sets, lists and maps, so nesting is allowed.

## Partition key

The primary key, hashed to choose a physical partition. A table with only a partition key requires
it to be unique.

Partition key choice is the single most important decision in a DynamoDB table. All traffic for one
key value lands on one partition, so a key like `status` with three possible values creates a hot
partition and throttling while the table as a whole looks idle. High-cardinality, evenly distributed
values — a user id, an order id — are what the design wants.

## Sort key

The optional second half of a composite key. The partition key then selects a partition and the sort
key orders items within it, which is what makes range queries possible:

```text
PK = USER#42, SK = ORDER#2026-10-01
PK = USER#42, SK = ORDER#2026-10-05
PK = USER#42, SK = ORDER#2026-10-07

Query: PK = USER#42 AND SK BETWEEN ORDER#2026-10-01 AND ORDER#2026-10-06
```

Encoding a prefix into the sort key (`ORDER#`, `PROFILE#`, `SESSION#`) lets one table hold several
entity types and still answer "everything for this user" in one query. That is the single-table
design DynamoDB is usually written about.

Secondary indexes give alternative access paths: a **Local Secondary Index** keeps the partition key
and changes the sort key; a **Global Secondary Index** changes both and is effectively a separate,
asynchronously replicated table.

## Use cases

| Fits | Does not fit |
| --- | --- |
| Session stores, shopping carts, user profiles | Ad-hoc analytical queries |
| Event and IoT ingestion | Reporting with joins across entities |
| Leaderboards and time-series by entity | Anything where the access pattern is still unknown |
| Terraform state locking | Workloads that need transactions across many entities |

Worth knowing: **DynamoDB Streams** emits a change log that can trigger a Lambda, which is how most
event-driven AWS architectures are wired. **TTL** expires items automatically, at no cost, which is
the right way to clean up sessions.

---

# RDS

## Relational database

A managed relational database: AWS runs the host, the patching, the backups, the failover and the
replication; you run the schema and the queries. It is an ordinary database reached over an ordinary
connection, which is exactly the point — nothing in the application changes.

## Supported engines

| Engine | Notes |
| --- | --- |
| PostgreSQL | The usual default for new work. |
| MySQL / MariaDB | Large existing ecosystem. |
| Oracle, SQL Server | Licensed; migration targets. |
| Amazon Aurora | AWS's own PostgreSQL- and MySQL-compatible engine. Storage is distributed across three AZs, up to 15 read replicas, failover in seconds. |

Aurora Serverless v2 scales capacity continuously, which suits workloads that are idle most of the
time.

## DB instances

An instance has a class (`db.t3.micro`, `db.r6g.large`), storage (gp3 or provisioned IOPS), and a
**subnet group** that places it in specific subnets — private ones, in any sane design.

A **parameter group** holds engine settings and an **option group** holds engine features. Some
parameter changes are dynamic; others need a reboot, which is a scheduled event rather than a
command.

## Security

Defence in depth, each layer independent:

1. **Network** — private subnets, and a security group that allows 5432 only from the application
   tier's security group. Never `0.0.0.0/0`, and `publicly_accessible = false`.
2. **Encryption at rest** — KMS, set at creation. It cannot be enabled later; you snapshot, copy
   the snapshot with encryption, and restore.
3. **Encryption in transit** — TLS, enforced with `rds.force_ssl`.
4. **Authentication** — IAM database authentication issues short-lived tokens instead of passwords,
   or AWS Secrets Manager rotates the password automatically.
5. **Audit** — logs exported to CloudWatch; Performance Insights for query-level visibility.

## Backups

| Mechanism | Retention | Characteristics |
| --- | --- | --- |
| Automated backups | 0–35 days | Daily snapshot plus transaction logs. Enables point-in-time recovery to any second in the window. |
| Manual snapshots | Until deleted | Survive instance deletion. The only thing that survives a dropped database. |

Setting the retention to 0 disables automated backups and point-in-time recovery with it. Restoring
always creates a **new instance** — there is no in-place restore — so a recovery plan has to include
repointing the application.

## Multi-AZ

A synchronous standby in another Availability Zone, with automatic failover by DNS. The standby
serves no traffic: this is availability, not scale. Failover takes a minute or two and is triggered
by host failure, AZ failure or a maintenance event.

Multi-AZ **DB cluster** deployments (three instances) add two readable standbys and faster failover.

## Read replicas

Asynchronous copies that serve read traffic. Up to five for most engines, fifteen for Aurora. They
can live in another region, and can be promoted to a standalone primary.

| | Multi-AZ standby | Read replica |
| --- | --- | --- |
| Replication | Synchronous | Asynchronous |
| Serves reads | No | Yes |
| Purpose | Availability | Scale, and cross-region DR |
| Failover | Automatic | Manual promotion |

Because replication is asynchronous, a replica lags. An application that writes and immediately
reads its own write must send that read to the primary.

## Use cases

| Need | Choice |
| --- | --- |
| Transactional application with a relational schema | RDS PostgreSQL, Multi-AZ. |
| Read-heavy reporting against live data | RDS with read replicas. |
| High availability and fast failover at scale | Aurora. |
| Rare, bursty usage | Aurora Serverless v2. |
| Cross-region disaster recovery | Cross-region read replica, promoted on failure. |

---

## Choosing between them

| Question | DynamoDB | RDS |
| --- | --- | --- |
| Are the access patterns known up front? | Required | Not required |
| Joins and ad-hoc queries? | No | Yes |
| Scale ceiling | Effectively none | The largest instance, plus replicas |
| Operational burden | None | Patching windows, parameter tuning, capacity |
| Latency | Single-digit ms, predictable | Depends on query and instance |
| Cost model | Per request or per provisioned capacity | Per instance-hour, running or not |

The honest default for most applications is RDS, because schema flexibility at the start matters
more than the scale ceiling, and a relational database is the thing most teams can actually operate.
DynamoDB wins when the access pattern is genuinely fixed and the scale is genuinely large — or when
the operational model, with nothing to patch, is the deciding feature.

## Interview answers worth having ready

**Multi-AZ vs read replica:** Multi-AZ is a synchronous standby for availability and serves no
traffic; a read replica is asynchronous and serves reads.

**Why is DynamoDB partition key choice critical?** It determines physical partitioning. A
low-cardinality key concentrates traffic on one partition and throttles while the table looks idle.

**Can RDS encryption be turned on later?** No. Snapshot, copy the snapshot with encryption, restore.

**What does a DynamoDB scan cost?** It reads every item and consumes capacity proportional to the
whole table, whatever the filter returns. Filters are applied after the read, not before it.
