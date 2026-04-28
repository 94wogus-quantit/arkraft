# create-test-datasource

Spins up a temporary PostgreSQL container on the `arkraft` network for local development,
and registers it as a data source via the arkraft API.

> **Temporary skill**: For ARK-1149 testing purposes. Validates the external DB data source registration flow.

---

## Constants

| Item | Value |
|------|-------|
| Container name | `arkraft-test-db` |
| Network | `arkraft` (same as arkraft-api) |
| DB user/pass | `testuser / testpass` |
| DB name | `test_data` |
| Internal host (API → container) | `arkraft-test-db:5432` |
| API base URL | `http://localhost:3002` |

---

## Step 1. Verify team_id

```bash
docker exec arkraft-api-postgres-1 psql -U arkraft -d arkraft -c "SELECT id FROM teams WHERE name = 'quantit' LIMIT 1;"
```

Save the output UUID as `TEAM_ID`.

---

## Step 2. Start Temporary DB Container

Remove any existing container with the same name first.

```bash
docker rm -f arkraft-test-db 2>/dev/null || true

docker run -d \
  --name arkraft-test-db \
  --network arkraft \
  -e POSTGRES_USER=testuser \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=test_data \
  postgres:17-alpine
```

Wait until the container is fully ready:

```bash
for i in $(seq 1 20); do
  docker exec arkraft-test-db pg_isready -U testuser -d test_data && break
  sleep 1
done
```

---

## Step 3. Seed Sample Tables + Data

```bash
docker exec arkraft-test-db psql -U testuser -d test_data -c "
CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(12,4),
    high NUMERIC(12,4),
    low NUMERIC(12,4),
    close NUMERIC(12,4),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO stock_prices (ticker, date, open, high, low, close, volume) VALUES
    ('005930', '2024-01-02', 74000, 75200, 73800, 74800, 12500000),
    ('005930', '2024-01-03', 74800, 76000, 74500, 75600, 11800000),
    ('005930', '2024-01-04', 75600, 75800, 74200, 74400, 9200000),
    ('000660', '2024-01-02', 138000, 141000, 137500, 140000, 3200000),
    ('000660', '2024-01-03', 140000, 143000, 139500, 142500, 2900000),
    ('000660', '2024-01-04', 142500, 143500, 140000, 141000, 2700000);

CREATE TABLE IF NOT EXISTS company_info (
    ticker VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    sector VARCHAR(50),
    market_cap BIGINT,
    listed_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO company_info (ticker, name, sector, market_cap, listed_date) VALUES
    ('005930', '삼성전자', 'Technology', 450000000000000, '1975-06-11'),
    ('000660', 'SK하이닉스', 'Technology', 110000000000000, '1996-12-26');
"
```

---

## Step 4. Register Data Source via API

Since `AUTH_ENABLED=false`, calls can be made with only the `X-Team-Id` header (no JWT needed).
Use the container name as `host` (docker internal network).

```bash
curl -s -X POST http://localhost:3002/data/sources \
  -H "Content-Type: application/json" \
  -H "X-Team-Id: <TEAM_ID>" \
  -d '{
    "name": "test-data-db",
    "connector": "postgresql",
    "methodology": "로컬 테스트용 임시 컨테이너 DB (ARK-1149)",
    "credentials": {
      "host": "arkraft-test-db",
      "port": 5432,
      "database": "test_data",
      "user": "testuser",
      "password": "testpass"
    }
  }' | python3 -m json.tool
```

Save `data.id` from the response as **SOURCE_ID**.

---

## Step 5. Verify Registration

```bash
docker exec arkraft-api-postgres-1 psql -U arkraft -d arkraft -c \
  "SELECT id, name, connector FROM data_sources ORDER BY created_at DESC LIMIT 5;"
```

---

## Completion Report

- Container `arkraft-test-db` running status
- Tables: `stock_prices` (6 rows), `company_info` (2 rows)
- Registered data source ID
- Connection info (API internal): `arkraft-test-db:5432 / test_data / testuser`

---

## Cleanup (After Testing)

```bash
# arkraft DB에서 data source 삭제
docker exec arkraft-api-postgres-1 psql -U arkraft -d arkraft -c \
  "DELETE FROM data_sources WHERE name = 'test-data-db';"

# 임시 컨테이너 제거
docker rm -f arkraft-test-db
```
