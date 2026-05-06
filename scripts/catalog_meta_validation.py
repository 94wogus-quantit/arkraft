#!/usr/bin/env python3
"""Catalog metadata validation — dry-run capable read-only sanity sweep.

자세한 PLAN: ../CATALOG_META_VALIDATION_PLAN.md

사용 예:
    # 코드 경로만 검증 (네트워크 미접근, 5초)
    python3 scripts/catalog_meta_validation.py --dry-run --universe kr_stock --category capital --limit 1

    # 한 카테고리 sample 1
    python3 scripts/catalog_meta_validation.py --universe kr_stock --category capital --limit 1 --output table

    # Tier A 전체 자동 (병렬 4)
    python3 scripts/catalog_meta_validation.py --tier A --parallel 4 --output json > validation-tier-a.json

    # 보고서 집계
    python3 scripts/catalog_meta_validation.py --report validation-tier-a.json validation-tier-b.json --output table

환경변수:
    ARKRAFT_VALIDATE_PG_DSN   staging RDS DSN (connect-remote 후 localhost tunnel)
    ARKRAFT_VALIDATE_S3_BUCKET   default 'arkraft-staging'
    AWS_PROFILE               SSO profile

read-only 보장:
    - SELECT / GetObject / HeadObject 만 호출.
    - INSERT/UPDATE/DELETE/PUT/DELETE 코드 패턴 없음.
    - --dry-run 분기는 boto3/sqlalchemy import 자체 안 함.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

# 19개 화이트리스트 universe×category 그룹 (260430_production_public.xlsx Summary R12-R42 노란색)
WHITELIST_GROUPS: list[tuple[str, str]] = [
    ("kr_stock", "capital"),
    ("kr_stock", "cax"),
    ("kr_stock", "company"),
    ("kr_stock", "consensus"),
    ("kr_stock", "credit"),
    ("kr_stock", "descriptor"),
    ("kr_stock", "economy"),
    ("kr_stock", "factor"),
    ("kr_stock", "financial"),
    ("kr_stock", "investor_activity"),
    ("kr_stock", "price_volume"),
    ("kr_stock", "status"),
    ("kr_stock", "theme"),
    ("us_stock", "cax"),
    ("us_stock", "classification"),
    ("us_stock", "economy"),
    ("us_stock", "factor"),
    ("us_stock", "financial"),
    ("us_stock", "price_volume"),
]

# spec enums
ADJUSTMENT_STATUS_ENUM = {"unadjusted", "split_only", "split_dividend", "pre_adjusted"}
DTYPE_ENUM = {"float32", "float64", "int64"}
FREQUENCY_ENUM = {"daily", "weekly", "monthly"}
FILL_METHOD_ENUM = {"ffill", "bfill", "none"}

# delivery_lag 정규식 — P1BD / P1W / 0 / null 모두 fail
DELIVERY_LAG_RE = re.compile(r"^P\d+D$")

# identity_name 정규식 — 정확히 하나의 . 이고 prefix 중복 금지
IDENTITY_NAME_RE = re.compile(r"^[a-z][a-z_]*\.[a-z0-9][a-z0-9_-]*$")


@dataclass
class CheckResult:
    """검증 한 entry 의 결과."""
    identity_name: str
    universe: str
    category: str
    check_name: str
    passed: bool
    priority: str  # "P0" | "P1" | "P2"
    detail: str = ""
    extras: dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────
# Pure validation functions — module-level, no I/O
# ────────────────────────────────────────────────────────────────────


def check_identity_name(identity_name: str, universe: str) -> tuple[bool, str]:
    """`identity_name` 형식 검증. prefix 중복 (kr_stock.kr_stock-*) 도 잡음."""
    if not identity_name:
        return False, "identity_name is NULL/empty"
    if not IDENTITY_NAME_RE.match(identity_name):
        return False, f"identity_name {identity_name!r} doesn't match ^[a-z_]+\\.[a-z0-9_-]+$"
    parts = identity_name.split(".", 1)
    if len(parts) != 2:
        return False, f"identity_name must contain exactly one '.': {identity_name!r}"
    prefix, name = parts
    if prefix != universe:
        return False, f"identity_name prefix {prefix!r} != universe {universe!r}"
    if name.startswith(f"{universe}-") or name.startswith(f"{universe}_"):
        return False, f"identity_name name part {name!r} starts with universe prefix again (duplication)"
    return True, "ok"


def check_description_quality(description: str | None) -> tuple[bool, str]:
    """`description` 1줄 영문 + 비어있지 않음 + ≥ 8 단어."""
    if not description:
        return False, "description is NULL/empty"
    if "\n" in description or "\r" in description:
        return False, "description contains newline (must be 1-line)"
    ascii_chars = sum(1 for c in description if ord(c) < 128)
    if ascii_chars / max(len(description), 1) < 0.7:
        return False, "description ascii ratio < 70% (likely non-English)"
    if len(description.split()) < 8:
        return False, f"description too short ({len(description.split())} words < 8)"
    return True, "ok"


def check_delivery_lag(pit: dict[str, Any] | None) -> tuple[bool, str]:
    """`pit.delivery_lag` 가 ^P\\d+D$ 정규식 일치 — P1BD 같은 Business 표기 reject."""
    if not pit:
        return False, "pit JSONB is NULL"
    lag = pit.get("delivery_lag")
    if lag is None or lag == 0 or lag == "":
        return False, f"delivery_lag is {lag!r} — look-ahead bias risk"
    if not isinstance(lag, str):
        return False, f"delivery_lag must be string (ISO 8601 P{{n}}D), got {type(lag).__name__}"
    if not DELIVERY_LAG_RE.match(lag):
        return False, f"delivery_lag {lag!r} doesn't match ^P\\d+D$ (P1BD-style Business notation forbidden)"
    return True, "ok"


def check_unit(unit: str | None) -> tuple[bool, str]:
    """`unit` 가 NULL/empty 면 fail."""
    if unit is None or unit.strip() == "":
        return False, "unit is NULL/empty — agent cannot interpret values"
    return True, "ok"


def check_dtype_enum(dtype: str | None) -> tuple[bool, str]:
    """catalog row `dtype` 가 enum 안에 있는지 (parquet storage dtype 비교는 별도)."""
    if dtype not in DTYPE_ENUM:
        return False, f"dtype {dtype!r} not in {sorted(DTYPE_ENUM)}"
    return True, "ok"


def check_frequency_enum(frequency: str | None) -> tuple[bool, str]:
    if frequency not in FREQUENCY_ENUM:
        return False, f"frequency {frequency!r} not in {sorted(FREQUENCY_ENUM)}"
    return True, "ok"


def check_fill_method_enum(fill_method: str | None) -> tuple[bool, str]:
    if fill_method not in FILL_METHOD_ENUM:
        return False, f"fill_method {fill_method!r} not in {sorted(FILL_METHOD_ENUM)}"
    return True, "ok"


def check_axes_entity_id_type(axes_entity: dict[str, Any] | None) -> tuple[bool, str]:
    if not axes_entity:
        return False, "axes_entity JSONB is NULL"
    if axes_entity.get("id_type") != "finter_id":
        return False, f"axes_entity.id_type {axes_entity.get('id_type')!r} != 'finter_id'"
    return True, "ok"


def check_lineage_must(lineage: dict[str, Any] | None) -> tuple[bool, str]:
    """`lineage.{source_type, source_vendor, methodology, finter_content_model}` MUST."""
    if not lineage:
        return False, "lineage JSONB is NULL"
    must = ["source_type", "source_vendor", "methodology", "finter_content_model"]
    missing = [k for k in must if not lineage.get(k)]
    if missing:
        return False, f"lineage missing MUST keys: {missing}"
    return True, "ok"


def check_parquet_metadata_must_keys(metadata: dict[bytes, bytes] | dict[str, str] | None) -> tuple[bool, str]:
    """parquet schema.metadata 4 MUST 키."""
    if not metadata:
        return False, "parquet schema.metadata is empty"
    md = {k if isinstance(k, bytes) else k.encode(): v for k, v in metadata.items()}
    must_keys = [b"identity_name", b"universe", b"category", b"adjustment"]
    missing = [k for k in must_keys if k not in md]
    if missing:
        return False, f"parquet meta missing MUST keys: {[k.decode() for k in missing]}"
    return True, "ok"


def check_parquet_adjustment_status(metadata: dict[bytes, bytes] | dict[str, str] | None) -> tuple[bool, str]:
    """parquet meta `adjustment.status` enum."""
    if not metadata:
        return False, "parquet schema.metadata is empty"
    md = {k if isinstance(k, bytes) else k.encode(): v for k, v in metadata.items()}
    raw = md.get(b"adjustment")
    if raw is None:
        return False, "parquet meta missing 'adjustment'"
    try:
        adj = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        return False, f"parquet meta 'adjustment' not valid JSON: {e}"
    status = adj.get("status")
    if status not in ADJUSTMENT_STATUS_ENUM:
        return False, f"adjustment.status {status!r} not in {sorted(ADJUSTMENT_STATUS_ENUM)}"
    return True, "ok"


def check_value_serialization(values_dtype_kind: str | None, first_cell: Any) -> tuple[bool, str]:
    """parquet body values 가 pickle bytes 가 아니어야 함.

    values_dtype_kind: pandas series dtype.kind (보통 'f' 가 정상, 'O' 가 의심)
    first_cell: 첫 row 값 — bytes / str 이고 b'\\x80\\x03' 시작이면 pickle.
    """
    if values_dtype_kind == "f":
        return True, "ok"
    if values_dtype_kind in {"i", "u"}:
        return True, "ok"
    if isinstance(first_cell, (bytes, bytearray)):
        if first_cell.startswith(b"\x80"):
            return False, "values column is pickle bytes (5/4 incident pattern)"
        return False, f"values column is bytes (len={len(first_cell)})"
    return False, f"values dtype.kind={values_dtype_kind!r} first_cell type={type(first_cell).__name__}"


def check_dtype_match(catalog_dtype: str, parquet_physical_type: str) -> tuple[bool, str]:
    expect_map = {
        "float32": ("FLOAT",),
        "float64": ("DOUBLE",),
        "int64": ("INT64",),
    }
    expects = expect_map.get(catalog_dtype)
    if expects is None:
        return False, f"unknown catalog.dtype {catalog_dtype!r}"
    if parquet_physical_type in expects:
        return True, "ok"
    return False, (
        f"catalog.dtype={catalog_dtype!r} expects {expects} but parquet physical_type={parquet_physical_type!r}"
    )


# ────────────────────────────────────────────────────────────────────
# Reporters
# ────────────────────────────────────────────────────────────────────


def render_table(results: list[CheckResult]) -> str:
    if not results:
        return "(no results)"
    lines = []
    header = f"{'identity_name':<40} {'check':<32} {'P':<3} {'pass':<4} {'detail'}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in results:
        status = "OK" if r.passed else "FAIL"
        lines.append(
            f"{r.identity_name[:40]:<40} {r.check_name[:32]:<32} {r.priority:<3} {status:<4} {r.detail[:60]}"
        )
    fail_n = sum(1 for r in results if not r.passed)
    pass_n = len(results) - fail_n
    by_p = {}
    for r in results:
        if not r.passed:
            by_p[r.priority] = by_p.get(r.priority, 0) + 1
    lines.append("-" * len(header))
    p_summary = ", ".join(f"{p}={n}" for p, n in sorted(by_p.items())) if by_p else "-"
    lines.append(f"summary: {pass_n} pass / {fail_n} fail (by priority: {p_summary})")
    return "\n".join(lines)


def render_json(results: list[CheckResult]) -> str:
    return json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2)


# ────────────────────────────────────────────────────────────────────
# Connection bootstrappers (NOT called in --dry-run)
# ────────────────────────────────────────────────────────────────────


def get_pg_engine() -> Any:
    """SQLAlchemy engine for staging RDS via connect-remote tunnel.

    DSN template:
        postgresql+psycopg2://arkraft:****@127.0.0.1:55432/arkraft

    실 자격증명은 환경변수 ARKRAFT_VALIDATE_PG_DSN 에서 읽음. hardcode 금지.
    """
    from sqlalchemy import create_engine  # local import — dry-run 에서 import 자체 안 함

    dsn = os.environ.get("ARKRAFT_VALIDATE_PG_DSN")
    if not dsn:
        raise RuntimeError(
            "ARKRAFT_VALIDATE_PG_DSN env not set. "
            "Run connect-remote and export DSN. See PLAN section 2."
        )
    return create_engine(dsn, pool_pre_ping=True, future=True)


def get_s3_client() -> Any:
    import boto3  # local import — dry-run 에서 import 자체 안 함

    region = os.environ.get("AWS_REGION", "ap-northeast-2")
    return boto3.client("s3", region_name=region)


def get_bucket() -> str:
    return os.environ.get("ARKRAFT_VALIDATE_S3_BUCKET", "arkraft-staging")


# ────────────────────────────────────────────────────────────────────
# Entry-level orchestration (real-run)
# ────────────────────────────────────────────────────────────────────


def fetch_catalog_rows(engine: Any, universe: str, category: str, limit: int) -> list[dict[str, Any]]:
    """SELECT only — read-only."""
    from sqlalchemy import text  # local

    sql = text(
        """
        SELECT identity_name, name, universe, category, description, frequency, dtype,
               unit, fill_method, axes_time, axes_entity, pit, lineage,
               production_state
        FROM catalogs
        WHERE universe = :u AND category = :c
        ORDER BY identity_name
        LIMIT :n
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"u": universe, "c": category, "n": limit}).mappings().all()
    return [dict(r) for r in rows]


def resolve_parquet_key(s3: Any, bucket: str, identity_name: str) -> str | None:
    """`teams/{system_team_id}/catalogs/<identity_name>/data.parquet` key 를 찾는다.

    우선 ARKRAFT_SYSTEM_TEAM_ID env 로 직접 지정. 없으면 ListObjectsV2 로 prefix 검색.
    read-only — ListObjects 만 호출.
    """
    sid = os.environ.get("ARKRAFT_SYSTEM_TEAM_ID")
    if sid:
        return f"teams/{sid}/catalogs/{identity_name}/data.parquet"

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="teams/"):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.endswith(f"/catalogs/{identity_name}/data.parquet"):
                return k
    return None


def head_parquet(s3: Any, bucket: str, identity_name: str) -> tuple[bool, str, str | None]:
    """HeadObject — read-only sanity check on parquet existence. Returns (ok, msg, key)."""
    key = resolve_parquet_key(s3, bucket, identity_name)
    if not key:
        return False, f"parquet key not found for identity {identity_name!r}", None
    try:
        resp = s3.head_object(Bucket=bucket, Key=key)
        return True, f"parquet exists size={resp.get('ContentLength', 0)}B", key
    except Exception as e:  # noqa: BLE001 — read-only error surface
        return False, f"head_object failed: {e}", key


def read_parquet_schema(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    """GetObject + pyarrow.read_schema — read-only."""
    import io

    import pyarrow.parquet as pq  # local

    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    schema = pq.read_schema(io.BytesIO(body))
    physical_types: dict[str, str] = {}
    parquet_meta = pq.ParquetFile(io.BytesIO(body)).metadata
    for i in range(parquet_meta.num_columns):
        col = parquet_meta.schema.column(i)
        physical_types[col.name] = col.physical_type
    return {
        "metadata": dict(schema.metadata or {}),
        "fields": [(f.name, str(f.type)) for f in schema],
        "physical_types": physical_types,
        "raw_body": body,
    }


def read_parquet_body_sample(raw_body: bytes, n_rows: int = 30) -> dict[str, Any]:
    """parquet body 의 첫 N row 만 읽어 dtype / index / first cell 확인."""
    import io

    import pandas as pd  # local
    import pyarrow.parquet as pq  # local

    table = pq.read_table(io.BytesIO(raw_body))
    df = table.to_pandas()
    head = df.head(n_rows)
    first_cell = head.iloc[0, 0] if not head.empty else None
    values_dtype_kind = str(head.dtypes.iloc[0].kind) if not head.empty else None
    return {
        "row_count": len(df),
        "col_count": len(df.columns),
        "values_dtype_kind": values_dtype_kind,
        "first_cell": first_cell,
        "index_is_datetime": isinstance(df.index, pd.DatetimeIndex),
        "index_monotonic": bool(df.index.is_monotonic_increasing) if len(df) > 1 else True,
    }


def make_result_appender(
    results: list[CheckResult], identity_name: str, universe: str, category: str
):
    """Module-level helper — 중복 closure 패턴 통합 (validate_one_row + run_real + run_real_usage 공유)."""
    def add(
        check: str, ok: bool, detail: str, priority: str,
        extras: dict[str, Any] | None = None,
    ) -> None:
        results.append(
            CheckResult(
                identity_name=identity_name,
                universe=universe,
                category=category,
                check_name=check,
                passed=ok,
                priority=priority,
                detail=detail,
                extras=extras or {},
            )
        )
    return add


def validate_one_row(row: dict[str, Any]) -> list[CheckResult]:
    """DB row 단독으로 검증 가능한 항목들."""
    out: list[CheckResult] = []
    iname = row["identity_name"]
    universe = row["universe"]
    category = row["category"]
    add = make_result_appender(out, iname, universe, category)

    ok, msg = check_identity_name(iname, universe)
    add("identity_name_format", ok, msg, "P1")

    ok, msg = check_description_quality(row.get("description"))
    add("description_quality", ok, msg, "P0")

    ok, msg = check_unit(row.get("unit"))
    add("unit_present", ok, msg, "P1")

    ok, msg = check_dtype_enum(row.get("dtype"))
    add("dtype_enum", ok, msg, "P0")

    ok, msg = check_frequency_enum(row.get("frequency"))
    add("frequency_enum", ok, msg, "P2")

    ok, msg = check_fill_method_enum(row.get("fill_method"))
    add("fill_method_enum", ok, msg, "P1")

    ok, msg = check_delivery_lag(row.get("pit"))
    add("delivery_lag", ok, msg, "P0")

    ok, msg = check_axes_entity_id_type(row.get("axes_entity"))
    add("axes_entity_id_type", ok, msg, "P1")

    ok, msg = check_lineage_must(row.get("lineage"))
    add("lineage_must_keys", ok, msg, "P1")

    return out


# ────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Catalog 메타데이터 검증 (read-only). PLAN: CATALOG_META_VALIDATION_PLAN.md"
    )
    p.add_argument("--dry-run", action="store_true", help="staging 미접근 — 코드 경로만 검증")
    p.add_argument("--universe", default=None, help="검증 universe (e.g. kr_stock)")
    p.add_argument("--category", default=None, help="검증 category (e.g. capital)")
    p.add_argument("--limit", type=int, default=10, help="entry 수 상한")
    p.add_argument("--tier", choices=["A", "B"], default=None, help="A=전 자동, B=그룹당 sample")
    p.add_argument("--parallel", type=int, default=1, help="parallel worker (Tier A 만 의미)")
    p.add_argument("--output", choices=["table", "json"], default="table")
    p.add_argument("--report", nargs="*", help="기존 결과 JSON 들을 집계")
    p.add_argument(
        "--frame",
        choices=["presence", "usage"],
        default="presence",
        help="presence=anatomy spec MUST 13 (이전 frame); usage=agent SDK 가 실제 read 하는 필드만 (AGENT_USAGE_VALIDATION_REPORT.md 참조)",
    )
    return p.parse_args(argv)


def run_dry_run(args: argparse.Namespace) -> int:
    """dry_run=True — boto3/sqlalchemy import 자체 안 함, network call X."""
    print(f"[DRY-RUN] dry_run=True frame={args.frame} universe={args.universe} category={args.category} limit={args.limit}")
    print(
        f"[DRY-RUN] would query catalogs WHERE universe={args.universe!r} "
        f"AND category={args.category!r} LIMIT {args.limit}"
    )
    print("[DRY-RUN] would HEAD s3://arkraft-staging/teams/{system_team_id}/catalogs/<identity_name>/data.parquet")
    if args.frame == "usage":
        print(
            "[DRY-RUN] check plan (usage): loader_smoke, delivery_lag_present, "
            "description_distinct, name_resolves, adjustment_status_known"
        )
    else:
        print(
            "[DRY-RUN] check plan (presence): schema_must_fields, value_serialization, "
            "dtype_match, freq_match, missing_outliers"
        )
    print(f"[DRY-RUN] whitelist groups loaded: {len(WHITELIST_GROUPS)}")
    print("DRY-RUN OK — no network calls performed")
    return 0


# ────────────────────────────────────────────────────────────────────
# Usage frame — agent SDK 실 사용 기반 5종 check
# (AGENT_USAGE_VALIDATION_REPORT.md §7 참조)
# ────────────────────────────────────────────────────────────────────


def usage_check_loader_smoke(values_dtype_kind: str | None, first_cell: Any, has_dt_idx: bool, row_n: int) -> tuple[bool, str]:
    """SDK loader smoke — pickle bytes / object dtype / DatetimeIndex 검증."""
    if row_n == 0:
        return False, "empty parquet"
    if not has_dt_idx:
        return False, "index is not DatetimeIndex — SDK apply_delivery_lag will fail"
    if isinstance(first_cell, (bytes, bytearray)) and first_cell[:1] == b"\x80":
        return False, "values column is pickle bytes (SDK loader can't compute on bytes)"
    if values_dtype_kind not in ("f", "i", "u"):
        return False, f"values dtype.kind={values_dtype_kind!r} (not numeric — SDK math fails)"
    return True, "ok"


def usage_check_delivery_lag_present(pit: dict[str, Any] | None) -> tuple[bool, str]:
    """SDK ValueError 차단 — DeliveryLag.is_zero == False 강제 (P1BD/PT16H 등 모두 valid)."""
    if not pit:
        return False, "pit JSONB is NULL — SDK CatalogFactory raises ValueError"
    lag = pit.get("delivery_lag")
    if lag is None or lag == 0 or lag == "":
        return False, f"delivery_lag={lag!r} → DeliveryLag.is_zero → SDK ValueError"
    # ISO 8601 valid 모든 형식 OK (P1D / P1BD / PT16H / etc) — DeliveryLag.parse() 가 처리
    return True, f"delivery_lag={lag!r} (SDK loader OK)"


def usage_check_description_distinct(description: str | None, group_descriptions: list[str]) -> tuple[bool, str]:
    """그룹 내 description 중복 — Catalog.browse() 결과에서 LLM 이 wrong selection 위험."""
    if not description:
        return False, "description empty/NULL — agent prompt 에서 의미 파악 불가"
    same = sum(1 for d in group_descriptions if (d or "").strip().lower() == description.strip().lower())
    if same > 1:
        return False, f"description 그룹 내 중복 {same}건 — agent wrong selection risk"
    return True, "ok"


def usage_check_name_resolves(name: str | None, identity_name: str | None) -> tuple[bool, str]:
    """SDK `_resolve_entry()` lowercase exact match — name 이 identity_name 의 . 뒤와 일치."""
    if not identity_name or not name:
        return False, "name or identity_name NULL"
    parts = identity_name.split(".", 1)
    if len(parts) != 2:
        return False, f"identity_name {identity_name!r} not <universe>.<name> form"
    if parts[1].lower() != name.lower():
        return False, f"name={name!r} mismatch identity_name suffix={parts[1]!r}"
    return True, "ok"


def usage_check_adjustment_status_known(parquet_metadata: dict[bytes, bytes] | dict[str, str] | None) -> tuple[bool, str]:
    """parquet custom_metadata.adjustment.status 가 알려진 enum 안 (display only — Catalog.inspect)."""
    if not parquet_metadata:
        return False, "parquet metadata empty — Catalog.inspect display 누락"
    md = {k if isinstance(k, bytes) else k.encode(): v for k, v in parquet_metadata.items()}
    raw = md.get(b"adjustment")
    if raw is None:
        return False, "adjustment key absent — Catalog.inspect 가 'unknown' 표시"
    try:
        adj = json.loads(raw)
        status = adj.get("status")
    except (json.JSONDecodeError, TypeError):
        return False, f"adjustment not JSON parseable: {raw!r}"
    if status not in ADJUSTMENT_STATUS_ENUM:
        return False, f"adjustment.status {status!r} not in {sorted(ADJUSTMENT_STATUS_ENUM)}"
    return True, "ok"


def run_report(paths: list[str], output: str) -> int:
    """기존 JSON 결과들을 집계 — read-only."""
    all_results: list[CheckResult] = []
    for p in paths:
        with open(p) as f:
            data = json.load(f)
        for d in data:
            all_results.append(CheckResult(**d))
    if output == "table":
        print(render_table(all_results))
    else:
        print(render_json(all_results))
    fail_n = sum(1 for r in all_results if not r.passed)
    return 1 if fail_n else 0


def run_real(args: argparse.Namespace) -> int:
    """실 staging 접근 — read-only."""
    if args.tier == "A":
        groups = WHITELIST_GROUPS
        per_limit = 9999
    elif args.tier == "B":
        groups = WHITELIST_GROUPS
        per_limit = 2
    elif args.universe and args.category:
        groups = [(args.universe, args.category)]
        per_limit = args.limit
    else:
        print("ERROR: provide --universe/--category, or --tier A/B, or --dry-run", file=sys.stderr)
        return 2

    engine = get_pg_engine()
    s3 = get_s3_client()
    bucket = get_bucket()

    all_results: list[CheckResult] = []
    for u, c in groups:
        rows = fetch_catalog_rows(engine, u, c, per_limit)
        for row in rows:
            all_results.extend(validate_one_row(row))
            add = make_result_appender(all_results, row["identity_name"], row["universe"], row["category"])

            # parquet check pipeline — read-only
            ok, msg, parquet_key = head_parquet(s3, bucket, row["identity_name"])
            add("parquet_reachable", ok, msg, "P2")
            if not ok or not parquet_key:
                continue

            try:
                schema_info = read_parquet_schema(s3, bucket, parquet_key)
            except Exception as e:  # noqa: BLE001
                add("parquet_schema_read", False, f"read_schema failed: {e}", "P0")
                continue

            md = schema_info["metadata"]
            phys = schema_info["physical_types"]

            ok_m, msg_m = check_parquet_metadata_must_keys(md)
            add("parquet_meta_must_keys", ok_m, msg_m, "P0")

            ok_a, msg_a = check_parquet_adjustment_status(md)
            add("parquet_adjustment_status", ok_a, msg_a, "P1")

            # body sample 읽어서 value 직렬화 + dtype match 검증
            try:
                body_info = read_parquet_body_sample(schema_info["raw_body"])
            except Exception as e:  # noqa: BLE001
                add(
                    "parquet_body_read", False,
                    f"read_table failed (likely pickle bytes): {e}",
                    "P0", extras={"physical_types": phys},
                )
                continue

            ok_v, msg_v = check_value_serialization(
                body_info["values_dtype_kind"], body_info["first_cell"]
            )
            add("value_serialization", ok_v, msg_v, "P0")

            # 첫 컬럼의 physical_type 으로 dtype match — heuristic (모든 컬럼이 같다 가정)
            first_phys = next(iter(phys.values()), None) if phys else None
            if first_phys:
                ok_d, msg_d = check_dtype_match(row.get("dtype", ""), first_phys)
                add(
                    "dtype_match", ok_d, msg_d, "P0",
                    extras={"parquet_physical_type": first_phys, "catalog_dtype": row.get("dtype")},
                )

            add(
                "index_datetime",
                bool(body_info["index_is_datetime"]) and bool(body_info["index_monotonic"]),
                f"index_is_datetime={body_info['index_is_datetime']} "
                f"monotonic={body_info['index_monotonic']}",
                "P2",
            )

    if args.output == "table":
        print(render_table(all_results))
    else:
        print(render_json(all_results))

    print(
        "\nESSENTIAL ID 변경 발생 시 SDK 전체 수정 필요 — identity_name 가 SDK 하드코딩 ID 와 충돌하는지 "
        "PLAN section 3.5 risk #6/#7 수동 검토 필요.",
        file=sys.stderr,
    )

    fail_n = sum(1 for r in all_results if not r.passed)
    return 1 if fail_n else 0


def run_real_usage(args: argparse.Namespace) -> int:
    """Usage frame — agent SDK 가 실 read 하는 5종 check 만 (AGENT_USAGE_VALIDATION_REPORT.md §7)."""
    if args.tier == "A":
        groups = WHITELIST_GROUPS
        per_limit = 9999
    elif args.tier == "B":
        groups = WHITELIST_GROUPS
        per_limit = 2
    elif args.universe and args.category:
        groups = [(args.universe, args.category)]
        per_limit = args.limit
    else:
        print("ERROR: provide --universe/--category, or --tier A/B, or --dry-run", file=sys.stderr)
        return 2

    engine = get_pg_engine()
    s3 = get_s3_client()
    bucket = get_bucket()

    all_results: list[CheckResult] = []
    for u, c in groups:
        # group-level descriptions for distinguishability — fetch_catalog_rows 재활용
        # (raw SQL 우회 제거 — 동일 테이블 접근은 fetch_catalog_rows SSOT 통과)
        all_in_group = fetch_catalog_rows(engine, u, c, 9999)
        group_descs = [(r.get("description") or "") for r in all_in_group]

        # sample rows: per_limit 수만큼 (Tier B 면 첫 2개)
        rows = all_in_group[:per_limit] if per_limit < len(all_in_group) else all_in_group
        for row in rows:
            ident = row["identity_name"]
            add = make_result_appender(all_results, ident, u, c)

            # name_resolves (P1)
            ok, msg = usage_check_name_resolves(row.get("name"), ident)
            add("usage_name_resolves", ok, msg, "P1")

            # delivery_lag_present (P0)
            ok, msg = usage_check_delivery_lag_present(row.get("pit"))
            add("usage_delivery_lag_present", ok, msg, "P0")

            # description_distinct (P1)
            ok, msg = usage_check_description_distinct(row.get("description"), group_descs)
            add("usage_description_distinct", ok, msg, "P1")

            # parquet load → loader_smoke + adjustment_status_known
            ok_p, msg_p, key = head_parquet(s3, bucket, ident)
            if not ok_p or not key:
                add("usage_loader_smoke", False, f"S3 unreachable: {msg_p}", "P0")
                add("usage_adjustment_status_known", False, "skipped (S3 unreachable)", "P2")
                continue

            try:
                schema_info = read_parquet_schema(s3, bucket, key)
                body_info = read_parquet_body_sample(schema_info["raw_body"])
            except Exception as e:  # noqa: BLE001 — read-only error surface
                add("usage_loader_smoke", False, f"parquet read failed: {type(e).__name__}: {e}"[:200], "P0")
                add("usage_adjustment_status_known", False, "skipped (parquet read failed)", "P2")
                continue

            ok, msg = usage_check_loader_smoke(
                body_info["values_dtype_kind"], body_info["first_cell"],
                body_info["index_is_datetime"], body_info["row_count"],
            )
            add("usage_loader_smoke", ok, msg, "P0")

            ok, msg = usage_check_adjustment_status_known(schema_info["metadata"])
            add("usage_adjustment_status_known", ok, msg, "P2")

    if args.output == "table":
        print(render_table(all_results))
    else:
        print(render_json(all_results))

    fail_n = sum(1 for r in all_results if not r.passed)
    return 1 if fail_n else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.report:
        return run_report(args.report, args.output)

    if args.dry_run:
        return run_dry_run(args)

    if args.frame == "usage":
        return run_real_usage(args)

    return run_real(args)


if __name__ == "__main__":
    sys.exit(main())
