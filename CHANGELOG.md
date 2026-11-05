# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-11-01

### Added

- ClickHouse 26.7 setup in `docker-compose.yml` with a single instance,
  published HTTP and native ports, data stored in `volume/`
- HTTP service in `app/` with the lab 1 endpoints: ping, owners, realty,
  readings, invoices, tariffs and gauge installation
- Star schema DDL in `db/schema.sql`: `dim_realty`, `dim_gauges`,
  `dim_tariffs`, `dim_users`, `fact_gauge_bindings`, `fact_meter_readings`,
  `fact_invoice`
- Dataset generator `scripts/generate.py`: 1 000 realty objects, 1 100 gauges,
  two tariff versions, 1 000 owners, 1 200 gauge bindings, about 1.13M meter
  readings with ~3% corrections, 36 000 invoices
- Loader `scripts/load.py` with batched CSV inserts over the HTTP interface
- `scripts/schema.py` and `scripts/teardown.py` for idempotent setup and
  full data removal
- Make targets `gen`, `load`, `setup`, `teardown` alongside the template's
  `run`, `stop`, `clean`
- Postman collection in `api/`
