# SCD scenarios

Worked examples of the slowly changing dimension patterns implemented in
lab 1. Each scenario is run against a local instance after `make setup`;
the SQL shows the stored state behind the HTTP response.

## Owner changed the name — SCD 1

`PATCH /users/1` with a new `fio` inserts a new row version, the old name is
gone after the merge:

```sql
SELECT count() FROM energosbyt.dim_users FINAL
WHERE id = 1 AND fio = 'Михайлов Татьяна Сергеевна';
-- 0
```

## Owner changed the phone twice — SCD 3

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

## Tariff changed on November 1st — SCD 2

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

## Reading correction — ReplacingMergeTree

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

## Gauge replacement — VersionedCollapsingMergeTree

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

## Erroneous row — DELETE

A row with a mistyped value can be removed directly:

```sql
ALTER TABLE energosbyt.fact_meter_readings DELETE
WHERE realty_id = 1 AND reading_date = '2026-10-01' AND day_kw = 999999;
```
