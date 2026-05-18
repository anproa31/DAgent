# Demo PostgreSQL (`db_test`)

Small PostgreSQL database pre-loaded with the same HR sample data as `sample_dataset/csv/`. Use it to demo **Connect database** and SQL/agent analysis against a live DB (via DuckDB `ATTACH` in the sandbox).

## Tables

| Table | Rows (approx.) | Description |
|-------|----------------|-------------|
| `hr_employee_data` | 6,677 | Employee master + attrition |
| `employee_office_survey` | 47,107 | Office ratings by year |
| `job_position_structure` | 32 | Department / level / role |
| `office_codes` | 8 | Office locations |

## Quick start

From the repository root:

```bash
docker compose -f sample_dataset/db_test/docker-compose.yml up -d
```

Wait until healthy (first run loads CSVs — ~30s):

```bash
docker compose -f sample_dataset/db_test/docker-compose.yml ps
```

Verify data:

```bash
docker exec demo_postgres psql -U demo -d hr_analytics -c "SELECT COUNT(*) FROM hr_employee_data;"
```

## Connect in the app

1. Start the main stack: `docker compose -f docker-compose.dev.yml up -d`
2. Open the UI → **Connect database** → PostgreSQL
3. Use one of the following:

**App on host (browser → localhost:8073), DB in Docker**

| Field | Value |
|-------|--------|
| Connection string | `postgresql://demo:demo@localhost:5433/hr_analytics` |

**App in Docker (`app_service`), DB in Docker**

| Field | Value |
|-------|--------|
| Connection string | `postgresql://demo:demo@host.docker.internal:5433/hr_analytics` |

Or structured fields: host `host.docker.internal`, port `5433`, database `hr_analytics`, user `demo`, password `demo`.

## Example questions (agent)

- Show me 5 employees from the Sales department
- What is the average office rating by city?
- How many employees left voluntarily in 2019?
- Join employees with office_codes and list headcount by country

## Reset demo data

```bash
docker compose -f sample_dataset/db_test/docker-compose.yml down -v
docker compose -f sample_dataset/db_test/docker-compose.yml up -d
```

## Credentials (demo only)

- User: `demo`
- Password: `demo`
- Database: `hr_analytics`
- Port on host: `5433`

Do not use these credentials in production.
