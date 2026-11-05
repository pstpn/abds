import os

from envlocal import clickhouse_from_env, load_env

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "db", "schema.sql")


def main() -> None:
    env = load_env()
    database = env.get("CLICKHOUSE_DATABASE", "energosbyt")
    ch = clickhouse_from_env(env)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = fh.read()
    for statement in schema.split(";"):
        statement = statement.strip()
        if not statement:
            continue
        ch.execute(statement.format(database=database))
    print(f"Schema created in database {database}")


if __name__ == "__main__":
    main()
