---
paths:
  - "ai-infra/**"
  - "arkraft-deploy/**"
  - "alpha-pool-infra/**"
  - "quanda_infra/**"
---

# 인프라 컨벤션

## ai-infra (Terraform + Atlantis)

### 명령어 (로컬에서 안전한 것만)

```bash
make fmt              # terraform fmt
make validate         # terraform validate
make output           # terraform output
make state-list       # 상태 리소스 목록
```

**`make plan`, `make apply`, `make destroy`는 로컬에서 실행 절대 금지.** PR + Atlantis만 사용.

### 워크플로우

1. 브랜치 생성 → 코드 수정 → `make fmt && make validate`
2. PR 생성 → 푸시 시 `atlantis plan` 자동 실행
3. 코드 리뷰 → PR 코멘트로 `atlantis apply`
4. 적용 완료 → `/record` → 사용자 승인 후 머지

### kubectl

```bash
# 항상 eks-access 프로파일 사용
AWS_PROFILE=eks-access kubectl get pods -A
```

### Terraform 규칙

- 변수 값은 `config/terraform.tfvars`에 정의
- EC2 인스턴스 타입: 최소 medium (nano, small 금지)
- K8s 매니페스트: `templatefile()` + `.yaml.tpl` 사용 (인라인 yaml_body 금지)
- `default_tags`에 이미 있는 태그를 개별 리소스에 중복 추가하지 말 것
- 새 모듈은 `aws/` 하위 디렉토리에 추가

## arkraft-deploy (Helm)

```bash
make template                    # 템플릿 렌더링
make update-web version=X       # 이미지 태그 업데이트
make update-api version=X
make update-agent agent=X version=Y
```

### 네임스페이스 구성

- `arkraft`: API, Web
- `arkraft-sandbox`: AI 에이전트 파드 (ResourceQuota: 10 파드, 20 CPU, 40Gi)

### Agent 샌드박스

- 에이전트 종류: `insight`, `alpha`, `portfolio`, `ops`
- 각 파드: `claude-agent` + `jupyter-mcp` 컨테이너
- 인증 우선순위: `claude.oauthToken` → AWS Bedrock
