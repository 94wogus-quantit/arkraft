# BYOC Terraform Deploy 권한 — PM팀 이식용 IAM Permission 전수 목록

> **목적**: B사가 PM팀(Quantit + B사 합작 운영팀)에게 부여해야 할 **Terraform deploy 권한** 전수 목록. PM팀은 이 권한으로 `terraform apply` 를 실행해 arkraft 인프라를 B사 AWS 계정에 처음부터 만든다.
>
> **두 권한 카테고리**:
> | | 운영 권한 (런타임) | **이식 작업 권한 (Terraform deploy) — 본 문서** |
> |--|-------------------|-----------------------------------------------|
> | 누가 사용? | Pod (IRSA) + 자원 자체 | **PM팀** (User/Role/SSO IAM Identity) |
> | 언제? | 자원 생성 후 Pod 동작 시 | **자원 생성/수정/삭제 시점 (Terraform apply)** |
> | 예시 Action | `s3:GetObject`, `bedrock:InvokeModel` | **`s3:CreateBucket`, `eks:CreateCluster`, `iam:CreateRole`** |
> | Doc | [`BYOC_AWS_PERMISSIONS.md`](./BYOC_AWS_PERMISSIONS.md) | **본 문서** |
>
> **Region**: `ap-northeast-2` (Seoul) 기준. B사 실 deploy region 변경 시 §6 참고.
>
> **arkraft 한정**: quanda / Atlantis (ECS) / EC2 Image Builder / SSM Bastion / WAFv2 / VPC Peering / OpenSearch Serverless / DynamoDB / Lambda alpha-migrator / agent-sandbox (Athena/Glue) — 모두 범위 밖.

---

## 1. 개요

### 1.1 PM팀이 받아야 할 권한 카테고리

PM팀이 B사 AWS 계정에 arkraft 를 이식하기 위해 받아야 할 권한은 다음 7개 카테고리:

1. **VPC 네트워킹** — VPC / Subnet / IGW / NAT / EIP / SG / Route Table / VPC Endpoint
2. **EKS 클러스터** — Cluster / Add-on / Access Entry / Access Policy / Pod Identity Agent
3. **EC2 (Karpenter)** — Launch Template / Instance / Volume / SecurityGroup / Spot
4. **Database / Cache** — RDS PostgreSQL / ElastiCache Redis / Parameter/Subnet Group
5. **Storage / Container** — S3 (8 sub-resources) / ECR Repository
6. **Identity / Encryption / Secrets** — IAM Role/Policy/InstanceProfile/OIDC + KMS Key/Alias + Secrets Manager
7. **DNS / TLS / Load Balancer / Messaging / Observability** — Route53 / ACM / ELBv2 / AmazonMQ / CloudWatch Logs

### 1.2 권장 구조: service-별 분리 정책

단일 admin-equivalent policy 대신 **service-별 IAM Policy 분리** 권장. B사 보안팀이 service 별 검토 + 부분 거부 가능. 또한 PM팀이 단계적 deploy 시 부분 권한만 사용 가능.

### 1.3 Terraform Backend 권한 (별도)

B사 자체 Terraform backend (S3 + DynamoDB lock) 를 사용한다면 다음 권한 별도:
- `s3:GetObject/PutObject/DeleteObject` on `{terraform-state-bucket}/*`
- `dynamodb:GetItem/PutItem/DeleteItem` on `{tf-state-lock-table}`

---

## 2. Service 매트릭스

> ai-infra Terraform 자원 type × CRUD Action 매트릭스. arkraft 한정 (범위 밖 자원 제외).

| # | Service | Resource Type (Terraform) | CRUD Actions | Resource ARN scope (narrow) | 사유 |
|---|---------|--------------------------|--------------|------------------------------|------|
| 1 | **VPC** | `aws_vpc`, `aws_subnet`, `aws_internet_gateway`, `aws_nat_gateway`, `aws_eip`, `aws_route_table`, `aws_vpc_endpoint` | `ec2:Create*Vpc*`, `ec2:Describe*`, `ec2:Modify*Vpc*`, `ec2:Delete*Vpc*`, `ec2:CreateSubnet`, `ec2:CreateInternetGateway`, `ec2:AttachInternetGateway`, `ec2:CreateNatGateway`, `ec2:AllocateAddress`, `ec2:CreateRouteTable`, `ec2:CreateRoute`, `ec2:AssociateRouteTable`, `ec2:CreateVpcEndpoint`, `ec2:ModifyVpcEndpoint` | `arn:aws:ec2:ap-northeast-2:{ACCOUNT_ID}:*` (Tag condition 권장) | VPC + 6 Subnet + NAT/EIP + Routing + S3 Gateway Endpoint |
| 2 | **Security Group** | `aws_security_group`, `aws_security_group_rule` | `ec2:CreateSecurityGroup`, `ec2:DescribeSecurityGroups`, `ec2:AuthorizeSecurityGroup{Ingress,Egress}`, `ec2:RevokeSecurityGroup{Ingress,Egress}`, `ec2:DeleteSecurityGroup`, `ec2:UpdateSecurityGroupRuleDescriptions{Ingress,Egress}`, `ec2:ModifySecurityGroupRules` | (동일) | ALB / EKS pod / RDS / Redis / RabbitMQ SG |
| 3 | **EKS Cluster** | (terraform-aws-modules/eks 자동 — 직접 `aws_eks_cluster` 정의 0건이지만 module 이 생성) | `eks:CreateCluster`, `eks:DescribeCluster`, `eks:UpdateCluster*`, `eks:DeleteCluster`, `eks:TagResource`, `eks:UntagResource`, `eks:ListClusters` | `arn:aws:eks:ap-northeast-2:{ACCOUNT_ID}:cluster/{CLUSTER_NAME}` | arkraft EKS 클러스터 생성 |
| 4 | **EKS Add-on** | `aws_eks_addon` | `eks:CreateAddon`, `eks:DescribeAddon`, `eks:UpdateAddon`, `eks:DeleteAddon`, `eks:DescribeAddonVersions`, `eks:DescribeAddonConfiguration` | `arn:aws:eks:*:*:addon/{CLUSTER}/*/*` | EBS CSI / VPC CNI / CoreDNS / kube-proxy / Pod Identity Agent |
| 5 | **EKS Access Entry** | `aws_eks_access_entry`, `aws_eks_access_policy_association` | `eks:CreateAccessEntry`, `eks:DescribeAccessEntry`, `eks:UpdateAccessEntry`, `eks:DeleteAccessEntry`, `eks:ListAccessEntries`, `eks:AssociateAccessPolicy`, `eks:DisassociateAccessPolicy`, `eks:ListAssociatedAccessPolicies` | `arn:aws:eks:*:*:access-entry/{CLUSTER}/*` | kubectl/Console 접근 (Role-based) |
| 6 | **EC2 (Karpenter)** | (Karpenter Pod Identity 자체는 `aws_iam_role` + module — 운영 시점 동작이지만 Terraform 도 일부 자원 만듦) + Karpenter NodeInstanceRole | `ec2:CreateLaunchTemplate`, `ec2:DeleteLaunchTemplate`, `ec2:ModifyLaunchTemplate`, `ec2:CreateLaunchTemplateVersion`, `ec2:DescribeLaunchTemplates*`, `ec2:RunInstances`, `ec2:TerminateInstances`, `ec2:DescribeInstances`, `ec2:CreateTags`, `iam:PassRole` | `aws:ResourceTag/karpenter.sh/nodepool: *` Condition 권장 | Karpenter NodePool 동작 |
| 7 | **EBS** | (Karpenter NodePool 이 EC2 launch 시 EBS volume 자동 생성 — Terraform 직접 자원 0건) | `ec2:CreateVolume`, `ec2:AttachVolume`, `ec2:DetachVolume`, `ec2:DeleteVolume`, `ec2:DescribeVolumes`, `ec2:CreateSnapshot`, `ec2:DeleteSnapshot`, `ec2:DescribeSnapshots` | `arn:aws:ec2:*:*:volume/*` (Tag condition) | EBS gp3 volume |
| 8 | **RDS PostgreSQL** | `aws_db_instance`, `aws_db_parameter_group`, `aws_db_subnet_group` | `rds:CreateDBInstance`, `rds:ModifyDBInstance`, `rds:DeleteDBInstance`, `rds:DescribeDBInstances`, `rds:RebootDBInstance`, `rds:CreateDBSubnetGroup`, `rds:DescribeDBSubnetGroups`, `rds:DeleteDBSubnetGroup`, `rds:CreateDBParameterGroup`, `rds:ModifyDBParameterGroup`, `rds:DescribeDBParameterGroups`, `rds:DeleteDBParameterGroup`, `rds:AddTagsToResource`, `rds:ListTagsForResource` | `arn:aws:rds:ap-northeast-2:{ACCOUNT_ID}:db:arkraft-*`, `:subgrp:arkraft-*`, `:pg:arkraft-*` | arkraft-postgres |
| 9 | **ElastiCache Redis** | `aws_elasticache_cluster`, `aws_elasticache_parameter_group`, `aws_elasticache_subnet_group` | `elasticache:CreateCacheCluster`, `elasticache:ModifyCacheCluster`, `elasticache:DeleteCacheCluster`, `elasticache:DescribeCacheClusters`, `elasticache:CreateCacheSubnetGroup`, `elasticache:DescribeCacheSubnetGroups`, `elasticache:DeleteCacheSubnetGroup`, `elasticache:CreateCacheParameterGroup`, `elasticache:ModifyCacheParameterGroup`, `elasticache:DescribeCacheParameterGroups`, `elasticache:DeleteCacheParameterGroup`, `elasticache:AddTagsToResource`, `elasticache:ListTagsForResource` | `arn:aws:elasticache:ap-northeast-2:{ACCOUNT_ID}:cluster:arkraft-*` | arkraft-redis |
| 10 | **S3 Bucket** | `aws_s3_bucket` + 7 sub-config (`cors`, `lifecycle`, `policy`, `public_access_block`, `sse`, `versioning`, `website`) | `s3:CreateBucket`, `s3:DeleteBucket`, `s3:PutBucketCORS`, `s3:GetBucketCORS`, `s3:PutLifecycleConfiguration`, `s3:GetLifecycleConfiguration`, `s3:PutBucketPolicy`, `s3:GetBucketPolicy`, `s3:DeleteBucketPolicy`, `s3:PutBucketPublicAccessBlock`, `s3:GetBucketPublicAccessBlock`, `s3:PutEncryptionConfiguration`, `s3:GetEncryptionConfiguration`, `s3:PutBucketVersioning`, `s3:GetBucketVersioning`, `s3:PutBucketWebsite`, `s3:GetBucketWebsite`, `s3:PutBucketTagging`, `s3:GetBucketTagging`, `s3:ListBucket`, `s3:ListAllMyBuckets` | `arn:aws:s3:::arkraft-*`, `arn:aws:s3:::ai-infra-argo-workflows-logs*` | arkraft-production / arkraft-staging / argo-workflows-logs |
| 11 | **ECR Repository** | `aws_ecr_repository`, `aws_ecr_lifecycle_policy` | `ecr:CreateRepository`, `ecr:DescribeRepositories`, `ecr:DeleteRepository`, `ecr:PutImageScanningConfiguration`, `ecr:PutLifecyclePolicy`, `ecr:GetLifecyclePolicy`, `ecr:DeleteLifecyclePolicy`, `ecr:TagResource`, `ecr:UntagResource`, `ecr:ListTagsForResource`, `ecr:DescribeRegistry`, `ecr:GetAuthorizationToken` | `arn:aws:ecr:ap-northeast-2:{ACCOUNT_ID}:repository/ark/*` | arkraft 9 services 의 image repository |
| 12 | **IAM** | `aws_iam_role`, `aws_iam_role_policy`, `aws_iam_role_policy_attachment`, `aws_iam_policy`, `aws_iam_instance_profile`, `aws_iam_openid_connect_provider` | `iam:CreateRole`, `iam:GetRole`, `iam:UpdateRole`, `iam:DeleteRole`, `iam:CreatePolicy`, `iam:GetPolicy`, `iam:DeletePolicy`, `iam:CreatePolicyVersion`, `iam:DeletePolicyVersion`, `iam:ListPolicyVersions`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PutRolePolicy`, `iam:GetRolePolicy`, `iam:DeleteRolePolicy`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, `iam:PassRole`, `iam:CreateInstanceProfile`, `iam:GetInstanceProfile`, `iam:DeleteInstanceProfile`, `iam:AddRoleToInstanceProfile`, `iam:RemoveRoleFromInstanceProfile`, `iam:CreateOpenIDConnectProvider`, `iam:GetOpenIDConnectProvider`, `iam:UpdateOpenIDConnectProviderThumbprint`, `iam:DeleteOpenIDConnectProvider`, `iam:TagRole`, `iam:TagPolicy`, `iam:TagInstanceProfile`, `iam:UntagRole`, `iam:UntagPolicy`, `iam:UntagInstanceProfile` | `arn:aws:iam::{ACCOUNT_ID}:role/arkraft-*`, `:policy/arkraft-*`, `:instance-profile/arkraft-*`, `:oidc-provider/oidc.eks.*` | arkraft IRSA Role / NodeInstanceRole / OIDC Provider |
| 13 | **KMS** | `aws_kms_key`, `aws_kms_alias` | `kms:CreateKey`, `kms:DescribeKey`, `kms:ScheduleKeyDeletion`, `kms:CancelKeyDeletion`, `kms:CreateAlias`, `kms:DeleteAlias`, `kms:UpdateAlias`, `kms:ListAliases`, `kms:PutKeyPolicy`, `kms:GetKeyPolicy`, `kms:EnableKeyRotation`, `kms:DisableKeyRotation`, `kms:GetKeyRotationStatus`, `kms:TagResource`, `kms:UntagResource`, `kms:ListResourceTags` | `arn:aws:kms:ap-northeast-2:{ACCOUNT_ID}:key/*` (Tag condition) + `arn:aws:kms:*:*:alias/arkraft/*` | arkraft KMS key (data-source-credentials) |
| 14 | **Secrets Manager** | `aws_secretsmanager_secret`, `aws_secretsmanager_secret_version` | `secretsmanager:CreateSecret`, `secretsmanager:DescribeSecret`, `secretsmanager:UpdateSecret`, `secretsmanager:DeleteSecret`, `secretsmanager:RestoreSecret`, `secretsmanager:PutSecretValue`, `secretsmanager:GetSecretValue`, `secretsmanager:TagResource`, `secretsmanager:UntagResource`, `secretsmanager:ListSecrets`, `secretsmanager:RotateSecret`, `secretsmanager:CancelRotateSecret` | `arn:aws:secretsmanager:ap-northeast-2:{ACCOUNT_ID}:secret:ai-infra/*`, `:secret:arkraft/*` | RDS / RabbitMQ credentials |
| 15 | **Route53** | `aws_route53_zone`, `aws_route53_record` | `route53:CreateHostedZone`, `route53:GetHostedZone`, `route53:UpdateHostedZoneComment`, `route53:DeleteHostedZone`, `route53:ListHostedZones*`, `route53:ChangeResourceRecordSets`, `route53:ListResourceRecordSets`, `route53:GetChange`, `route53:ChangeTagsForResource`, `route53:ListTagsForResource` | `arn:aws:route53:::hostedzone/*` (List 는 account-wide 강제) | B사 도메인 hosted zone |
| 16 | **ACM** | `aws_acm_certificate` (+ `aws_acm_certificate_validation` 가능) | `acm:RequestCertificate`, `acm:DescribeCertificate`, `acm:GetCertificate`, `acm:DeleteCertificate`, `acm:ListCertificates`, `acm:AddTagsToCertificate`, `acm:RemoveTagsFromCertificate`, `acm:ListTagsForCertificate` | `arn:aws:acm:ap-northeast-2:{ACCOUNT_ID}:certificate/*` | wildcard *.B사도메인 |
| 17 | **ELBv2 (ALB/NLB)** | `aws_lb`, `aws_lb_listener`, `aws_lb_target_group` (Istio 가 aws-load-balancer-controller 통해 동적 생성하지만 직접 정의도 가능) | `elasticloadbalancing:CreateLoadBalancer`, `elasticloadbalancing:DescribeLoadBalancers`, `elasticloadbalancing:ModifyLoadBalancer*`, `elasticloadbalancing:DeleteLoadBalancer`, `elasticloadbalancing:CreateTargetGroup`, `elasticloadbalancing:DescribeTargetGroups`, `elasticloadbalancing:ModifyTargetGroup*`, `elasticloadbalancing:DeleteTargetGroup`, `elasticloadbalancing:RegisterTargets`, `elasticloadbalancing:DeregisterTargets`, `elasticloadbalancing:CreateListener`, `elasticloadbalancing:DescribeListeners`, `elasticloadbalancing:ModifyListener`, `elasticloadbalancing:DeleteListener`, `elasticloadbalancing:AddTags`, `elasticloadbalancing:RemoveTags`, `elasticloadbalancing:DescribeTags` | `arn:aws:elasticloadbalancing:ap-northeast-2:{ACCOUNT_ID}:*` | Istio external/internal gateway |
| 18 | **AmazonMQ** | `aws_mq_broker` | `mq:CreateBroker`, `mq:DescribeBroker`, `mq:UpdateBroker`, `mq:RebootBroker`, `mq:DeleteBroker`, `mq:ListBrokers`, `mq:CreateTags`, `mq:DeleteTags`, `mq:ListTags`, `mq:CreateUser`, `mq:UpdateUser`, `mq:DeleteUser`, `mq:DescribeUser`, `mq:ListUsers`, `mq:CreateConfiguration`, `mq:UpdateConfiguration`, `mq:DescribeConfiguration*` | `arn:aws:mq:ap-northeast-2:{ACCOUNT_ID}:broker:*` | RabbitMQ broker |
| 19 | **CloudWatch Logs** | `aws_cloudwatch_log_group` | `logs:CreateLogGroup`, `logs:DescribeLogGroups`, `logs:DeleteLogGroup`, `logs:PutRetentionPolicy`, `logs:DeleteRetentionPolicy`, `logs:TagResource`, `logs:UntagResource`, `logs:ListTagsForResource`, `logs:PutResourcePolicy`, `logs:DescribeResourcePolicies` | `arn:aws:logs:ap-northeast-2:{ACCOUNT_ID}:log-group:*` (path condition 권장) | EKS control plane log + 인프라 컴포넌트 log |
| 20 | **SQS** | (Karpenter terraform-aws-modules 자동 생성 — `{app}-karpenter` queue) | `sqs:CreateQueue`, `sqs:GetQueueAttributes`, `sqs:SetQueueAttributes`, `sqs:DeleteQueue`, `sqs:ListQueues`, `sqs:TagQueue` | `arn:aws:sqs:ap-northeast-2:{ACCOUNT_ID}:*-karpenter*` | Karpenter spot interruption queue |
| 21 | **EventBridge** | (Karpenter terraform-aws-modules 자동 생성 — spot interruption rules) | `events:PutRule`, `events:DescribeRule`, `events:DeleteRule`, `events:PutTargets`, `events:RemoveTargets` | `arn:aws:events:ap-northeast-2:{ACCOUNT_ID}:rule/*-karpenter*` | Karpenter spot interruption rules |

---

## 3. 권장 IAM Policy JSON (service 별 분리)

> arkraft 한정 — `*FullAccess` / `PowerUserAccess` / `AdministratorAccess` 사용 금지. Resource ARN 가능한 한 narrow + Tag/Path Condition 권장.

### 3.1 VPC 네트워킹

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "VPCManagement",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateVpc",
        "ec2:DescribeVpcs",
        "ec2:ModifyVpcAttribute",
        "ec2:DeleteVpc",
        "ec2:CreateSubnet",
        "ec2:DescribeSubnets",
        "ec2:ModifySubnetAttribute",
        "ec2:DeleteSubnet",
        "ec2:CreateInternetGateway",
        "ec2:AttachInternetGateway",
        "ec2:DetachInternetGateway",
        "ec2:DeleteInternetGateway",
        "ec2:DescribeInternetGateways",
        "ec2:CreateNatGateway",
        "ec2:DeleteNatGateway",
        "ec2:DescribeNatGateways",
        "ec2:AllocateAddress",
        "ec2:ReleaseAddress",
        "ec2:DescribeAddresses",
        "ec2:CreateRouteTable",
        "ec2:DeleteRouteTable",
        "ec2:AssociateRouteTable",
        "ec2:DisassociateRouteTable",
        "ec2:CreateRoute",
        "ec2:DeleteRoute",
        "ec2:DescribeRouteTables",
        "ec2:CreateVpcEndpoint",
        "ec2:ModifyVpcEndpoint",
        "ec2:DeleteVpcEndpoints",
        "ec2:DescribeVpcEndpoints",
        "ec2:CreateTags",
        "ec2:DeleteTags",
        "ec2:DescribeTags",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeAccountAttributes"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
      }
    }
  ]
}
```

> **Resource: "\*" 사유**: VPC API 의 대부분이 region-level 만 narrow 가능. `aws:RequestedRegion` Condition 으로 region narrow.

### 3.2 Security Group

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:CreateSecurityGroup",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeSecurityGroupRules",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:DeleteSecurityGroup",
        "ec2:UpdateSecurityGroupRuleDescriptionsIngress",
        "ec2:UpdateSecurityGroupRuleDescriptionsEgress",
        "ec2:ModifySecurityGroupRules"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
      }
    }
  ]
}
```

### 3.3 EKS

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EKSClusterFullManagement",
      "Effect": "Allow",
      "Action": [
        "eks:CreateCluster",
        "eks:DescribeCluster",
        "eks:UpdateClusterConfig",
        "eks:UpdateClusterVersion",
        "eks:DeleteCluster",
        "eks:ListClusters",
        "eks:TagResource",
        "eks:UntagResource",
        "eks:ListTagsForResource"
      ],
      "Resource": "arn:aws:eks:ap-northeast-2:{ACCOUNT_ID}:cluster/{CLUSTER_NAME}"
    },
    {
      "Sid": "EKSAddonManagement",
      "Effect": "Allow",
      "Action": [
        "eks:CreateAddon",
        "eks:DescribeAddon",
        "eks:UpdateAddon",
        "eks:DeleteAddon",
        "eks:ListAddons",
        "eks:DescribeAddonVersions",
        "eks:DescribeAddonConfiguration"
      ],
      "Resource": [
        "arn:aws:eks:*:*:addon/{CLUSTER_NAME}/*/*",
        "arn:aws:eks:*:*:cluster/{CLUSTER_NAME}"
      ]
    },
    {
      "Sid": "EKSAccessEntryManagement",
      "Effect": "Allow",
      "Action": [
        "eks:CreateAccessEntry",
        "eks:DescribeAccessEntry",
        "eks:UpdateAccessEntry",
        "eks:DeleteAccessEntry",
        "eks:ListAccessEntries",
        "eks:AssociateAccessPolicy",
        "eks:DisassociateAccessPolicy",
        "eks:ListAssociatedAccessPolicies"
      ],
      "Resource": "arn:aws:eks:*:*:access-entry/{CLUSTER_NAME}/*"
    },
    {
      "Sid": "EKSPodIdentityManagement",
      "Effect": "Allow",
      "Action": [
        "eks:CreatePodIdentityAssociation",
        "eks:DescribePodIdentityAssociation",
        "eks:UpdatePodIdentityAssociation",
        "eks:DeletePodIdentityAssociation",
        "eks:ListPodIdentityAssociations"
      ],
      "Resource": "arn:aws:eks:*:*:podidentityassociation/{CLUSTER_NAME}/*"
    }
  ]
}
```

### 3.4 EC2 (Karpenter NodePool 동작 + Terraform 자체 자원)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EC2LaunchTemplateAndInstance",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateLaunchTemplate",
        "ec2:CreateLaunchTemplateVersion",
        "ec2:ModifyLaunchTemplate",
        "ec2:DeleteLaunchTemplate",
        "ec2:DescribeLaunchTemplates",
        "ec2:DescribeLaunchTemplateVersions",
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeInstanceTypeOfferings",
        "ec2:DescribeImages",
        "ec2:DescribeAvailabilityZones",
        "ec2:CreateFleet",
        "ec2:CreateTags",
        "ec2:DescribeSpotPriceHistory"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
      }
    },
    {
      "Sid": "EC2VolumeAndSnapshot",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateVolume",
        "ec2:AttachVolume",
        "ec2:DetachVolume",
        "ec2:DeleteVolume",
        "ec2:DescribeVolumes",
        "ec2:CreateSnapshot",
        "ec2:DeleteSnapshot",
        "ec2:DescribeSnapshots"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
      }
    },
    {
      "Sid": "EC2NetworkInterface",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:ModifyNetworkInterfaceAttribute",
        "ec2:DeleteNetworkInterface",
        "ec2:AttachNetworkInterface",
        "ec2:DetachNetworkInterface"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
      }
    }
  ]
}
```

### 3.5 RDS PostgreSQL

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:CreateDBInstance",
        "rds:ModifyDBInstance",
        "rds:DeleteDBInstance",
        "rds:DescribeDBInstances",
        "rds:RebootDBInstance",
        "rds:StartDBInstance",
        "rds:StopDBInstance",
        "rds:CreateDBSubnetGroup",
        "rds:DescribeDBSubnetGroups",
        "rds:DeleteDBSubnetGroup",
        "rds:ModifyDBSubnetGroup",
        "rds:CreateDBParameterGroup",
        "rds:DescribeDBParameterGroups",
        "rds:DescribeDBParameters",
        "rds:ModifyDBParameterGroup",
        "rds:DeleteDBParameterGroup",
        "rds:AddTagsToResource",
        "rds:ListTagsForResource",
        "rds:RemoveTagsFromResource"
      ],
      "Resource": [
        "arn:aws:rds:ap-northeast-2:{ACCOUNT_ID}:db:arkraft-*",
        "arn:aws:rds:ap-northeast-2:{ACCOUNT_ID}:subgrp:arkraft-*",
        "arn:aws:rds:ap-northeast-2:{ACCOUNT_ID}:pg:arkraft-*"
      ]
    },
    {
      "Sid": "RDSGlobalRead",
      "Effect": "Allow",
      "Action": ["rds:DescribeDBEngineVersions"],
      "Resource": "*"
    }
  ]
}
```

### 3.6 ElastiCache Redis

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticache:CreateCacheCluster",
        "elasticache:ModifyCacheCluster",
        "elasticache:DeleteCacheCluster",
        "elasticache:DescribeCacheClusters",
        "elasticache:CreateCacheSubnetGroup",
        "elasticache:DescribeCacheSubnetGroups",
        "elasticache:DeleteCacheSubnetGroup",
        "elasticache:ModifyCacheSubnetGroup",
        "elasticache:CreateCacheParameterGroup",
        "elasticache:DescribeCacheParameterGroups",
        "elasticache:DescribeCacheParameters",
        "elasticache:ModifyCacheParameterGroup",
        "elasticache:DeleteCacheParameterGroup",
        "elasticache:AddTagsToResource",
        "elasticache:ListTagsForResource",
        "elasticache:RemoveTagsFromResource"
      ],
      "Resource": [
        "arn:aws:elasticache:ap-northeast-2:{ACCOUNT_ID}:cluster:arkraft-*",
        "arn:aws:elasticache:ap-northeast-2:{ACCOUNT_ID}:subnetgroup:arkraft-*",
        "arn:aws:elasticache:ap-northeast-2:{ACCOUNT_ID}:parametergroup:arkraft-*"
      ]
    },
    {
      "Sid": "ElastiCacheGlobalRead",
      "Effect": "Allow",
      "Action": ["elasticache:DescribeEngineDefaultParameters"],
      "Resource": "*"
    }
  ]
}
```

### 3.7 S3

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:PutBucketCORS",
        "s3:GetBucketCORS",
        "s3:PutLifecycleConfiguration",
        "s3:GetLifecycleConfiguration",
        "s3:PutBucketPolicy",
        "s3:GetBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutEncryptionConfiguration",
        "s3:GetEncryptionConfiguration",
        "s3:PutBucketVersioning",
        "s3:GetBucketVersioning",
        "s3:PutBucketWebsite",
        "s3:GetBucketWebsite",
        "s3:DeleteBucketWebsite",
        "s3:PutBucketTagging",
        "s3:GetBucketTagging"
      ],
      "Resource": [
        "arn:aws:s3:::arkraft-*",
        "arn:aws:s3:::ai-infra-argo-workflows-logs*"
      ]
    },
    {
      "Sid": "S3ListAccountWide",
      "Effect": "Allow",
      "Action": "s3:ListAllMyBuckets",
      "Resource": "*"
    }
  ]
}
```

> **Resource: "\*" 사유 (ListAllMyBuckets)**: ListAllMyBuckets API 는 account-wide 만 — narrow 불가.

### 3.8 ECR

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:DeleteRepository",
        "ecr:PutImageScanningConfiguration",
        "ecr:PutLifecyclePolicy",
        "ecr:GetLifecyclePolicy",
        "ecr:DeleteLifecyclePolicy",
        "ecr:TagResource",
        "ecr:UntagResource",
        "ecr:ListTagsForResource"
      ],
      "Resource": "arn:aws:ecr:ap-northeast-2:{ACCOUNT_ID}:repository/ark/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:DescribeRegistry",
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3.9 IAM

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IAMRoleManagementArkraftScope",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:UpdateRole",
        "iam:UpdateRoleDescription",
        "iam:UpdateAssumeRolePolicy",
        "iam:DeleteRole",
        "iam:ListRoles",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:ListRolePolicies",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:ListRoleTags",
        "iam:CreateInstanceProfile",
        "iam:GetInstanceProfile",
        "iam:DeleteInstanceProfile",
        "iam:AddRoleToInstanceProfile",
        "iam:RemoveRoleFromInstanceProfile",
        "iam:TagInstanceProfile",
        "iam:UntagInstanceProfile"
      ],
      "Resource": [
        "arn:aws:iam::{ACCOUNT_ID}:role/arkraft-*",
        "arn:aws:iam::{ACCOUNT_ID}:role/ai-infra-eks-*",
        "arn:aws:iam::{ACCOUNT_ID}:instance-profile/arkraft-*",
        "arn:aws:iam::{ACCOUNT_ID}:instance-profile/ai-infra-eks-*"
      ]
    },
    {
      "Sid": "IAMPolicyManagementArkraftScope",
      "Effect": "Allow",
      "Action": [
        "iam:CreatePolicy",
        "iam:GetPolicy",
        "iam:DeletePolicy",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicyVersion",
        "iam:ListPolicyVersions",
        "iam:GetPolicyVersion",
        "iam:TagPolicy",
        "iam:UntagPolicy"
      ],
      "Resource": "arn:aws:iam::{ACCOUNT_ID}:policy/arkraft-*"
    },
    {
      "Sid": "IAMOIDCProvider",
      "Effect": "Allow",
      "Action": [
        "iam:CreateOpenIDConnectProvider",
        "iam:GetOpenIDConnectProvider",
        "iam:UpdateOpenIDConnectProviderThumbprint",
        "iam:DeleteOpenIDConnectProvider",
        "iam:AddClientIDToOpenIDConnectProvider",
        "iam:RemoveClientIDFromOpenIDConnectProvider",
        "iam:TagOpenIDConnectProvider",
        "iam:UntagOpenIDConnectProvider",
        "iam:ListOpenIDConnectProviders"
      ],
      "Resource": "arn:aws:iam::{ACCOUNT_ID}:oidc-provider/oidc.eks.*"
    },
    {
      "Sid": "IAMPassRoleNarrow",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "arn:aws:iam::{ACCOUNT_ID}:role/arkraft-*",
        "arn:aws:iam::{ACCOUNT_ID}:role/ai-infra-eks-*"
      ],
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": [
            "ec2.amazonaws.com",
            "eks.amazonaws.com",
            "rds.amazonaws.com",
            "elasticache.amazonaws.com"
          ]
        }
      }
    },
    {
      "Sid": "IAMReadOnlyForTerraform",
      "Effect": "Allow",
      "Action": [
        "iam:GetUser",
        "iam:ListAccountAliases",
        "iam:GetAccountSummary"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMServiceLinkedRoleNarrow",
      "Effect": "Allow",
      "Action": "iam:CreateServiceLinkedRole",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "iam:AWSServiceName": [
            "eks.amazonaws.com",
            "eks-nodegroup.amazonaws.com",
            "elasticloadbalancing.amazonaws.com",
            "spot.amazonaws.com",
            "elasticache.amazonaws.com",
            "rds.amazonaws.com"
          ]
        }
      }
    }
  ]
}
```

> **iam:PassRole Condition**: `iam:PassedToService` 명시적 화이트리스트 — EC2 (Karpenter), EKS, RDS, ElastiCache 만. 다른 service 로 passrole 차단.
>
> **iam:CreateServiceLinkedRole**: 신규 B사 account 첫 deploy 시 `AWSServiceRoleForAmazonEKS` / `AWSServiceRoleForElasticLoadBalancing` 등 자동 생성 필요. `iam:AWSServiceName` 화이트리스트로 narrow.
>
> **iam:SimulatePrincipalPolicy 제거**: 임의 principal 시뮬 가능해 정보 누출 위험. Terraform 동작에 불필요.

### 3.10 KMS

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "KMSCreateKeyOnly",
      "Effect": "Allow",
      "Action": "kms:CreateKey",
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
      }
    },
    {
      "Sid": "KMSKeyManagementArkraftTagOnly",
      "Effect": "Allow",
      "Action": [
        "kms:DescribeKey",
        "kms:ScheduleKeyDeletion",
        "kms:CancelKeyDeletion",
        "kms:PutKeyPolicy",
        "kms:GetKeyPolicy",
        "kms:EnableKeyRotation",
        "kms:DisableKeyRotation",
        "kms:GetKeyRotationStatus",
        "kms:TagResource",
        "kms:UntagResource",
        "kms:ListResourceTags"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "ap-northeast-2",
          "aws:ResourceTag/Project": "arkraft"
        }
      }
    },
    {
      "Sid": "KMSEncryptDecryptForResourceCreation",
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "kms:GenerateDataKeyWithoutPlaintext",
        "kms:ReEncryptFrom",
        "kms:ReEncryptTo"
      ],
      "Resource": "arn:aws:kms:ap-northeast-2:{ACCOUNT_ID}:key/*",
      "Condition": {
        "StringLike": { "kms:RequestAlias": "alias/arkraft/*" }
      }
    },
    {
      "Sid": "KMSAliasManagementArkraftScope",
      "Effect": "Allow",
      "Action": [
        "kms:CreateAlias",
        "kms:DeleteAlias",
        "kms:UpdateAlias",
        "kms:ListAliases"
      ],
      "Resource": [
        "arn:aws:kms:ap-northeast-2:{ACCOUNT_ID}:alias/arkraft/*",
        "arn:aws:kms:ap-northeast-2:{ACCOUNT_ID}:key/*"
      ]
    }
  ]
}
```

### 3.11 Secrets Manager

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:DeleteSecret",
        "secretsmanager:RestoreSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:GetSecretValue",
        "secretsmanager:TagResource",
        "secretsmanager:UntagResource",
        "secretsmanager:RotateSecret",
        "secretsmanager:CancelRotateSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:ap-northeast-2:{ACCOUNT_ID}:secret:ai-infra/*",
        "arn:aws:secretsmanager:ap-northeast-2:{ACCOUNT_ID}:secret:arkraft/*"
      ]
    },
    {
      "Sid": "SecretsManagerListAccountWide",
      "Effect": "Allow",
      "Action": "secretsmanager:ListSecrets",
      "Resource": "*"
    }
  ]
}
```

> **Resource: "\*" 사유 (ListSecrets)**: ListSecrets API 는 account-wide 만 — narrow 불가.

### 3.12 Route53 + ACM

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Route53HostedZoneManagement",
      "Effect": "Allow",
      "Action": [
        "route53:CreateHostedZone",
        "route53:GetHostedZone",
        "route53:UpdateHostedZoneComment",
        "route53:DeleteHostedZone",
        "route53:ChangeResourceRecordSets",
        "route53:ListResourceRecordSets",
        "route53:GetChange",
        "route53:ChangeTagsForResource",
        "route53:ListTagsForResource"
      ],
      "Resource": "arn:aws:route53:::hostedzone/*"
    },
    {
      "Sid": "Route53AccountWide",
      "Effect": "Allow",
      "Action": [
        "route53:ListHostedZones",
        "route53:ListHostedZonesByName",
        "route53:GetHostedZoneCount"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ACMCertificate",
      "Effect": "Allow",
      "Action": [
        "acm:RequestCertificate",
        "acm:DescribeCertificate",
        "acm:GetCertificate",
        "acm:DeleteCertificate",
        "acm:ListCertificates",
        "acm:AddTagsToCertificate",
        "acm:RemoveTagsFromCertificate",
        "acm:ListTagsForCertificate",
        "acm:RenewCertificate"
      ],
      "Resource": [
        "arn:aws:acm:ap-northeast-2:{ACCOUNT_ID}:certificate/*"
      ]
    }
  ]
}
```

### 3.13 ELBv2

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:CreateLoadBalancer",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeLoadBalancerAttributes",
        "elasticloadbalancing:ModifyLoadBalancerAttributes",
        "elasticloadbalancing:DeleteLoadBalancer",
        "elasticloadbalancing:CreateTargetGroup",
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetGroupAttributes",
        "elasticloadbalancing:DescribeTargetHealth",
        "elasticloadbalancing:ModifyTargetGroupAttributes",
        "elasticloadbalancing:DeleteTargetGroup",
        "elasticloadbalancing:RegisterTargets",
        "elasticloadbalancing:DeregisterTargets",
        "elasticloadbalancing:CreateListener",
        "elasticloadbalancing:DescribeListeners",
        "elasticloadbalancing:DescribeListenerAttributes",
        "elasticloadbalancing:ModifyListener",
        "elasticloadbalancing:DeleteListener",
        "elasticloadbalancing:CreateRule",
        "elasticloadbalancing:DescribeRules",
        "elasticloadbalancing:ModifyRule",
        "elasticloadbalancing:DeleteRule",
        "elasticloadbalancing:AddTags",
        "elasticloadbalancing:RemoveTags",
        "elasticloadbalancing:DescribeTags"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
      }
    }
  ]
}
```

### 3.14 AmazonMQ

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "mq:CreateBroker",
        "mq:DescribeBroker",
        "mq:UpdateBroker",
        "mq:RebootBroker",
        "mq:DeleteBroker",
        "mq:ListBrokers",
        "mq:CreateTags",
        "mq:DeleteTags",
        "mq:ListTags",
        "mq:CreateUser",
        "mq:UpdateUser",
        "mq:DeleteUser",
        "mq:DescribeUser",
        "mq:ListUsers",
        "mq:CreateConfiguration",
        "mq:UpdateConfiguration",
        "mq:DescribeConfiguration",
        "mq:DescribeConfigurationRevision",
        "mq:ListConfigurations",
        "mq:ListConfigurationRevisions"
      ],
      "Resource": "arn:aws:mq:ap-northeast-2:{ACCOUNT_ID}:*"
    }
  ]
}
```

### 3.15 CloudWatch Logs

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DescribeLogGroups",
        "logs:DeleteLogGroup",
        "logs:PutRetentionPolicy",
        "logs:DeleteRetentionPolicy",
        "logs:TagResource",
        "logs:UntagResource",
        "logs:ListTagsForResource",
        "logs:PutResourcePolicy",
        "logs:DescribeResourcePolicies"
      ],
      "Resource": "arn:aws:logs:ap-northeast-2:{ACCOUNT_ID}:log-group:*"
    }
  ]
}
```

### 3.16 SQS (Karpenter Spot Interruption Queue)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:CreateQueue",
        "sqs:GetQueueAttributes",
        "sqs:SetQueueAttributes",
        "sqs:DeleteQueue",
        "sqs:ListQueues",
        "sqs:TagQueue",
        "sqs:UntagQueue",
        "sqs:ListQueueTags"
      ],
      "Resource": "arn:aws:sqs:ap-northeast-2:{ACCOUNT_ID}:*-karpenter*"
    }
  ]
}
```

### 3.17 EventBridge (Karpenter Spot Interruption Rules)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "events:PutRule",
        "events:DescribeRule",
        "events:DeleteRule",
        "events:ListRules",
        "events:PutTargets",
        "events:RemoveTargets",
        "events:ListTargetsByRule",
        "events:TagResource",
        "events:UntagResource",
        "events:ListTagsForResource"
      ],
      "Resource": "arn:aws:events:ap-northeast-2:{ACCOUNT_ID}:rule/*-karpenter*"
    }
  ]
}
```

---

## 4. 자원별 CRUD Action 상세

> §2 매트릭스의 19개 service 각각에 대한 Create / Read / Update / Delete Action 분류. 보안팀이 stage 별 권한 부여 가능 (예: "Create 만 먼저 부여, Update/Delete 는 별도 승인").

(매트릭스 §2 와 동일 — 추후 iter 에서 sub-section 으로 expand)

---

## 5. 최소권한 narrow 가이드

### 5.1 Resource Tag Condition 권장

`aws:ResourceTag/Project: arkraft` Condition 을 모든 자원에 적용. Terraform 의 `default_tags` 가 자동으로 Project 태그 부여 → narrow 자동.

```json
"Condition": {
  "StringEquals": { "aws:ResourceTag/Project": "arkraft" }
}
```

### 5.2 Region Condition 권장

```json
"Condition": {
  "StringEquals": { "aws:RequestedRegion": "ap-northeast-2" }
}
```

### 5.3 IAM PassRole 화이트리스트

`iam:PassedToService` 로 명시적 service narrow:
- EC2 (Karpenter NodeInstanceRole)
- EKS (Cluster Role)
- RDS (Enhanced Monitoring Role)
- ElastiCache (Service Role)

### 5.4 Path Prefix Condition (IAM)

IAM Role/Policy/InstanceProfile 의 Resource ARN 을 prefix 로 narrow:
- `arn:aws:iam::{ACCOUNT_ID}:role/arkraft-*`
- `arn:aws:iam::{ACCOUNT_ID}:policy/arkraft-*`

---

## 6. Region 변경 시 영향

B사 가 `us-east-1` 또는 다른 region 사용 시:
- 모든 `aws:RequestedRegion` Condition 의 region 값 변경
- ACM Certificate region 변경 (ALB region 과 동일해야 함)
- KMS Key / S3 Bucket / RDS / ElastiCache / OpenSearch 등 region-bound 자원 모두 신규 생성

---

## 7. B사 신청 체크리스트

> 보안팀이 항목별 ack 체크 가능한 markdown checkbox.

### 7.1 PM팀 IAM Identity 부여

- [ ] PM팀 IAM Role / User / SSO Identity 생성 (B사 측 식별자)
- [ ] PM팀 Identity 에 **§3 service-별 IAM Policy 17개 attach** (또는 단일 통합 정책)
- [ ] Trust Policy: PM팀 식별자만 sts:AssumeRole 가능

### 7.2 Service 별 정책 attach

- [ ] §3.1 VPC 네트워킹
- [ ] §3.2 Security Group
- [ ] §3.3 EKS (Cluster + Add-on + Access Entry + Pod Identity)
- [ ] §3.4 EC2 (Karpenter + EBS + ENI)
- [ ] §3.5 RDS PostgreSQL
- [ ] §3.6 ElastiCache Redis
- [ ] §3.7 S3 (arkraft-* + argo-workflows-logs)
- [ ] §3.8 ECR (ark/* repository)
- [ ] §3.9 IAM (Role + Policy + InstanceProfile + OIDC Provider)
- [ ] §3.10 KMS
- [ ] §3.11 Secrets Manager
- [ ] §3.12 Route53 + ACM
- [ ] §3.13 ELBv2
- [ ] §3.14 AmazonMQ
- [ ] §3.15 CloudWatch Logs
- [ ] §3.16 SQS (Karpenter spot)
- [ ] §3.17 EventBridge (Karpenter spot)

### 7.3 (선택) Bedrock Model Access 활성화

- [ ] B사 root account 또는 organization admin 이 Bedrock Console → Model Access 에서 anthropic.claude-* 모델 활성화

### 7.4 (선택) Terraform State Backend

- [ ] B사 자체 Terraform backend 사용 시: S3 bucket + DynamoDB lock table 별도 생성 + PM팀에게 read/write 권한

---

## 8. 출처/근거

| # | 항목 | 출처 |
|---|------|------|
| 1 | aws_* resource type enumeration | `grep -rE "^resource \"aws_" /Users/wogus/Project/arkraft/ai-infra` 결과 60개 → arkraft 한정 filter 후 19개 service group |
| 2 | EKS Cluster (terraform-aws-modules) | https://github.com/terraform-aws-modules/terraform-aws-eks |
| 3 | Karpenter Pod Identity 정책 | https://karpenter.sh/v1.0/getting-started/getting-started-with-karpenter/ |
| 4 | AWS IAM Action Reference | https://docs.aws.amazon.com/service-authorization/latest/reference/reference_policies_actions-resources-contextkeys.html |
| 5 | AWS Load Balancer Controller IAM Policy | https://github.com/kubernetes-sigs/aws-load-balancer-controller/blob/main/docs/install/iam_policy.json |

---

## 변경 이력

- **iter 1 (2026-04-28)**: 초안 작성. ai-infra Terraform 자원 60개 enumerate → arkraft 한정 19개 service 매트릭스 + 17개 service 별 IAM Policy JSON. 4 sub-agent (Reviewer/QA/Security/Completeness) 검증 대기.
