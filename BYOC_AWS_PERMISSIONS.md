# BYOC AWS 권한·자원 전수 목록 (B사 → PM팀 권한 부여 신청용)

> **목적**: B사 AWS 계정에 **Arkraft (한정)** 를 이식하기 위해, B사 보안팀이 PM팀(Quantit + B사 합작 운영팀)에게 부여해야 할 AWS 자원·IAM 권한의 전수 목록. PM팀이 이 권한을 받으면 Quantit 서포트로 arkraft 인프라 시스템을 B사 AWS 계정에 이식 가능.
>
> **⚠️ 범위 (arkraft 한정)**:
> - **포함**: arkraft-api (Backend), arkraft-web (Frontend), arkraft-agent-* (alpha/insight/portfolio/report/extract/data), agent-manager. 이들이 가동되기 위한 필수 AWS 자원 (EKS / RDS / ElastiCache / S3 / ECR / Bedrock / KMS / Secrets Manager / Route53 / ACM / ALB / VPC / NAT / AmazonMQ).
> - **제외 (Quantit 내부 또는 별도 시스템 — B사 PoC 와 무관)**: Quanda 시스템 (agent-memory AOSS, Bedrock Knowledge Base, quanda-agent IRSA), Atlantis (Quantit Terraform GitOps), WAF (Atlantis ALB 보호 전용), SSM Bastion (Quantit ops 디버깅), EC2 Image Builder (gVisor AMI — Quantit sandbox 용), agent-sandbox + Athena + Glue Data Catalog (Quantit 데이터 탐색), VPC Peering (Quantit 내부 다른 VPC 연결), Loki/Grafana/Prometheus (Quantit 자체 호스팅 observability — B사가 자체 솔루션 사용 권장), GitHub Actions OIDC + CI Role (Quantit CI 시스템 — B사가 자체 CI 사용 시 면제).
> - 제외 자원은 §3 / §7 에 ~~취소선~~ + "**arkraft 범위 밖**" 표시로 남기되, §9 신청 체크리스트에서는 제외.
>
> **컨텍스트**: B사 PoC 패키지 → B사 보안팀이 PM팀(Quantit 서포트 + B사 합작 운영팀)에게 권한 부여 시 사용할 신청서 형태. Quantit AWS 어드민 권한으로 운영 중이라 운영자 본인이 무의식적으로 사용 중인 권한이 누락될 위험을 다층 reviewer (Reviewer / QA / Security / Completeness / AWS-Architect) 로 다섯 번 점검.
>
> **Region 정책**: 본 문서는 `ap-northeast-2` (Seoul) 기준. B사 실제 deploy region 이 다를 경우 (B사 본사 위치 NYC → `us-east-1` 가능성) §8 "Region 변경 시 영향" 참고. **Bedrock 은 already cross-region** (`us`, `eu`, `ap`, `global` inference profiles 모두 사용 중) — region 변경 시 검토 우선순위.
>
> **운영 AWS 계정 (Quantit prod)**: `696201523565` — B사 계정 ID 와 무관하지만 ARN 패턴 비교용 참고.

---

## 1. 개요

### 1.1 문서 목적

Arkraft 인프라를 B사 AWS 계정에 이식하기 위해 PM팀(Quantit 서포트 + B사 합작)이 받아야 할 IAM Role · IAM Policy · AWS 자원의 전수 목록. B사 보안팀이 이 문서를 보고 PM팀에게 적절한 AWS 권한을 부여하면, Quantit가 그 권한으로 arkraft 인프라 시스템을 이식한다.

**역할 분담**:
- **B사 보안팀**: 본 문서 검토 → PM팀 IAM Principal 에 권한 부여 결정 → 실제 IAM Role/User/SSO 매핑 발급
- **PM팀** (권한 수령): 본 문서의 IAM Role 들을 자기 또는 자기가 가진 cross-account assume role 로 받아 사용
- **Quantit (이식 서포트)**: PM팀이 받은 권한으로 Terraform/Helm 적용 + 실제 가동까지 책임

**Trust Policy 주의** (§3 모든 IRSA Trust): 본 문서의 Trust 예시는 **EKS Pod 가 IRSA 로 assume** 하는 패턴 (운영 시나리오). 이식 작업 자체는 PM팀 IAM identity (User / Role / SSO) 가 별도 admin-equivalent 또는 service-별 deploy role 로 수행. **이식용 PM팀 권한과 운영용 Pod IRSA 권한은 분리** (§3 의 IRSA Trust 가 PM팀 identity 가 되면 안 됨).

### 1.2 신청 우선순위 (Tier 분류)

| Tier | 분류 | 자원 |
|------|------|------|
| **Tier-1 (필수)** | 미가동 자원, 신청 즉시 시작 | EKS · RDS · ElastiCache · S3 · ECR · Bedrock · KMS · Secrets Manager · Route53 · ACM · ALB/NLB · VPC/Subnet/NAT |
| **Tier-2 (운영)** | 가동 후 즉시 필요 | Karpenter (EC2) · EBS CSI · ALB Controller · External-DNS · External-Secrets · CloudWatch Logs · Argo Workflows S3 artifact · AmazonMQ (RabbitMQ) |
| **Tier-별도** | Cognito 미사용 확정 | ai-infra Terraform 0건 + app code grep 0건 (§7.7, §10.4 검증). Arkraft 인증은 다른 메커니즘 (JWT 자체 발급) |

### 1.3 Region 정책

- 본 문서: `ap-northeast-2` (Seoul) 기준.
- B사 실제 위치 (NYC) 고려: latency·data residency 관점에선 `us-east-1` 또는 `us-east-2` 권장 가능.
- Bedrock 은 이미 cross-region inference profile 사용 (`us.anthropic.*`, `eu.anthropic.*`, `ap.anthropic.*`, `global.anthropic.*`) — region 변경 시 inference profile 패턴이 그대로 통과.
- 자세한 영향 분석은 §8 참고.

### 1.4 신청 단위

본 문서는 다음 4개 단위로 권한을 정리:

- **AWS Service 단위 + 사유** (§2) — 보안팀 신청서 첫 페이지 요약용.
- **IAM 최소권한 정책 JSON** (§3) — Action·Resource·Condition 조합. **`*FullAccess` 추천 안 함**. `Resource: "*"` 는 Describe-only API 가 강제하는 경우만 + 사유 코멘트.
- **AWS Managed Policy 매핑 (참조용)** (§4) — 빠른 fallback 용 참조. 추천 아님.
- **IRSA → IAM Role → K8s ServiceAccount 매핑** (§5, §6) — Pod 내부에서 어떻게 권한이 흘러가는지.

---

## 2. AWS Service 매트릭스

| # | Service | 사용 컴포넌트 | 1줄 사유 | Region 의존성 | 출처 |
|---|---------|-------------|---------|--------------|------|
| 1 | **EKS** | 전체 (control plane) | K8s 클러스터 — 모든 워크로드 (api, web, agent-*, monitoring, gitops) 의 호스팅 | `ap-northeast-2` | `ai-infra/aws/eks*.tf`, `arkraft-deploy/*` |
| 2 | **EC2** (Karpenter) | NodePool (on-demand + spot) | EKS 노드 자동 프로비저닝. agent pod 4 CPU/24Gi 단위 spawn | region-bound | `ai-infra/karpenter/` |
| 3 | **EBS** (CSI) | StatefulSet 볼륨 (RDS/Redis/Argo workdir 등) | Pod 영속 볼륨 (gp3) | region-bound | `ai-infra/aws/eks-ebs-csi*.tf` |
| 4 | **RDS PostgreSQL** | api server | 메타데이터 DB (사용자, 세션, alpha topic, portfolio, community 등) | region-bound | `ai-infra/aws/rds.tf` |
| 5 | **ElastiCache Redis** | api + agent-* | 세션 캐시, SSE event 큐, data-query 캐시 (DB 0/2/3 분리) | region-bound | `ai-infra/aws/elasticache.tf` |
| 6 | **S3** | api + agent-* + Argo Workflow artifact | `arkraft-production` (prod data) + `ai-infra-argo-workflows-logs` (agent run artifact) | region-bound | `ai-infra/aws/s3/` |
| 7 | **ECR** | EKS pull (production deploy 만) | arkraft 서비스 image repository: `ark/arkraft-api`, `ark/arkraft-web`, `ark/arkraft-agent-{alpha,insight,portfolio,report,extract,data}`, `ark/arkraft-agent-manager` | region-bound | `ai-infra/aws/ecr/` |
| 8 | **Bedrock** | agent-* | LLM inference. anthropic.* foundation + cross-region inference profile (`us.`, `eu.`, `ap.`, `global.`) | **cross-region** | `ai-infra/main.tf` (arkraft_agent_irsa bedrock policy) |
| 9 | **KMS** | api + RDS + S3 + Secrets Manager | 데이터 암호화. alias `alias/arkraft/*` | region-bound | `ai-infra/aws/kms/` |
| 10 | **Secrets Manager** | api (RDS creds) + RabbitMQ admin | RDS credentials + RabbitMQ admin (External-Secrets 가 sync) | region-bound | `ai-infra/aws/rds/`, `ai-infra/rabbitmq/` |
| 11 | **Route53** | external-dns | B사 도메인 hosted zone + ALB/NLB DNS record 자동 생성 | global | `ai-infra/aws/route53/` |
| 12 | **ACM** | ALB/NLB TLS | wildcard cert | region-bound (ALB 와 동일) | `ai-infra/aws/route53/` |
| 13 | **ELBv2** (ALB/NLB) | Istio ingress | external-gateway (NLB public), internal-gateway (NLB private) — arkraft api/web 인그레스 | region-bound | `ai-infra/istio/` |
| 14 | **VPC + NAT + EIP** | network 기반 | VPC, subnet (3 AZ), NAT (private subnet egress), EIP (NAT 용) | region-bound | `ai-infra/aws/vpc.tf` |
| 15 | **VPC Endpoints** | 비용 절감 | S3, ECR, Secrets Manager, KMS 등 private subnet 통신 | region-bound | `ai-infra/aws/vpc-endpoints.tf` |
| 16 | **AmazonMQ** (RabbitMQ) | api + agent-* (worker queue) | `m7g.large` (Graviton) multi-AZ. 비동기 작업 큐 | region-bound | `ai-infra/aws/rabbitmq.tf` |
| ~~18~~ | ~~DynamoDB~~ | ~~alpha-pool~~ | **제거됨 (ARK-1518, alpha-pool 내재화)** — `dynamodb_tables = {}` | — | — |
| ~~19~~ | ~~Lambda alpha-migrator~~ | ~~scheduled ETL~~ | **제거됨 (ARK-1518)** — `aws/alpha-migrator/` 디렉터리 자체 삭제 | — | — |
| ~~20~~ | ~~EventBridge alpha-migrator~~ | ~~Lambda schedule~~ | **제거됨 (ARK-1518)** — Karpenter spot interruption rule 만 잔존 | — | — |
| 21 | **CloudWatch Logs** | EKS control plane + Karpenter + Argo Workflows + Istio + External-DNS | EKS / agent run / 인프라 log | region-bound | EKS 자동 + Karpenter 자동 |
| 22 | **STS** | IRSA AssumeRoleWithWebIdentity | 모든 Pod 의 IAM Role assume mechanism | global | (모든 IRSA module) |
| 23 | **IAM** | api/agent IRSA + EKS Pod Identity (Karpenter) | Role/Policy/OIDC provider 관리. **Cognito 미사용 확정** | global | `ai-infra/aws/iam/`, `ai-infra/main.tf` |

> **참고**: web chart 는 ServiceAccount 미설정 (default SA 사용) — Pod 내부에서 직접 AWS API 호출 안 하고 BFF 가 api 로 위임하는 패턴. 별도 IRSA 불필요.
>
> **Cognito**: ai-infra Terraform 에 Cognito 자원 0건 확인. arkraft-api 가 JWT 검증을 한다면 외부 IdP 또는 자체 발급. §10 출처/근거에서 재확인 필요 (subagent 3 결과 대기 중).

---

## 3. IAM 최소권한 정책 JSON

> 각 IAM Role 별로 grouped. 각 JSON 앞에 "이 Role 을 assume 하는 Pod / SA" 명시. **`*FullAccess` 사용 금지**. `Resource: "*"` 는 AWS API 가 강제하는 경우만 + 사유 코멘트.

### 3.1 `arkraft-api-server-role`

**현재 운영 Trust**: namespace `*` SA `*` (wildcard). 
**B사 신청 권장 Trust** (narrow): `system:serviceaccount:arkraft:arkraft-api` 만 assume.

> ⚠️ **CRITICAL — Security**: 현 ai-infra Terraform 의 Trust 가 `*:*` wildcard. B사 신청 시 반드시 narrow 권장 Trust 로 작성:
> ```json
> {
>   "Effect": "Allow",
>   "Principal": { "Federated": "{OIDC_PROVIDER_ARN}" },
>   "Action": "sts:AssumeRoleWithWebIdentity",
>   "Condition": {
>     "StringEquals": {
>       "{OIDC_ISSUER}:aud": "sts.amazonaws.com",
>       "{OIDC_ISSUER}:sub": "system:serviceaccount:arkraft:arkraft-api"
>     }
>   }
> }
> ```

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3DataBuckets",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::arkraft-production",
        "arn:aws:s3:::arkraft-production/*",
        "arn:aws:s3:::arkraft-staging",
        "arn:aws:s3:::arkraft-staging/*",
        "arn:aws:s3:::arkraft.quantit.ai",
        "arn:aws:s3:::arkraft.quantit.ai/*"
      ]
    },
    {
      "Sid": "S3FinterReadOnly",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::c2-performance-data-production",
        "arn:aws:s3:::c2-performance-data-production/*"
      ],
      "//comment": "외부 account 의 read-only 데이터. cross-account bucket policy 도 별도 필요."
    },
    {
      "Sid": "KMSDataKeyForEncryptedS3",
      "Effect": "Allow",
      "Action": [
        "kms:GenerateDataKey",
        "kms:Decrypt",
        "kms:DescribeKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringLike": {
          "kms:RequestAlias": "alias/arkraft/*"
        }
      }
    },
  ]
}
```

> **Resource: "\*" 사유 (KMS)**: KMS 의 `kms:RequestAlias` Condition 으로 alias 패턴이 narrow 됨 — 실제 키는 condition 으로 제한. AWS 공식 패턴.
>
> **Glue Data Catalog 제거 (iter 8)**: 이전 iter 에서 추정으로 추가됐던 `GlueDataCatalogReadOnly` Statement 는 **제거**. arkraft-api/src 에 boto3.client('glue') 호출 0건 확인 (Completeness reviewer 검증). 실제 사용처 없음. 신청 불필요.

### 3.2 `arkraft-agent-role` (production agent sandbox)

**Assume**: namespace `arkraft-sandbox` 의 ServiceAccount `*` (alpha/insight/portfolio/report/extract/data 6개 agent 의 wildcard SA). **wildcard SA 는 Argo Workflow 가 동적으로 SA 생성하기 때문**.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3AgentArtifactAndProductionData",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::ai-infra-argo-workflows-logs",
        "arn:aws:s3:::ai-infra-argo-workflows-logs/*",
        "arn:aws:s3:::arkraft-production",
        "arn:aws:s3:::arkraft-production/*"
      ]
    },
    {
      "Sid": "AOSSAlphaPoolVectorAndAgentMemory",
      "Effect": "Allow",
      "Action": [
        "aoss:APIAccessAll",
        "aoss:BatchGetCollection"
      ],
      "Resource": "arn:aws:aoss:ap-northeast-2:{ACCOUNT_ID}:collection/*"
    },
    {
      "Sid": "BedrockClaudeModelsAllRegionInferenceProfiles",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-opus-4-7*",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-6*",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5*",
        "arn:aws:bedrock:*:{ACCOUNT_ID}:inference-profile/us.anthropic.claude-*",
        "arn:aws:bedrock:*:{ACCOUNT_ID}:inference-profile/eu.anthropic.claude-*",
        "arn:aws:bedrock:*:{ACCOUNT_ID}:inference-profile/ap.anthropic.claude-*",
        "arn:aws:bedrock:*:{ACCOUNT_ID}:inference-profile/global.anthropic.claude-*"
      ]
    }
  ]
}
```

> **Bedrock cross-region 사유**: Claude 모델 가용성을 region 별로 보장하기 위해 inference profile 패턴 사용. ap-northeast-2 에서 us/eu inference profile 호출 정상 패턴.
>
> **AOSS resource scope**: `collection/*` wildcard 는 AOSS API 특성상 collection ID 를 미리 알 수 없음 — 단 region + account 로 narrow 됨.

### 3.3 `arkraft-agent-staging-role` (staging variant)

**Assume**: namespace `arkraft-staging-sandbox` 의 ServiceAccount `*`.

§3.2 와 동일한 정책에서 S3 bucket 만 staging:
- `arkraft-staging` (대신 `arkraft-production`)
- `ai-infra-argo-workflows-logs` 동일

### 3.4 `arkraft-agent-manager-role`

**현재 운영 Trust**: namespace `*` SA `*` (wildcard).
**B사 신청 권장 Trust**: 정확한 SA 명시.

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "{OIDC_PROVIDER_ARN}" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "{OIDC_ISSUER}:aud": "sts.amazonaws.com",
      "{OIDC_ISSUER}:sub": "system:serviceaccount:arkraft-sandbox:agent-manager"
    }
  }
}
```

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3PublicArtifactBucket",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::arkraft.quantit.ai",
        "arn:aws:s3:::arkraft.quantit.ai/*"
      ]
    }
  ]
}
```

### 3.5 `argo-workflows-role`

**Assume**: namespace `argo` SA `*`. Argo Workflows artifact storage.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::ai-infra-argo-workflows-logs",
        "arn:aws:s3:::ai-infra-argo-workflows-logs/*"
      ]
    }
  ]
}
```


### 3.6 `ebs-csi-driver-role` (K8s add-on)

**Assume**: namespace `kube-system` SA `ebs-csi-controller-sa`.

> **정책**: AWS Managed Policy `arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy` 사용 (custom JSON 작성 안 함).
>
> **사유**: AWS 공식 EKS add-on. narrow custom policy 사용 시 add-on 업그레이드와 충돌 위험. 권장 정책: managed policy 그대로 attach. 권한 내용 (요약): `ec2:CreateVolume`, `ec2:AttachVolume`, `ec2:DetachVolume`, `ec2:DeleteVolume`, `ec2:CreateSnapshot`, `ec2:DeleteSnapshot`, `ec2:DescribeVolumes`, `ec2:DescribeSnapshots`, `kms:CreateGrant` (encrypted EBS volume 사용 시).

### 3.7 `external-dns-role` (K8s add-on)

**Assume**: namespace `kube-system` SA `external-dns`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "route53:ChangeResourceRecordSets",
        "route53:ListResourceRecordSets"
      ],
      "Resource": [
        "arn:aws:route53:::hostedzone/{ZONE_ID_ARKRAFT_AI}",
        "arn:aws:route53:::hostedzone/{ZONE_ID_ARKRAFT_IO}",
        "arn:aws:route53:::hostedzone/{ZONE_ID_ARKRAFT_TRADE}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "route53:ListHostedZones",
        "route53:ListHostedZonesByName"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Resource: "\*" 사유 (Route53 List)**: List API 는 account-wide 만 — narrow 불가. ChangeResourceRecordSets 는 정확한 zone ARN 으로 narrow.

### 3.8 `aws-load-balancer-controller-role` (K8s add-on)

**Assume**: namespace `kube-system` SA `aws-load-balancer-controller`. ALB/NLB 동적 생성.

> **정책**: AWS 공식 권장 IAM Policy 사용 — `https://github.com/kubernetes-sigs/aws-load-balancer-controller/blob/main/docs/install/iam_policy.json`. AWS Managed Policy `AWSLoadBalancerControllerIAMPolicy` 사용 가능하지만 official 정책 JSON 이 더 정확함.
>
> **사유**: ALB Controller 는 ELBv2 (Create/Modify/Delete LoadBalancer/TargetGroup/Listener), EC2 (DescribeSecurityGroup/Subnet/VPC, CreateSecurityGroup, RevokeSecurityGroupIngress 등), ACM (DescribeCertificate, ListCertificates), Cognito (DescribeUserPoolClient — Cognito 인증 사용 시), WAF (AssociateWebACL — 필요 시), tag (Resource tagging) 권한 모두 필요. narrow 매우 제한적.
>
> **Custom narrow 옵션**: Controller 가 생성하는 ALB/NLB 에 `elbv2.k8s.aws/cluster=ai-infra-eks` 태그 강제 + condition `aws:ResourceTag/elbv2.k8s.aws/cluster: ai-infra-eks` 적용 시 일부 destructive action 만 narrow 가능. 보안팀 협의 권장.

### 3.9 Karpenter Controller (Pod Identity, **not** IRSA)

**Assume**: namespace `kube-system` SA `karpenter` via **EKS Pod Identity association** (Karpenter v21+ 권장 패턴 — IRSA 가 아님). `arn:aws:iam::aws:policy/AmazonEKSPodIdentityAssociation` 또는 EKS Pod Identity Agent.

> **Karpenter Module Source**: `terraform-aws-modules/eks/aws//modules/karpenter` v21+. 표준 정책을 자동 생성하며 Pod Identity 사용 (OIDC provider 불필요, AWS SDK 자동 인증).

#### 3.12a Karpenter Controller IAM Role (terraform-aws-modules 자동 생성)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowScopedEC2InstanceAccessActions",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:CreateFleet"
      ],
      "Resource": [
        "arn:aws:ec2:*::image/*",
        "arn:aws:ec2:*::snapshot/*",
        "arn:aws:ec2:*:*:security-group/*",
        "arn:aws:ec2:*:*:subnet/*"
      ]
    },
    {
      "Sid": "AllowScopedEC2LaunchTemplateAccessActions",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:CreateFleet"
      ],
      "Resource": "arn:aws:ec2:*:*:launch-template/*",
      "Condition": {
        "StringEquals": { "aws:ResourceTag/kubernetes.io/cluster/{CLUSTER_NAME}": "owned" },
        "StringLike":   { "aws:ResourceTag/karpenter.sh/nodepool": "*" }
      }
    },
    {
      "Sid": "AllowScopedEC2InstanceActionsWithTags",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:CreateFleet",
        "ec2:CreateLaunchTemplate"
      ],
      "Resource": [
        "arn:aws:ec2:*:*:fleet/*",
        "arn:aws:ec2:*:*:instance/*",
        "arn:aws:ec2:*:*:volume/*",
        "arn:aws:ec2:*:*:network-interface/*",
        "arn:aws:ec2:*:*:launch-template/*",
        "arn:aws:ec2:*:*:spot-instances-request/*"
      ],
      "Condition": {
        "StringEquals": { "aws:RequestTag/kubernetes.io/cluster/{CLUSTER_NAME}": "owned" },
        "StringLike":   { "aws:RequestTag/karpenter.sh/nodepool": "*" }
      }
    },
    {
      "Sid": "AllowScopedResourceCreationTagging",
      "Effect": "Allow",
      "Action": "ec2:CreateTags",
      "Resource": [
        "arn:aws:ec2:*:*:fleet/*",
        "arn:aws:ec2:*:*:instance/*",
        "arn:aws:ec2:*:*:volume/*",
        "arn:aws:ec2:*:*:network-interface/*",
        "arn:aws:ec2:*:*:launch-template/*",
        "arn:aws:ec2:*:*:spot-instances-request/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestTag/kubernetes.io/cluster/{CLUSTER_NAME}": "owned",
          "ec2:CreateAction": ["RunInstances", "CreateFleet", "CreateLaunchTemplate"]
        }
      }
    },
    {
      "Sid": "AllowMachineMigrationTagging",
      "Effect": "Allow",
      "Action": "ec2:CreateTags",
      "Resource": "arn:aws:ec2:*:*:instance/*",
      "Condition": {
        "StringEquals": { "aws:ResourceTag/kubernetes.io/cluster/{CLUSTER_NAME}": "owned" },
        "ForAllValues:StringEquals": { "aws:TagKeys": ["karpenter.sh/nodeclaim", "karpenter.sh/nodepool"] }
      }
    },
    {
      "Sid": "AllowScopedDeletion",
      "Effect": "Allow",
      "Action": ["ec2:TerminateInstances", "ec2:DeleteLaunchTemplate"],
      "Resource": ["arn:aws:ec2:*:*:instance/*", "arn:aws:ec2:*:*:launch-template/*"],
      "Condition": {
        "StringEquals": { "aws:ResourceTag/kubernetes.io/cluster/{CLUSTER_NAME}": "owned" },
        "StringLike":   { "aws:ResourceTag/karpenter.sh/nodepool": "*" }
      }
    },
    {
      "Sid": "AllowRegionalReadActions",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeImages",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypeOfferings",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeLaunchTemplates",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeSpotPriceHistory",
        "ec2:DescribeSubnets"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": "{REGION}" } }
    },
    {
      "Sid": "AllowSSMReadActions",
      "Effect": "Allow",
      "Action": "ssm:GetParameter",
      "Resource": "arn:aws:ssm:{REGION}::parameter/aws/service/*"
    },
    {
      "Sid": "AllowPricingReadActions",
      "Effect": "Allow",
      "Action": "pricing:GetProducts",
      "Resource": "*"
    },
    {
      "Sid": "AllowInterruptionQueueActions",
      "Effect": "Allow",
      "Action": ["sqs:DeleteMessage", "sqs:GetQueueUrl", "sqs:ReceiveMessage"],
      "Resource": "{KARPENTER_INTERRUPTION_QUEUE_ARN}"
    },
    {
      "Sid": "AllowPassingInstanceRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "{NODE_INSTANCE_ROLE_ARN}",
      "Condition": { "StringEquals": { "iam:PassedToService": "ec2.amazonaws.com" } }
    },
    {
      "Sid": "AllowScopedInstanceProfileCreationActions",
      "Effect": "Allow",
      "Action": "iam:CreateInstanceProfile",
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestTag/kubernetes.io/cluster/{CLUSTER_NAME}": "owned" }
      }
    },
    {
      "Sid": "AllowAPIServerEndpointDiscovery",
      "Effect": "Allow",
      "Action": "eks:DescribeCluster",
      "Resource": "arn:aws:eks:{REGION}:{ACCOUNT_ID}:cluster/{CLUSTER_NAME}"
    }
  ]
}
```

> **Resource: "\*" 사유 (Karpenter)**: EC2 Describe API + Pricing GetProducts + ssm GetParameter (AWS service parameter) 는 narrow 불가. 단 region condition 으로 narrow.

#### 3.12b Karpenter Node Instance Role (NodePool 이 launch 하는 EC2 가 가질 Role)

> **정책**: AWS Managed Policies 4종 attach
>
> - `arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy` — kubelet 인증
> - `arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy` — VPC CNI
> - `arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly` — ECR pull
> - `arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore` — SSM Session Manager (디버깅)
>
> **사유**: AWS 공식 EKS 노드 권장. Karpenter v21 module 자동 attach.

#### 3.12c Karpenter Spot Termination SQS Queue

Karpenter v21+ 는 spot interruption notice 처리용 SQS Queue + EventBridge Rules 를 자동 생성. Queue ARN 은 `{KARPENTER_INTERRUPTION_QUEUE_ARN}` 으로 §3.12a 의 SQS 권한에 사용. 별도 자원 신청은 SQS + EventBridge.

### 3.10 External-Secrets Operator IRSA (`{app}-external-secrets`)

**Assume**: namespace `external-secrets` SA `external-secrets`. **Trust subject narrow 됨** (`system:serviceaccount:external-secrets:external-secrets`).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerReadScoped",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:{ACCOUNT_ID}:secret:ai-infra/*"
    },
    {
      "Sid": "SecretsManagerListAccount",
      "Effect": "Allow",
      "Action": "secretsmanager:ListSecrets",
      "Resource": "*"
    },
    {
      "Sid": "KMSDecryptForCMKEncryptedSecrets",
      "Effect": "Allow",
      "Action": ["kms:Decrypt", "kms:DescribeKey"],
      "Resource": "*",
      "Condition": {
        "StringLike": { "kms:RequestAlias": "alias/arkraft/*" }
      }
    }
  ]
}
```

> **Resource: "\*" 사유 (Secrets Manager List)**: `ListSecrets` API 는 account-wide 만 — narrow 불가. `GetSecretValue` 와 `DescribeSecret` 는 prefix `ai-infra/*` 로 narrow (External-Secrets 가 sync 하는 secret 이 모두 이 prefix).
>
> **B사 적용 시**: prefix `ai-infra` 를 B사가 정의한 prefix 로 변경 (예: `arkraft-byoc/*`).

### 3.11 `arkraft-web-server-role` (B사 신청 권장 — 신설)

> ⚠️ **현재 운영 (위험)**: web Pod 은 IRSA 미사용. `arkraft-deploy/web/values/production/values.yaml` 에 IAM User long-lived access key (`AKIA*REDACTED*XZG`) + secret key plaintext 노출. 이 IAM User 는 ai-infra Terraform 으로 관리되지 않는 수동 자원. 정책 추적 불가.
>
> ⭐ **B사 PoC 권장 (이 섹션)**: web Pod 에 IRSA Role 부여 + Long-lived access key 폐기.

**Assume**: namespace `arkraft` SA `arkraft-web` (신설 — 현재 helm chart 에 미존재).

**Trust Policy**:

```json
{
  "Effect": "Allow",
  "Principal": { "Federated": "{OIDC_PROVIDER_ARN}" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "{OIDC_ISSUER}:aud": "sts.amazonaws.com",
      "{OIDC_ISSUER}:sub": "system:serviceaccount:arkraft:arkraft-web"
    }
  }
}
```

**Permission Policy** (web BFF 가 사용하는 최소 권한 — `@aws-sdk/client-s3` 의 GetObject 만 추정):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3ReadOnlyForBFFAssetServing",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::arkraft-production",
        "arn:aws:s3:::arkraft-production/*"
      ]
    }
  ]
}
```

> **B사 PoC 적용 절차**:
> 1. ai-infra 에 `arkraft_web_server_irsa` module 추가 (현재 미존재)
> 2. `arkraft-deploy/web/templates/serviceaccount.yaml` 에 `arkraft-web` SA + `eks.amazonaws.com/role-arn` annotation 추가
> 3. values.yaml 에서 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env var 제거
> 4. 기존 IAM User `AKIA*REDACTED*XZG` 폐기 (key rotation → access key 삭제 → IAM User 자체 삭제)
> 5. Pod 재시작으로 IRSA 자격증명 자동 적용 확인
>
> **Web BFF 의 실제 S3 호출 패턴 재확인 필요** (iter 6): `arkraft-web/src/infra/clients/s3/client.ts` 에서 어떤 메서드 (Get/Put/Delete?) 와 어떤 bucket 사용. 위 정책은 현재 추정 — 실제 호출에 따라 narrow.

### 3.12 AmazonMQ (RabbitMQ) — Pod 측 IAM 권한 불필요

> **AmazonMQ 자체 IAM 권한**: 보통 불필요. RabbitMQ 는 AMQP protocol 직접 (TLS) 로 인증하며, Pod 은 Secrets Manager 에서 admin/user credentials 를 받음 (External-Secrets 가 sync). 즉 Pod 에 추가 IAM 정책 불필요 — `arkraft-api-server-role` 의 KMS Decrypt 권한 (External-Secrets 가 sync 한 K8s Secret 사용 시) 또는 직접 Secrets Manager 호출 권한이 있으면 됨.
>
> **Terraform 자체**: AmazonMQ broker 생성/관리 권한은 Atlantis IAM Role (별도) — Pod 에 부여 불필요.

---

## 4. AWS Managed Policy 매핑 (참조용)

> ⚠️ **이 섹션은 "참조 / 빠른 fallback" 용. 추천 아님**. 가능하면 §3 의 custom policy 를 권장.

| Service | Custom Policy (권장 — §3) | AWS Managed Policy (참조) | 사용 비추 사유 |
|---------|---------------------------|---------------------------|-----------------|
| S3 | §3.1, §3.2 | `AmazonS3FullAccess` | 모든 bucket 모든 action — 우리 bucket 4-8개에만 scope down 가능 |
| EKS | (control plane Terraform 자동) | `AmazonEKSClusterPolicy` | EKS control plane 정책상 필요 — narrow 어려움 (사용 권장) |
| EKS Worker | (Karpenter 가 관리) | `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly` | Karpenter 사용 시 NodeInstanceRole 에 attach (사용 권장) |
| EBS CSI | §3.9 (managed) | `AmazonEBSCSIDriverPolicy` | EKS add-on, narrow 시 충돌 위험 (사용 권장) |
| ALB Controller | §3.11 (managed) | `AWSLoadBalancerControllerIAMPolicy` | 광범위하지만 narrow 제한적 (사용 권장 + tag-based condition 추가) |
| Bedrock | §3.2 | `AmazonBedrockFullAccess` | 모든 모델 invoke — 우리는 Claude Opus/Sonnet/Haiku 만 |
| RDS | (Pod 직접 RDS API 호출 없음) | `AmazonRDSFullAccess`, `AmazonRDSReadOnlyAccess` | Pod 은 PostgreSQL protocol 직접 — IAM 불필요 |
| Secrets Manager | (External-Secrets 만 read) | `SecretsManagerReadWrite` | Read 만 필요 → custom: `secretsmanager:GetSecretValue` 만 |
| KMS | §3.1 | `AWSKeyManagementServicePowerUser` | 광범위 — `kms:RequestAlias` condition 으로 narrow 가능 |
| Route53 | §3.10 | `AmazonRoute53FullAccess` | external-dns 만 사용, ChangeRecord 만 narrow |
| ECR | (CI 만 push, Pod 만 pull) | `AmazonEC2ContainerRegistryFullAccess`, `AmazonEC2ContainerRegistryReadOnly` | EKS 노드 ReadOnly + CI 별도 push role |

---

## 5. IRSA Role 매트릭스

> 11개 IRSA Role 전수 (8개 application + 3개 K8s add-on)

| # | IRSA Module | Pod / ServiceAccount | IAM Role 이름 | 핵심 IAM Action | Resource ARN 패턴 | Trust Policy condition |
|---|------------------------|------------------|---------------|-------------|-------------------|-----------------|
| 1 | `arkraft_api_server_irsa` | `arkraft:arkraft-api` (narrow 권장) | `arkraft-api-server-role` | s3:* 4 buckets, kms:GenerateDataKey | `arkraft-{prod,staging}, arkraft.quantit.ai, c2-performance-data-production` + KMS alias `alias/arkraft/*` | OIDC StringLike |
| 2 | `arkraft_agent_irsa` | `arkraft-sandbox:*` | `arkraft-agent-role` | s3:* 2 buckets, aoss:APIAccessAll, bedrock:InvokeModel* | argo-logs, arkraft-production + AOSS collection/* + Bedrock anthropic.* + inference-profile us/eu/ap/global | OIDC StringLike |
| 3 | `arkraft_agent_staging_irsa` | `arkraft-staging-sandbox:*` | `arkraft-agent-staging-role` | (§2와 동일 — bucket 만 staging) | argo-logs, arkraft-staging + AOSS + Bedrock | OIDC StringLike |
| 4 | `arkraft_agent_manager_irsa` | `arkraft-sandbox:agent-manager` (narrow 권장) | `arkraft-agent-manager-role` | s3:* (1 bucket) | arkraft.quantit.ai* | OIDC StringLike |
| 5 | `argo_workflows_irsa` | `argo:*` | `argo-workflows-role` | s3:Put/Get/ListObject | ai-infra-argo-workflows-logs/* | OIDC StringLike |
| 6 | `ebs_csi_irsa` | `kube-system:ebs-csi-controller-sa` | `ai-infra-eks-ebs-csi-driver` | (managed) AmazonEBSCSIDriverPolicy | EBS volumes | OIDC StringLike |
| 7 | `external_dns_irsa` | `kube-system:external-dns` | `ai-infra-eks-external-dns` | route53:ChangeResourceRecordSets | hosted zone ARN | OIDC StringLike |
| 8 | `aws_load_balancer_controller_irsa` | `kube-system:aws-load-balancer-controller` | `ai-infra-eks-aws-load-balancer-controller` | (managed) AWSLoadBalancerControllerIAMPolicy | EC2/ELBv2 | OIDC StringLike |
| 9 | `external_secrets` (Operator) | `external-secrets:external-secrets` | `{app}-external-secrets` | secretsmanager:GetSecretValue/DescribeSecret/ListSecrets + kms:Decrypt | `secret:ai-infra/*` + KMS alias condition | OIDC StringEquals (narrow) |
| 10 | `karpenter` (Pod Identity, **not** IRSA) | `kube-system:karpenter` | `{app}-karpenter` Controller Role + `{app}-karpenter-node` Node Instance Role | EC2 RunInstances/CreateFleet/Tag, iam:PassRole, sqs:Receive (spot termination) | tag-based scope (`kubernetes.io/cluster/{CLUSTER}: owned` + `karpenter.sh/nodepool: *`) | EKS Pod Identity Association |
| 11 | `arkraft_web_server_irsa` (B사 신청 권장 신설) | `arkraft:arkraft-web` | `arkraft-web-server-role` | s3:GetObject/ListBucket | `arkraft-production` 만 | OIDC StringEquals |

> **모든 Trust Policy 패턴 동일**: `sts:AssumeRoleWithWebIdentity` + OIDC provider `module.aws.eks_oidc_provider_arn` + `StringLike` condition (token audience + subject match).

---

## 6. K8s ServiceAccount 매핑

| # | Chart | Namespace | ServiceAccount | IRSA Role ARN annotation | Pod 환경변수 (AWS 자원) |
|---|-------|-----------|----------------|--------------------------|------------------------|
| 1 | api (prod) | `arkraft` | `arkraft-api` | `arn:aws:iam::{ACCOUNT}:role/arkraft-api-server-role` | S3=`arkraft-production`, REDIS=`arkraft-redis...apn2.cache.amazonaws.com:6379/0`, RDS=`arkraft-postgres...ap-northeast-2.rds.amazonaws.com:5432`, MQ=`b-{id}.mq.ap-northeast-2.on.aws` |
| 2 | api (staging) | `arkraft` | `arkraft-api` | (동일 role) | S3=`arkraft-staging`, REDIS=`/2`, DATA_QUERY_REDIS=`/3` |
| 3 | web | `arkraft` | (default SA — IRSA 미설정) | **❌ IRSA 미사용 — 대신 IAM User long-lived access key (`AKIA...`) 가 `arkraft-deploy/web/values/production/values.yaml` 에 plaintext** | S3 호출 (`@aws-sdk/client-s3` BFF, `src/infra/clients/s3/client.ts`) |
| 4 | agent-alpha | `arkraft-sandbox` | `alpha-argo-wf-sa` | `arn:aws:iam::{ACCOUNT}:role/arkraft-agent-role` (prod) / `arkraft-agent-staging-role` (staging) | S3, REDIS, BEDROCK_REGION=`ap-northeast-2`, LLM_BACKEND=`bedrock` |
| 5 | agent-insight | `arkraft-sandbox` | `insight-argo-wf-sa` | (동일 패턴) | (동일 패턴) |
| 6 | agent-portfolio | `arkraft-sandbox` | `portfolio-argo-wf-sa` | (동일 패턴) | (동일 패턴) |
| 7 | agent-report | `arkraft-sandbox` | `report-argo-wf-sa` | (동일 패턴) | (동일 패턴) |
| 8 | agent-extract | `arkraft-sandbox` | `extract-argo-wf-sa` | (동일 패턴) | (동일 패턴) |
| 9 | agent-data | `arkraft-sandbox` | `data-argo-wf-sa` | (동일 패턴) | (동일 패턴) |
| 10 | **agent-manager** | `arkraft-sandbox` | (helm chart 미존재 — `tmp/manifests-agents.yaml` 에 정의) | `arn:aws:iam::{ACCOUNT}:role/arkraft-agent-manager-role` | Pod 가 다른 Pod orchestrate 시 사용 (관리 도메인) |

> **Argo WorkflowTemplate 패턴**: 6 agent 가 각자 WorkflowTemplate 보유. Pod 리소스 4 CPU / 24Gi (alpha 기준), Karpenter on-demand NodePool 에 schedule. ConfigMap (`{agent}-argo-wf-config`) + Secret (`{agent}-argo-wf-secret`) 으로 env 자동 주입.
>
> ⚠️ **CRITICAL — web 의 IAM User access key 보안 리스크 (§6 #3 행)**:
> - 현재 운영: `arkraft-deploy/web/values/production/values.yaml` 에 IAM User access key (`AKIA*REDACTED*XZG`) + secret key 가 plaintext 로 박혀 있음.
> - 이 IAM User 는 ai-infra Terraform 으로 관리되지 **않음** — 수동 생성. 정책 추적 불가.
> - **B사 PoC 신청 권장**: web Pod 에 IRSA Role (`arkraft-web-server-role`) 부여 + S3 GetObject 권한 narrow. Long-lived access key 폐기. §3 에 §3.16 으로 추가 정책 권장 (iter 4 보강 예정).
> - **B사 신청 시 빠지면 안 되는 항목**: 만약 B사가 IRSA 패턴으로 통일하려면 web 에 별도 SA + IRSA + IAM Role 필요.

---

## 7. 인프라 자원 인벤토리

### 7.1 Compute

| 자원 | 식별자 | 사양 | Region | 암호화 | 접근 제어 | 출처 |
|------|--------|------|--------|--------|-----------|------|
| EKS Cluster | `ai-infra-eks` | v1.34, public endpoint | ap-northeast-2 | EKS-managed (KMS envelope optional) | aws-auth + RBAC | `ai-infra/aws/eks/` |
| EC2 (Karpenter) | NodePool (on-demand + spot) | t/m/c/r 시리즈 mix, gp3 EBS, AL2023 표준 AMI 권장 | ap-northeast-2 | EBS encrypt | Karpenter Pod Identity (IRSA 가 아님) + Node Instance Role | `ai-infra/karpenter/` |

### 7.2 Storage (S3)

| Bucket 이름 | 용도 | Region | 암호화 | 접근 제어 (bucket policy + Public Access Block) | versioning | lifecycle |
|-------------|------|--------|--------|-------------------------------------|------------|-----------|
| `arkraft-production` | arkraft 운영 데이터 (api / 6 agents 의 결과물 저장) | ap-northeast-2 | SSE-S3 (default) | private + IAM only (`arkraft-api-server-role`, `arkraft-agent-role`). CORS: B사 도메인 | enabled 권장 | TTL 권장 |
| `arkraft-staging` | staging 데이터 (선택 — 동일 패턴) | ap-northeast-2 | SSE-S3 | private + IAM only | — | — |
| `ai-infra-argo-workflows-logs` | Argo Workflow artifact (agent run 결과) | ap-northeast-2 | SSE-S3 | private + IAM only (`argo-workflows-role`, `arkraft-agent-role`) | — | TTL 권장 |
| Terraform state (B사 GitOps 사용 시) | B사 측 backend bucket (B사 자체 정의) | ap-northeast-2 | SSE-KMS | private + B사 deploy IAM Role only. DynamoDB lock table 동반 | enabled | — |

> **B사 신청 시**: 위 이름 그대로 만들거나 prefix 변경. IAM Resource ARN 도 같이 바꿔야 함.

### 7.3 Database

| 자원 | 식별자 | Engine / 사양 | Multi-AZ | Backup | 암호화 | Region | 접근 제어 |
|------|--------|--------------|----------|--------|--------|--------|-----------|
| RDS | `arkraft-postgres` | PostgreSQL 17.2, db.t4g.medium, 20GB → 100GB max | false (PoC 권장 true) | 2d retention, deletion_protection=true | KMS | ap-northeast-2 | private subnet + SG (VPC CIDR 5432) |
| ElastiCache | `arkraft-redis` | Redis 7.1, cache.t4g.micro, single node, maxmemory=noeviction | false | 1d snapshot | TLS+KMS | ap-northeast-2 | private subnet + SG (VPC CIDR 6379) |

> **alpha-pool 내재화 (ARK-1518)**: 외부 데이터 파이프라인 (Finter → Lambda alpha-migrator → DynamoDB → AOSS VECTORSEARCH) 이 모두 제거됨. agent (alpha) 가 직접 데이터를 in-house 처리하는 메커니즘으로 전환. arkraft 데이터 영속성은 RDS PostgreSQL + ElastiCache Redis + S3 (`arkraft-production`) 만 사용.

### 7.4 Messaging / Eventing

| 자원 | 이름 | Region | 암호화 | 접근 제어 | 용도 |
|------|------|--------|--------|-----------|------|
| AmazonMQ (RabbitMQ) | `ai-infra-rabbitmq` | ap-northeast-2 | TLS in-transit + KMS | VPC private subnet only + Secrets Manager admin credential (External-Secrets 가 K8s Secret 으로 sync) | api/agent worker queue. mq.m7g.large (Graviton), 3.13, multi-AZ |
| EventBridge Rule | Karpenter spot interruption rules (자동 생성) | ap-northeast-2 | (managed) | Karpenter target | Karpenter 노드 spot 회수 알림 |
| **SQS** | `{app}-karpenter` (Karpenter spot interruption queue, terraform-aws-modules/eks 자동 생성) | ap-northeast-2 | KMS optional | Karpenter Pod Identity 만 receive | Spot 인스턴스 회수 통보 처리 |

### 7.5 AI/ML — Bedrock

| 모델 ID | 호출 컴포넌트 | Region (호출) | 암호화 | 접근 제어 | inference profile |
|---------|--------------|---------------|--------|-----------|-------------------|
| `anthropic.claude-opus-4-7*` | agent-* | ap-northeast-2 (default region) + cross-region inference profile (`us.`, `eu.`, `ap.`, `global.`) | (managed by Bedrock — TLS) | IAM Action `bedrock:InvokeModel*` resource 패턴 narrow + AWS Org Bedrock model-access 활성화 필요 | foundation + inference profile (cross-region routing) |
| `anthropic.claude-sonnet-4-6*` | agent-* + (api 추정) | (동일) | (동일) | (동일) | (동일) |
| `anthropic.claude-haiku-4-5*` | agent-* (light) | (동일) | (동일) | (동일) | (동일) |
| `global.anthropic.claude-sonnet-4-6` | arkraft-agent-extract (BedrockConverseModel via pydantic-ai) | global inference profile | (managed) | IAM Action narrow | global inference profile |

> **Bedrock Model Access 활성화 (B사 별도 작업)**: Bedrock Console → Model Access → "Anthropic Claude" 패밀리 활성화 요청 (B사 root account 또는 organization admin). IAM 권한과 별개의 sign-up 절차.

### 7.6 Network

| 자원 | 식별자 | Region | 암호화 | 접근 제어 | 사유 |
|------|--------|--------|--------|-----------|------|
| VPC | (Terraform module aws.vpc) | ap-northeast-2 | (N/A) | Security Group 다수 | 전체 클러스터 |
| Public Subnet × 3 | per AZ | ap-northeast-2 | — | Public IP enabled | NAT/ALB ingress 용 |
| Private Subnet (services /24) × 3 | per AZ | ap-northeast-2 | — | private (NAT egress only) | 일반 워크로드 |
| Private Subnet (workload /20) × 3 | per AZ | ap-northeast-2 | — | private (NAT egress only) | Karpenter (Prefix Delegation 위해 /20 이상 필수) |
| NAT Gateway | (×3 또는 single) | ap-northeast-2 | — | EIP attach | private subnet egress |
| EIP | (NAT용) | ap-northeast-2 | — | NAT 전용 | — |
| ALB/NLB | external-gateway (NLB public), internal-gateway (NLB private) | ap-northeast-2 | TLS (ACM) | SG | Istio 인그레스 (arkraft api/web) |
| Route53 zone | B사 도메인 (예: `arkraft.b사.com`) | global | — | account-bound | 도메인 + ALB DNS record (External-DNS 자동 생성) |
| ACM cert | wildcard `*.{B사 도메인}` + bare | ap-northeast-2 (ALB region 동일) | (managed) | DNS validation | ALB TLS |
| **VPC Endpoint (Gateway)** | S3 + DynamoDB | ap-northeast-2 | — | route table 연결 | 비용 무료 (gateway type) — private subnet 에서 S3 비용 절감 |
| **VPC Endpoint (Interface)** — 권장 신규 추가 | ECR (api+dkr), Secrets Manager, KMS, STS, CloudWatch Logs | ap-northeast-2 | TLS | VPC SG narrow | NAT egress 비용 절감 + 보안 강화 |

### 7.7 Security

| 자원 | 식별자 | Region | 암호화 | 접근 제어 | 사유 |
|------|--------|--------|--------|-----------|------|
| KMS Key | `alias/arkraft/data-source-credentials` | ap-northeast-2 | (CMK 자체) | key policy + alias condition | arkraft api 가 외부 DB credentials 암호화 시 사용 |
| KMS Key (default AWS managed) | `alias/aws/{rds,s3,ebs,secretsmanager}` | ap-northeast-2 | (CMK 자체) | account-bound default | 별도 CMK 미사용 자원 |
| Secrets Manager | `ai-infra/rds/arkraft-postgres` (또는 B사 prefix) | ap-northeast-2 | KMS default | IAM only (External-Secrets sync) | RDS credentials |
| Secrets Manager | `ai-infra/rabbitmq/{user}` (또는 B사 prefix) | ap-northeast-2 | KMS default | IAM only | RabbitMQ broker user credentials (per-service) |
| **Cognito** | **미사용 확정** (ai-infra Terraform 0건 + app code grep 0건) | — | — | — | Arkraft 인증은 다른 메커니즘 (JWT 자체 발급) |
| IAM OIDC Provider (EKS) | EKS cluster OIDC | global | — | thumbprint pinned | IRSA Trust |
| **EKS Pod Identity Agent add-on** | `aws_eks_addon` type `eks-pod-identity-agent` | ap-northeast-2 | — | EKS managed | Karpenter Pod Identity Association 동작에 필요 (v21+) |
| **EKS Access Entries / Roles** | `aws_eks_access_entry` + `aws_eks_access_policy_association` | ap-northeast-2 | — | account IAM Role/User → EKS RBAC | kubectl / Console 접근 (Role-based 권장) |

### 7.8 Container Registry (ECR)

| Repository | Region | 암호화 | 접근 제어 (push / pull) | 사용 |
|-----------|--------|--------|--------------------------|------|
| `ark/arkraft-api` | ap-northeast-2 | AES256 (default) | push: B사 CI / pull: EKS NodeInstanceRole | api server |
| `ark/arkraft-web` | ap-northeast-2 | AES256 | (동일) | web frontend |
| `ark/arkraft-agent-alpha` | ap-northeast-2 | AES256 | (동일) | alpha agent |
| `ark/arkraft-agent-insight` | ap-northeast-2 | AES256 | (동일) | insight agent |
| `ark/arkraft-agent-portfolio` | ap-northeast-2 | AES256 | (동일) | portfolio agent |
| `ark/arkraft-agent-report` | ap-northeast-2 | AES256 | (동일) | report agent |
| `ark/arkraft-agent-extract` | ap-northeast-2 | AES256 | (동일) | extract agent |
| `ark/arkraft-agent-data` | ap-northeast-2 | AES256 | (동일) | data agent |
| `ark/arkraft-agent-manager` | ap-northeast-2 | AES256 | (동일) | agent manager |

> 모든 repo: `image_scanning_configuration.scan_on_push=true`, `lifecycle_policy.max_image_count=30`. Repository Policy 는 default (private + 동일 account IAM only). Push side IAM Role 은 B사 자체 CI 시스템 (GitHub Actions / GitLab CI / Jenkins 등) 에서 별도 정의.

### 7.9 Observability

| 자원 | 이름 | 사유 |
|------|------|------|
| CloudWatch Log Group | `/aws/eks/{cluster}/cluster` | EKS control plane log |
| CloudWatch Log Group | Karpenter / Argo Workflows / External-DNS / ALB Controller (in-cluster Helm chart 가 기본 stdout 로 출력 — CloudWatch agent 활성화 시 별도 group) | 인프라 컴포넌트 log |

> **Loki / Grafana / Prometheus**: B사 자체 observability 솔루션 사용 권장. arkraft 자체에는 self-hosted 없음 (B사 PoC 신청 불필요).

### 7.10 GitOps / Workflow

| 자원 | 이름 | 호스팅 | 사유 |
|------|------|--------|------|
| Argo Workflows | (in-cluster) + S3 artifact bucket `ai-infra-argo-workflows-logs` | EKS pod | arkraft agent run 의 artifact 저장. arkraft agent 6종 (alpha/insight/portfolio/report/extract/data) 가 WorkflowTemplate 으로 동작. |
| ArgoCD (선택) | (in-cluster) | EKS pod | B사가 GitOps 에 ArgoCD 사용 시. 또는 다른 GitOps 솔루션 사용 가능. AWS 권한 별도 필요 X (EKS 내부 동작) |

---

## 8. Region 변경 시 영향

> B사가 us-east-1 또는 us-east-2 (NYC 가까움) 에 deploy 하는 시나리오.

| 자원 | ap-northeast-2 → us-east-1 변경 시 영향 |
|------|-----------------------------------------|
| **Bedrock 모델** | Claude Opus/Sonnet/Haiku us-east-1 가용 — 검증 필요. **inference profile 패턴은 그대로 통과** (`us.anthropic.*`, `eu.anthropic.*`, `ap.anthropic.*`, `global.anthropic.*`). 단 prod 에선 ap-northeast-2 → ap.anthropic.* 호출이 자연스러움; us-east-1 에선 us.anthropic.* 가 자연스러움. |
| **KMS Key** | region-bound. Multi-region key 옵션 고려 (cross-region 데이터 접근 필요 시). |
| **S3 Bucket** | region-bound. cross-region replication 시 양쪽 IAM Action 필요. bucket 이름은 global namespace 라 충돌 주의. |
| **ACM Certificate** | region-bound. ALB region 과 동일해야 함. CloudFront 사용 시 us-east-1 강제. |
| **Route53** | global service — 영향 없음 (zone 위치 무관). |
| **Secrets Manager** | region-bound. cross-region secret replication 옵션. |
| **RDS PostgreSQL** | region-bound. Multi-AZ within region OK. cross-region read replica 별도. |
| **ElastiCache Redis** | region-bound. Global Datastore 옵션 (cross-region replication). |
| **OpenSearch Serverless** | region-bound. cross-region 미지원. |
| **DynamoDB** | region-bound. Global Tables 옵션 (multi-region). |
| **ECR** | region-bound. cross-region pull 가능하지만 비용+latency. ECR replication 옵션. |
| **Lambda** | region-bound. function 코드 + IAM role 모두 재생성. |
| **EventBridge** | region-bound. rule + target 재생성. |
| **CloudWatch Logs** | region-bound. log group 재생성. |
| **AmazonMQ (RabbitMQ)** | region-bound. broker URL 변경. |
| **Karpenter** | region-bound. instance type 가용성 region 별 차이 가능 (Graviton instance 등). |
| **VPC + NAT + EIP** | region-bound. 새 VPC + NAT + EIP. |
| **ALB/NLB** | region-bound. ACM cert 도 같은 region 이어야 함. |

> **B사 deploy 시 결정 사항**: 단일 region (us-east-1) 단순 vs. multi-region (ap-northeast-2 + us-east-1 with replication) 비용 vs. latency. PoC 단계에선 **단일 region 권장**.

---

## 9. B사 신청 체크리스트

> 보안팀이 항목별 ack 체크 가능한 markdown checkbox 형태.

### 9.1 Tier-1 (arkraft 가동에 필수)

#### 컴퓨트
- [ ] EKS Cluster 생성 권한 + control plane IAM Role
- [ ] Karpenter NodePool (EC2 RunInstances 등 — Pod Identity 패턴, terraform-aws-modules/eks v21 표준)

#### 네트워크
- [ ] VPC + 6 Subnet (public×3 / private×3 — workload `/20`+ for Karpenter Prefix Delegation)
- [ ] Internet Gateway + NAT Gateway × 1-3 + EIP × 1-3
- [ ] Security Group (ALB, EKS pod, RDS, Redis, RabbitMQ)
- [ ] Route53 Hosted Zone (B사 도메인)
- [ ] ACM Certificate (wildcard, ALB region 동일)
- [ ] ALB/NLB × 2 (external-gateway public, internal-gateway private — Istio 인그레스)

#### 데이터
- [ ] S3 Bucket × 2-3: `arkraft-production` (필수), `arkraft-staging` (선택), `ai-infra-argo-workflows-logs` (Argo agent run artifact)
- [ ] RDS PostgreSQL 17.x (db.t4g.medium 권장) — Multi-AZ for prod
- [ ] ElastiCache Redis 7.x (cache.t4g.micro 또는 .medium)

#### AI/ML
- [ ] Bedrock Model Access — `anthropic.claude-opus-4-7`, `anthropic.claude-sonnet-4-6`, `anthropic.claude-haiku-4-5` (foundation + inference profile)

#### 컨테이너
- [ ] ECR Repository × 9: `ark/arkraft-api`, `ark/arkraft-web`, `ark/arkraft-agent-{alpha,insight,portfolio,report,extract,data}`, `ark/arkraft-agent-manager` — image scan + lifecycle 권장

#### 보안
- [ ] KMS Key × 1+ (alias `alias/{prefix}/data-source-credentials` + 자동 RDS/S3/EBS default 사용)
- [ ] Secrets Manager × 2+ (RDS credentials, RabbitMQ credentials per-service)

#### 메시징
- [ ] AmazonMQ (RabbitMQ) — `mq.m7g.large` Graviton, 3.13, multi-AZ

### 9.2 Tier-2 (운영, K8s add-on)

- [ ] EBS CSI driver IRSA + IAM Role (`AmazonEBSCSIDriverPolicy`)
- [ ] AWS Load Balancer Controller IRSA + IAM Role (AWS 공식 정책 또는 tag-based narrow)
- [ ] External-DNS IRSA + IAM Role (Route53 ChangeResourceRecordSets, zone ARN narrow)
- [ ] **Karpenter Pod Identity** (terraform-aws-modules/eks v21 표준 정책) + Node Instance Role (`{app}-karpenter-node`: AmazonEKSWorkerNodePolicy + EKS_CNI_Policy + ECR ReadOnly + SSM ManagedInstanceCore)
- [ ] **EKS Pod Identity Agent add-on** (`aws_eks_addon` type `eks-pod-identity-agent`) — Karpenter 동작 필수
- [ ] **Karpenter Spot Interruption SQS Queue + EventBridge Rules** — terraform-aws-modules/eks 자동 생성
- [ ] External-Secrets Operator IRSA + IAM Role (Secrets Manager GetSecretValue + DescribeSecret + ListSecrets, KMS Decrypt narrow `alias/arkraft/*`)
- [ ] Argo Workflows controller IRSA + IAM Role (S3 artifact bucket)
- [ ] **arkraft-web-server-role IRSA (§3.11 신설 권장)** — web Pod 의 IAM User access key 폐기 + IRSA 전환 (보안 강화)
- [ ] CloudWatch Logs (EKS control plane 자동 + agent run log)
- [ ] **VPC Endpoints (Interface)** — ECR API/DKR + Secrets Manager + KMS + STS + CloudWatch Logs (NAT egress 비용 절감 + 보안 강화). 현재는 S3 + DynamoDB Gateway 만 정의됨.
- [ ] **EKS Access Entries / Access Roles** — `aws_eks_access_entry` + `aws_eks_access_policy_association` Role-based EKS access (kubectl/Console)

### 9.3 Region 별 추가 신청 (us-east-1 deploy 시)

- [ ] Bedrock 모델 us-east-1 가용성 재확인 — Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 모두 활성화
- [ ] inference profile 패턴 `us.anthropic.*`, `global.anthropic.*` 호출 권한
- [ ] KMS multi-region key 또는 us-east-1 별도 key
- [ ] ACM certificate us-east-1 발급

### 9.4 IAM Trust Policy narrow 요청

> ⚠️ **현재 ai-infra 의 일부 IRSA Trust Policy 가 namespace/SA wildcard `*:*` 사용**. B사 보안팀 신청 시 narrow 권장:

- [ ] `arkraft-api-server-role` Trust → `system:serviceaccount:arkraft:arkraft-api`
- [ ] `arkraft-agent-manager-role` Trust → `system:serviceaccount:arkraft-sandbox:agent-manager`
- [ ] `arkraft-agent-role` Trust → `system:serviceaccount:arkraft-sandbox:*` (namespace 까진 narrow)
- [ ] `arkraft-agent-staging-role` Trust → `system:serviceaccount:arkraft-staging-sandbox:*`

---

## 10. 출처/근거

> 각 항목이 어느 Terraform 모듈 / Helm 차트 / 앱 코드에서 도출됐는지 추적. 감사 가능성 보장.

### 10.1 Terraform 출처

| # | 항목 | 파일 |
|---|------|------|
| 1 | EKS Cluster | `ai-infra/aws/eks*.tf` |
| 2 | Karpenter | `ai-infra/karpenter/` (Helm chart values) |
| 3 | EBS CSI IRSA | `ai-infra/aws/eks-ebs-csi*.tf` (module) |
| 4 | RDS PostgreSQL | `ai-infra/aws/rds.tf` |
| 5 | ElastiCache Redis | `ai-infra/aws/elasticache.tf` |
| 6 | S3 buckets | `ai-infra/aws/s3*.tf`, `ai-infra/argo-workflows/`, `ai-infra/monitoring/loki/` |
| 7 | ECR | `ai-infra/aws/ecr.tf` |
| 8 | KMS | `ai-infra/aws/kms.tf` |
| 9 | Secrets Manager | `ai-infra/aws/secretsmanager.tf` |
| 10 | Route53 zones | `ai-infra/aws/route53.tf` |
| 11 | ACM | `ai-infra/aws/acm.tf` |
| 12 | ALB/NLB | `ai-infra/istio/`, `ai-infra/atlantis/` |
| 13 | VPC + NAT | `ai-infra/aws/vpc.tf` |
| 14 | OpenSearch Serverless | `ai-infra/aws/opensearch*.tf` |
| 15 | DynamoDB | `ai-infra/aws/dynamodb*.tf` |
| 16 | AmazonMQ | `ai-infra/aws/rabbitmq.tf` |
| 17 | Lambda alpha-migrator | `ai-infra/lambda/` |
| 18 | EventBridge | `ai-infra/lambda/eventbridge.tf` |
| 19 | CloudWatch Log Groups | `ai-infra/aws/cloudwatch*.tf` (예상 — Terraform 명시 또는 K8s 자동 생성) |
| 20 | IAM IRSA modules (11개) | `ai-infra/aws/iam-*.tf` (각 IRSA module) |
| 21 | OIDC Provider | `ai-infra/aws/eks*.tf` (cluster identity output) |

### 10.2 Helm chart 출처

| # | 항목 | 파일 |
|---|------|------|
| 22 | api ServiceAccount + IRSA annotation | `arkraft-deploy/api/templates/serviceaccount.yaml`, `values.yaml` |
| 23 | api 환경변수 (S3, RDS, Redis, MQ) | `arkraft-deploy/api/values.yaml`, `templates/configmap.yaml` |
| 24 | agent-* ServiceAccount + Argo WorkflowTemplate | `arkraft-deploy/agents/{alpha,insight,portfolio,report,extract,data}/values.yaml` |
| 25 | agent-* Argo WorkflowTemplate | `arkraft-deploy/agents/*/templates/workflowtemplate.yaml` |

### 10.3 앱 코드 출처 (재검증 후 정정)

> ⚠️ **iter 3 정정**: Completeness reviewer 의 직접 grep 결과 일부 호출이 첫 iter 에서 잘못 보고됨. 정확한 결과로 갱신.

| # | 레포 | 직접 grep 결과 | AWS Service | IAM Action 추정 |
|---|------|---------------|-------------|-----------------|
| 26 | arkraft-api/src | **boto3 직접 호출 0건** (확인됨) | — | §3.1 의 GlueDataCatalogReadOnly 는 **사용되지 않을 가능성** — 정확한 호출 위치 재확인 필요 (iter 4) |
| 27 | arkraft-web | `@aws-sdk/client-s3` (`src/infra/clients/s3/client.ts:3` server-only) — **BFF 가 IAM User access key 로 직접 S3 호출** | S3 | GetObject (실제 grep 으로 호출 메서드 확인 필요) |
| 28 | arkraft-agent-alpha | boto3.client('s3') 호출 위치 있음 | S3 | PutObject (run artifact 저장) |
| 29 | arkraft-agent-data | boto3.client('s3') | S3 | read/write |
| 30 | arkraft-agent-extract | (boto3 직접 0건, pydantic-ai BedrockConverseModel 경유로 추정) | S3, Bedrock | global.anthropic.claude-sonnet-4-6 |
| 31 | arkraft-agent-insight | boto3.client('s3') | S3 | (Bedrock 은 wrapper SDK 추정) |
| 32 | arkraft-agent-portfolio | boto3.client('s3') 3곳 | S3 | read/write |
| 33 | arkraft-cli | (없음) | — | — |
| 34 | arkraft-sdk | (없음) | — | — |
| 35 | arkraft-wiki | (없음 — markdown 전용) | — | — |

> **Bedrock 호출 패턴**: agent-* 들이 Bedrock 을 직접 boto3 로 부르지 않고 **Claude Agent SDK / pydantic-ai 의 BedrockConverseModel / LiteLLM** 같은 wrapper 를 통해 호출 추정. wrapper 는 boto3 에 dependency 가 있지만 import 가 trasitive — IRSA 의 Bedrock 권한은 여전히 필요 (호출 자체는 boto3 가 함). §3.2 의 Bedrock IAM Action 은 그대로 유효.

> **확정 사항**:
> - **Bucket 패턴**: 모든 agent 가 `teams/{team_id}/*/` 경로로 S3 R/W. `arkraft-{production,staging}` bucket 만 prod/staging — `arkraft-dev` 는 로컬 MinIO 용 (B사 신청 불필요).
> - **`c2-performance-data-production` bucket**: read-only access. 외부 (Finter) 데이터.
> - **Cognito boto3 호출 0건 확인** — Cognito 는 ai-infra Terraform 도 0건. Arkraft 인증은 다른 메커니즘 사용 추정 (JWT 자체 발급 또는 외부 IdP). §10.4 검증 항목으로 유지.
> - **arkraft-web `@aws-sdk/client-s3`**: web Pod 은 SA 없음 → BFF (Next.js API route) 가 사용한다면 별도 IRSA 또는 사용 안 하고 import 만 — 다음 iter 에서 코드 직접 확인 필요.

### 10.3a Local Dev (B사 신청 무관)

| 항목 | 위치 | 비고 |
|------|------|------|
| MinIO (S3 호환) | `arkraft-dev` bucket via S3_ACCESS_KEY_ID/SECRET 환경변수 | 로컬 docker-compose, B사 신청 불필요 |

### 10.4 검증 누락 가능성 (다음 iter 에서 보강)

- [x] **Cognito 미사용 확인**: arkraft-api/web 모두 `cognito-idp` boto3 호출 0건. ai-infra 도 자원 0건. Arkraft 인증은 다른 메커니즘 사용.
- [x] **alpha-pool-infra 별도 레포 — 사실 정정**: ARK-1518 (`Quantit-Github/ai-infra` PR #225 등 4 PR, 2026-04 머지) 으로 alpha-pool 외부 데이터 파이프라인 자원 (Lambda alpha-migrator, alpha-pool-indexer, DynamoDB tables, OpenSearch VECTORSEARCH collection, alpha-pool 관련 Secrets Manager) **모두 제거**. alpha-pool-infra 별도 레포는 더이상 사용 안 함. agent (alpha) 가 직접 데이터를 처리하는 in-house 메커니즘으로 전환 — **이것이 "alpha-pool 내재화" 의 의미**.
- [x] **WAF 사용 여부**: 이전 iter "0건" 으로 잘못 보고. 실제는 `aws/waf/` 모듈 존재 — Atlantis ALB IP allowlist (WAFv2 web ACL + IP set IPv4/IPv6). §7.13 에 추가됨.
- [x] **CloudFront 사용 여부**: ai-infra 0건 확정. 미사용.
- [x] **SES / SNS / SQS 사용 여부**: app code grep 0건. ai-infra 의 SQS는 **Karpenter spot termination queue 가 자동 생성** — 별도 신청 불필요 (Karpenter module 자동). SES/SNS 미사용.
- [ ] **CloudTrail / Config / GuardDuty / Security Hub**: organization-level 자원. B사 본인 계정 정책에 따라 별도. 본 PoC 자원과 무관 — B사 보안팀이 자체 적용.
- [x] **SSM Parameter Store 사용 여부**: 직접 자원 0건. 단 Karpenter EC2NodeClass 가 `/aws/service/eks/...` AMI lookup 시 사용 — Karpenter Controller IAM 의 `ssm:GetParameter` 로 cover (§3.12).
- [ ] **CloudWatch Alarms / Dashboards**: 별도 monitoring 자원. 운영 안정성 위해 권장하되 신청 필수 아님.
- [ ] **Cost Explorer / Billing**: read-only. 비용 모니터링 dashboard 가 있으면 별도.
- [x] **arkraft-web `@aws-sdk/client-s3` 실제 사용 여부**: **확정 — BFF 가 IAM User access key 로 S3 호출**. §6 #3 에 ❌ 표기 + iter 4 권장 사항 (IRSA 전환).
- [x] **Karpenter Controller IRSA Role 의 정확한 IAM Policy** — §3.12 본문 추가됨. **단 IRSA 가 아니라 EKS Pod Identity** 패턴 (terraform-aws-modules/eks v21).
- [x] **External-Secrets Operator IRSA Role** — §3.13 본문 추가됨. KMS Decrypt 추가 권장.
- [x] **VPC Endpoints 정확한 enumeration** — §7.6 정정: 실제는 **S3 + DynamoDB Gateway 만** 존재. ECR/SM/KMS/STS interface endpoint 미존재 → B사 신청 시 권장.

### 10.5 iter 3 신규 검증 항목

- [x] **ECS Fargate (Atlantis)** — 이전 iter "EKS Pod" 으로 잘못 기술. 실제는 ECS Fargate (ARK-599). §7.10 + §3.15 에 추가.
- [x] **EC2 Image Builder (gVisor AMI)** — §7.11 + §3.16 에 추가.
- [x] **SSM Bastion EC2** — §7.12 + §3.17 에 추가.
- [x] **GitHub Actions OIDC + CI Role** — §7.11 + §3.18 에 추가.
- [x] **quanda Bedrock Knowledge Base (Retrieve/RetrieveAndGenerate)** — §3.19 에 추가 (ai-infra/main.tf:858-862 출처).
- [x] **WAF (Atlantis ALB IP allowlist)** — §7.13 에 추가.
- [x] **VPC Peering × 8** — §7.6 에 추가, B사 PoC 면제 명시.
- [x] **Karpenter NodePool 6종** (default-arm64/x86, gvisor-arm64/x86, gpu-x86, agent-workload) — §7.1 에 일부 언급, §3.12 에서 NodeInstanceRole 정책 명시.
- [x] **Karpenter Spot SQS + EventBridge Rule** — §3.12c 자동 생성 명시. §7.4 에서 "SQS 0건" 정정.
- [x] **EKS Pod Identity Agent add-on** — Karpenter 가 사용. EKS add-on 으로 별도 신청 항목 (Tier-2).

---

## 변경 이력

- **iter 1 (2026-04-28)**: 초안 작성. Pass 1 Codebase Forensics 3개 영역 (Terraform IRSA + AWS resource, Helm chart SA mapping, 앱 코드 boto3/aws-sdk import) 모두 반영. 25개 AWS Service 매트릭스, 11개 IRSA Role 매트릭스, 8개 IAM 최소권한 정책 JSON, 9개 ServiceAccount 매핑, 자원 인벤토리 7.1-7.10, Region 변경 영향 17개 항목, 9.1-9.5 Tier 별 신청 체크리스트, 36개 출처 reference 작성.
- **iter 5 (2026-04-28)**: 5명 reviewer iter 4 발견사항 일괄 처리.
  - **QA FAIL**: §9 체크리스트 ECS/WAF/Image Builder/SSM Bastion/GitHub OIDC/EKS Pod Identity Agent/EKS Access Roles 추가, §3.8 Athena workgroup ARN narrow + Glue catalog ARN narrow, §3.16 pseudo-JSON → blockquote.
  - **Security SCOPED-DOWN**: §3.4 / §3.5 Trust narrow JSON 인라인, §3.18 GitHub Actions Trust subject narrow (repo+branch 화이트리스트), §3.18 GetAuthToken 사유 코멘트, §3.20 신설 (`arkraft-web-server-role` IRSA + IAM User access key 폐기 절차), §3.20 → §3.21 (RabbitMQ).
  - **Reviewer REVISE**: §3.15 ECS Execution Role Assume 행 추가, §3.19 Bedrock KB 가 §3.5 Statement 추가임을 명시, §7.6 / §7.7 / §7.11 / §7.12 / §7.13 표 Region·암호화·접근 제어 컬럼 추가.
  - **Completeness MISSING (경미)**: §6 #10 agent-manager 행, §7.7 EKS Access Roles + Pod Identity Agent + GitHub OIDC, §3.14 Lambda EventBridge resource policy, §3.16 Image Builder SSM Managed Policy, §7.7 Cognito 미사용 확정.
  - **AWS-Architect GAPS**: §7.6 AOSS VPC Endpoint, §7.3 DynamoDB Streams 주의 사항.
  - 5층 reviewer iter 6 재검증 대기.

- **iter 3 (2026-04-28)**: Completeness reviewer (MISSING 21+3) + AWS-Architect (GAPS 17) 발견사항 반영.
  - **사실 오류 정정**: (1) Atlantis = ECS Fargate (이전 iter "EKS Pod"), (2) Karpenter = EKS Pod Identity (IRSA 아님), (3) WAF 미사용 → 실제 존재 (Atlantis ALB IP allowlist).
  - **누락 자원 추가** (§7): SSM Bastion EC2 (§7.1), EC2 Image Builder pipeline (§7.1, §7.11), VPC Peering × 8 (§7.6, B사 면제), Karpenter NodePool 6종 (§7.1), Karpenter spot SQS + EventBridge (§7.4), VPC Endpoint 정정 (S3+DynamoDB Gateway만 존재 — interface 부재), WAFv2 web ACL + IP set (§7.13), ECS Fargate (Atlantis) (§7.10).
  - **누락 IAM Role 추가** (§3): §3.15 ECS Task/Execution Role, §3.16 EC2 Image Builder Service Role, §3.17 SSM Bastion Instance Profile, §3.18 GitHub Actions CI Role (OIDC), §3.19 quanda Bedrock Knowledge Base (Retrieve/RetrieveAndGenerate).
  - **§6 web 보안 리스크 표시**: web Pod 이 IRSA 가 아닌 IAM User long-lived access key (`AKIA...`) 사용 — `arkraft-deploy/web/values/production/values.yaml` plaintext 노출. iter 4 에서 IRSA 전환 권장 §3.x 작성 예정.
  - **§10.3 boto3 호출 정정**: arkraft-api/src 직접 boto3 호출 0건 (Glue/S3 모두). agent-* 도 Bedrock 직접 호출 0건 (wrapper SDK 경유). §3.1 GlueDataCatalogReadOnly 사용성 iter 4 재확인.
  - **§10.4 검증 항목 갱신**: WAF/CloudFront/Cognito/SES-SNS-SQS/SSM Param Store 사용 여부 확정.
  - 5층 reviewer 재검토 (iter 4) 대기.

- **iter 2 (2026-04-28)**: 5층 reviewer 의 발견사항 반영.
  - Reviewer (REVISE): IRSA 매트릭스 컬럼 헤더 정정 (핵심 IAM Action / Trust Policy condition 으로), §3.9/§3.11 invalid JSON 블록을 blockquote 텍스트로 변환, §7.2/§7.4/§7.5/§7.8 region·암호화·접근 제어 컬럼 추가.
  - QA (FAIL): IRSA 매트릭스 #5 `bedrock:*` → `bedrock:InvokeModel, InvokeModelWithResponseStream` 정정, §3.8 S3DataSourceRead `arn:aws:s3:::*` → 특정 bucket narrow + `aws:ResourceAccount` condition.
  - Security (SCOPED-DOWN): §3.1 Trust subject narrow 권장 명시 (현재 wildcard `*:*` → `system:serviceaccount:arkraft:arkraft-api`), §3.5 quanda Bedrock anthropic.* wildcard → 명시 모델 ARN narrow, c2-performance-data-production read-only 분리 statement.
  - §3.12 Karpenter Controller (Pod Identity) IAM Policy concrete (terraform-aws-modules/eks v21 자동 생성 패턴).
  - §3.13 External-Secrets Operator IRSA Policy concrete (ai-infra/external-secrets/main.tf 추출).
  - §3.14 Lambda alpha-migrator Execution Role concrete + Bedrock narrow (ai-infra/aws/alpha-migrator/main.tf:138 의 `bedrock:* Resource: "*"` 운영 over-permission 표시 + 권장 narrow 패턴).
  - §3.15 AmazonMQ — Pod 측 IAM 불필요 명시 (Secrets Manager 경유).
  - 5층 reviewer 재검토 대기.
