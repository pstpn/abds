from envlocal import ClickHouse, load_env

TABLES = [
    "dim_realty",
    "dim_gauges",
    "dim_tariffs",
    "dim_users",
    "fact_gauge_bindings",
    "fact_meter_readings",
    "fact_invoice",
]


def main() -> None:
    env = load_env()
    database = env.get("CLICKHOUSE_DATABASE", "energosbyt")
    ch = ClickHouse(env)
    for table in TABLES:
        ch.execute(f"DROP TABLE IF EXISTS {database}.{table}")
    print(f"Tables dropped from database {database}")


if __name__ == "__main__":
    main()
