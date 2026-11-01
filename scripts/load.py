import os

from envlocal import ClickHouse, load_env

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

TABLES = [
    "dim_realty",
    "dim_gauges",
    "dim_tariffs",
    "dim_users",
    "fact_gauge_bindings",
    "fact_meter_readings",
    "fact_invoice",
]

BATCH_LINES = 200000


def load_table(ch: ClickHouse, database: str, table: str) -> int:
    path = os.path.join(DATA_DIR, table + ".csv")
    if not os.path.exists(path):
        raise RuntimeError(f"missing {path}, run make gen first")
    total = 0
    with open(path, encoding="utf-8") as fh:
        while True:
            batch = fh.readlines(BATCH_LINES)
            if not batch:
                break
            ch.execute(
                f"INSERT INTO {database}.{table} FORMAT CSV",
                data="".join(batch).encode("utf-8"),
            )
            total += len(batch)
    return total


def main() -> None:
    env = load_env()
    database = env.get("CLICKHOUSE_DATABASE", "energosbyt")
    ch = ClickHouse(env)
    for table in TABLES:
        total = load_table(ch, database, table)
        print(f"{table}: {total} rows loaded")


if __name__ == "__main__":
    main()
