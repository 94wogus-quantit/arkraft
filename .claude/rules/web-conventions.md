---
paths:
  - "arkraft-web/**"
---

# arkraft-web 컨벤션

## 명령어

```bash
pnpm dev              # 개발 서버 (포트 3000)
pnpm build            # 프로덕션 빌드
pnpm lint             # ESLint
pnpm lint:fix         # 자동 수정
pnpm format           # Prettier
pnpm generate:types   # OpenAPI -> TypeScript 타입 생성
```

## 커스텀 ESLint 규칙

| 규칙 | 목적 |
|------|------|
| `no-direct-infra-import` | 레이어 경계 강제 |
| `no-use-client-in-server-folder` | RSC 패턴 강제 |
| `prefer-react-compiler` | `useMemo`/`useCallback` 사용 금지 |
| `no-console-in-production` | console.log 금지 |
| `no-server-env-in-client` | 환경변수 유출 방지 |
| `no-direct-process-env` | `@infra/config/env` 사용 강제 |

## 경로 별칭

```typescript
import { apiRequest } from '@infra/api';
import { Button } from '@shared/components';
import { useAuth } from '@domains/auth';
```

## 컴포넌트 패턴

```typescript
// 서버 컴포넌트 (app/ 기본)
export default async function Page() {
  const data = await fetchData();
  return <ClientComponent data={data} />;
}

// 클라이언트 컴포넌트
'use client';
export function ClientComponent({ data }: Props) { ... }
```

## API 사용법

```typescript
// 올바름
import { apiRequest } from '@infra/api';
const data = await apiRequest<ResponseType>('/endpoint');

// 잘못됨 — raw fetch 금지
const data = await fetch('/api/endpoint');
```

## 환경 변수

```typescript
// 올바름
import { env } from '@infra/config/env';
const apiUrl = env.INTERNAL_API_URL;

// 잘못됨
const apiUrl = process.env.INTERNAL_API_URL;
```

## 도메인 기능 구조

```
domains/{feature}/
├── types/
├── server/
│   ├── components/    # RSC
│   ├── actions/       # Server Actions
│   └── services/
├── client/
│   ├── components/    # 'use client'
│   └── hooks/
└── index.ts           # 공개 API
```

## 파일 네이밍

| 유형 | 규칙 | 예시 |
|------|------|------|
| 컴포넌트 | PascalCase | `UserProfile.tsx` |
| 훅 | camelCase + `use` | `useAuth.ts` |
| 유틸 | camelCase | `formatDate.ts` |
| 페이지 | `page.tsx` | `app/(protected)/home/page.tsx` |
