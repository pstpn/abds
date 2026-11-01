# Energosbyt

[![labs](https://github.com/pstpn/abds/actions/workflows/energosbyt.energosbyt.lab.yml/badge.svg)](https://github.com/pstpn/abds/actions/workflows/energosbyt.energosbyt.lab.yml)

Backend service of a fictional utility company, Lab 1 of the
[Architecture of Big Data Systems](https://github.com/sitnikovik/abds) course.
A single ClickHouse instance holds a star schema of meters, owners, tariffs and
readings; a Python HTTP service exposes the data and applies SCD 1, SCD 2 and
SCD 3 on top of `MergeTree`, `ReplacingMergeTree` and
`VersionedCollapsingMergeTree`.

## Stack

- ClickHouse `26.7` in Docker, one instance
- HTTP service in Python 3 standard library only, talks to ClickHouse
  over the HTTP interface
- Dataset generator in Python, writes CSV files

## Run

```bash
make run       # starts ClickHouse and the app
make setup     # creates the schema, generates and loads the data
make teardown  # drops the tables and the data
make stop      # stops the containers
```

Typical flow:

```bash
make run
make setup
curl http://localhost:8123/ping   # Ok.
curl http://localhost:8080/ping   # 200 OK
make teardown
make stop
```

All configuration lives in `.env.local`: the app port and the ClickHouse
connection settings. The app container reaches ClickHouse by the service name,
everything else uses the published ports.

## Make targets

| Target | Description |
| --- | --- |
| `make run` | Starts ClickHouse and the app via docker compose |
| `make stop` | Stops the containers |
| `make clean` | Stops the containers and removes volumes |
| `make gen` | Generates CSV datasets into `data/` |
| `make load` | Loads `data/` into ClickHouse |
| `make setup` | Creates the schema, then runs `gen` and `load` |
| `make teardown` | Drops the tables and the data |

`make setup` recreates the tables from scratch, so a repeated run never
produces duplicates. The whole setup takes about 1.5 minutes on a stock runner.

## Data volumes

| Table | Rows | Content |
| --- | --- | --- |
| `dim_realty` | 1 000 | Flats and non-residential units across several houses |
| `dim_gauges` | 1 100 | One gauge per unit plus 100 replacements |
| `dim_tariffs` | 2 | Two versions of one tariff |
| `dim_users` | 1 000 | One owner per unit |
| `fact_gauge_bindings` | 1 200 | Installation per unit, 100 units with an annulled and a new binding |
| `fact_meter_readings` | 1 128 885 | A reading per unit per day from 2023-11-01 to 2026-10-31, ~3% with a correction |
| `fact_invoice` | 36 000 | An invoice per unit per month, 36 months |

## Schema

| Table | Engine | Sort key | Partitioning |
| --- | --- | --- | --- |
| `dim_realty` | `MergeTree` | `id` | — |
| `dim_gauges` | `MergeTree` | `id` | — |
| `dim_tariffs` | `ReplacingMergeTree(updated_at)` | `(id, valid_from)` | — |
| `dim_users` | `ReplacingMergeTree(updated_at)` | `id` | — |
| `fact_gauge_bindings` | `VersionedCollapsingMergeTree(sign, version)` | `(realty_id, gauge_id)` | — |
| `fact_meter_readings` | `ReplacingMergeTree(created_at)` | `(realty_id, reading_date)` | `toYYYYMM(reading_date)` |
| `fact_invoice` | `MergeTree` | `(realty_id, created_at)` | `toYYYYMM(created_at)` |

Why these keys:

- `dim_realty`, `dim_gauges` — point lookups by `id`, no updates, a plain
  `MergeTree` with the `id` sort key is enough.
- `dim_tariffs` — a version is identified by `(id, valid_from)`; the sorting
  key keeps every version its own row, and `ReplacingMergeTree(updated_at)`
  collapses rewrites of the same version.
- `dim_users` — all versions of an owner share one `id`, the newest version
  wins on `FINAL` by `updated_at`.
- `fact_gauge_bindings` — the sort key holds the key fields of a binding; an
  annul row repeats the key fields and the version of the row it cancels, so
  `VersionedCollapsingMergeTree` collapses the pair.
- `fact_meter_readings` — a correction repeats the key `(realty_id,
  reading_date)` with a later `created_at`, monthly partitions let a range
  query read only the months it needs.
- `fact_invoice` — invoices are read per unit sorted by issue date; monthly
  partitions keep future labs cheap when data grows.

## API

All bodies are JSON, fields are `snake_case`, dates are `YYYY-MM-DD`,
timestamps are `YYYY-MM-DD HH:MM:SS`, errors are `{"message": "..."}`.
A Postman collection lives in `api/`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/ping` | Liveness probe, `200` with an empty body |
| `GET` | `/users/{id}` | Owner: `id`, `fio`, `phone`, `phone_prev` |
| `PATCH` | `/users/{id}` | Updates `fio` (SCD 1) and `phone` (SCD 3), `204` |
| `GET` | `/realty/{id}` | Realty object |
| `POST` | `/realty/{id}/readings` | Submits a reading, repeated calls correct it, `201` |
| `GET` | `/realty/{id}/readings?date_from&date_to` | Actual readings per date, inclusive range |
| `GET` | `/realty/{id}/invoices?limit&offset` | Invoices sorted by `created_at` descending, defaults `limit=10`, `offset=0` |
| `GET` | `/tariffs?date=` | Tariff version valid on the date |
| `POST` | `/realty/{id}/gauges` | Installs a gauge, annuls the active binding first, `201` |

## SCD scenarios

### Owner changed the name — SCD 1

`PATCH /users/1` with a new `fio` inserts a new row version, the old name is
gone after the merge:

```sql
SELECT count() FROM energosbyt.dim_users FINAL
WHERE id = 1 AND fio = 'Михайлов Татьяна Сергеевна';
-- 0
```

### Owner changed the phone twice — SCD 3

```bash
curl -X PATCH localhost:8080/users/1 -d '{"phone": "+79222222222"}'
```

The current phone lands in `phone`, the previous one stays in `phone_prev`:

```sql
SELECT phone, phone_prev FROM energosbyt.dim_users FINAL WHERE id = 1;
```

```json
{"phone": "+79222222222", "phone_prev": "+79125668452"}
```

### Tariff changed on November 1st — SCD 2

```bash
curl "localhost:8080/tariffs?date=2026-10-31"
curl "localhost:8080/tariffs?date=2026-11-01"
```

The day before the boundary returns the old version (620/310 kopecks), the
boundary day returns the new one (680/340), each with its own validity range:

```sql
SELECT valid_from, valid_to, price_day_kwph FROM energosbyt.dim_tariffs
FINAL ORDER BY valid_from;
```

```text
2023-11-01 00:00:00 │ 2026-11-01 00:00:00 │ 620
2026-11-01 00:00:00 │ 2099-01-01 00:00:00 │ 680
```

An old invoice does not change: its price was computed with the version valid
on the invoice date, the generator already reflects that.

### Reading correction — ReplacingMergeTree

```bash
curl -X POST localhost:8080/realty/1/readings \
  -d '{"user_id":1,"gauge_id":1,"tariff_id":1,"reading_date":"2026-10-01","day_kw":1250,"night_kw":300}'
```

The table keeps both rows, the latest `created_at` wins:

```sql
SELECT count() FROM energosbyt.fact_meter_readings
WHERE realty_id = 1 AND reading_date = '2026-10-01';
-- 2 before the background merge

SELECT day_kw, night_kw FROM energosbyt.fact_meter_readings FINAL
WHERE realty_id = 1 AND reading_date = '2026-10-01';
-- one row: 1250, 300
```

`GET /realty/1/readings?date_from=2026-10-01&date_to=2026-10-01` returns the
corrected value only.

### Gauge replacement — VersionedCollapsingMergeTree

```bash
curl -X POST localhost:8080/realty/1/gauges -d '{"gauge_id": 2}'
```

The endpoint annuls the active binding with `sign = -1` and the same version,
then inserts the new installation with `version + 1`:

```sql
SELECT * FROM energosbyt.fact_gauge_bindings FINAL WHERE realty_id = 1;
```

```text
2 │ 1 │ 2026-11-01 19:50:23 │  1 │ 2
```

Without `FINAL` the raw rows are still there and collapse in the background:

```sql
SELECT gauge_id, sign, version FROM energosbyt.fact_gauge_bindings
WHERE realty_id = 1 ORDER BY version;
```

```text
1 │  1 │ 1
1 │ -1 │ 1
2 │  1 │ 2
```

### Erroneous row — DELETE

A row with a mistyped value can be removed directly:

```sql
ALTER TABLE energosbyt.fact_meter_readings DELETE
WHERE realty_id = 1 AND reading_date = '2026-10-01' AND day_kw = 999999;
```

## Repository layout

```text
api/                    Postman collection
app/                    HTTP service
db/schema.sql           ClickHouse DDL
scripts/                generator, loader, schema and teardown scripts
data/                   generated CSV files, not committed
volume/                 ClickHouse data, not committed
```
