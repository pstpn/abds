import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.ch import ClickHouse

ENV_FILE = os.path.join(ROOT, ".env.local")


def load_env(path: str = ENV_FILE) -> dict:
    values = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def clickhouse_from_env(env: dict) -> ClickHouse:
    return ClickHouse(
        host=env.get("CLICKHOUSE_HOST", "localhost"),
        http_port=env.get("CLICKHOUSE_HTTP_PORT", "8123"),
        user=env.get("CLICKHOUSE_USER", "default"),
        password=env.get("CLICKHOUSE_PASSWORD", ""),
        database=env.get("CLICKHOUSE_DATABASE", "energosbyt"),
    )
