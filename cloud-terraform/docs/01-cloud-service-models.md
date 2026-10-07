# Cloud service models

The usual three, plus the two that matter in practice.

| Model | You manage | The provider manages | Example |
| --- | --- | --- | --- |
| **IaaS** | OS, runtime, application, data | Hardware, network, virtualisation | EC2, EBS, VPC |
| **PaaS** | Application, data | Everything below the runtime | Elastic Beanstalk, App Runner, RDS |
| **SaaS** | Configuration and your data | Everything | Google Workspace, Datadog |
| **CaaS** | Container images, manifests | Orchestrator control plane, nodes | EKS, ECS |
| **FaaS** | A function | Everything, including when to run it | Lambda |

The useful way to read the table is as a line that moves: the further down, the less you operate and
the less you control. A VM gives you a kernel version and a patching schedule; Lambda gives you
neither and also no server to forget to patch.

## Where this homework sits

| Thing | Model |
| --- | --- |
| [The EC2 instance](../infrastructure/compute.tf) | IaaS |
| [The S3 bucket](../infrastructure/storage.tf) | IaaS storage, consumed as an API |
| [Kubernetes in the final project](../../final-devops-project/README.md) | CaaS. Managed as EKS, self-run here as kind |
| GitHub Actions | SaaS, with the runner as PaaS |

## Responsibility, concretely

The phrase "shared responsibility" is worth making specific. For the Session 19 EC2 instance:

| Concern | AWS | Me |
| --- | --- | --- |
| Physical datacentre, hypervisor | ✓ | |
| Host patching | ✓ | |
| Guest OS patching | | ✓ |
| Security group rules | | ✓ |
| Data on the EBS volume | | ✓ |
| EBS durability | ✓ | |
| Network isolation between tenants | ✓ | |
| Who may call the API | | ✓ (IAM) |

The rows on the right are where breaches happen. An open security group and an over-permissive IAM
policy are my mistakes to make, not the provider's.

## Deployment models

| Model | What it means | Why it is chosen |
| --- | --- | --- |
| Public cloud | Shared infrastructure, one provider | Cost, speed, no capital expense |
| Private cloud | Dedicated infrastructure | Regulation, legacy integration, existing hardware |
| Hybrid | Both, connected | Migration in progress, or data that cannot move |
| Multi-cloud | More than one provider | Avoiding lock-in, or acquisitions |

Multi-cloud is more often the result of history than of strategy. The cost is real: every managed
service that makes a provider worth using is the thing that cannot be made portable.

## Why the service model matters to a DevOps engineer

It decides what the pipeline deploys. IaaS means images and configuration management. CaaS means
container images and manifests, which is why [the final project](../../final-devops-project/README.md)
has a Dockerfile, a Helm chart and a GitOps definition rather than an AMI pipeline. FaaS means
deployment artefacts measured in kilobytes and a completely different debugging story.

It also decides what can break. With IaaS, a full disk is yours to notice. With PaaS, the same event
is the provider's alarm — and your outage anyway.
