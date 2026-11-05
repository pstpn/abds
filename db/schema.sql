CREATE DATABASE IF NOT EXISTS {database};

DROP TABLE IF EXISTS {database}.dim_realty;
DROP TABLE IF EXISTS {database}.dim_gauges;
DROP TABLE IF EXISTS {database}.dim_tariffs;
DROP TABLE IF EXISTS {database}.dim_users;
DROP TABLE IF EXISTS {database}.fact_gauge_bindings;
DROP TABLE IF EXISTS {database}.fact_meter_readings;
DROP TABLE IF EXISTS {database}.fact_invoice;

CREATE TABLE {database}.dim_realty
(
    id         UInt64,
    address    String,
    square     UInt32,
    type       String,
    number     String,
    rooms      UInt8,
    floor      UInt8,
    porch      UInt8,
    created_at DateTime
)
ENGINE = MergeTree
ORDER BY id;

CREATE TABLE {database}.dim_gauges
(
    id         UInt64,
    name       String,
    country    String,
    created_at DateTime
)
ENGINE = MergeTree
ORDER BY id;

CREATE TABLE {database}.dim_tariffs
(
    id               UInt64,
    name             String,
    price_day_kwph   UInt32,
    price_night_kwph UInt32,
    valid_from       DateTime,
    valid_to         DateTime,
    created_at       DateTime,
    updated_at       DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (id, valid_from);

CREATE TABLE {database}.dim_users
(
    id          UInt64,
    fio         String,
    phone       String,
    phone_prev  String,
    created_at  DateTime,
    updated_at  DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY id;

CREATE TABLE {database}.fact_gauge_bindings
(
    gauge_id   UInt64,
    realty_id  UInt64,
    created_at DateTime,
    sign       Int8,
    version    UInt64
)
ENGINE = VersionedCollapsingMergeTree(sign, version)
ORDER BY (realty_id, gauge_id);

CREATE TABLE {database}.fact_meter_readings
(
    realty_id    UInt64,
    user_id      UInt64,
    tariff_id    UInt64,
    gauge_id     UInt64,
    reading_date Date,
    day_kw       UInt32,
    night_kw     UInt32,
    created_at   DateTime
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (realty_id, reading_date)
PARTITION BY toYYYYMM(reading_date);

CREATE TABLE {database}.fact_invoice
(
    realty_id  UInt64,
    user_id    UInt64,
    tariff_id  UInt64,
    gauge_id   UInt64,
    day_kw     UInt32,
    night_kw   UInt32,
    price      UInt64,
    deadline   Date,
    created_at DateTime
)
ENGINE = MergeTree
ORDER BY (realty_id, created_at)
PARTITION BY toYYYYMM(created_at);
