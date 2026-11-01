import os
import urllib.error
import urllib.parse
import urllib.request

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")


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


class ClickHouse:
    def __init__(self, env: dict) -> None:
        self.host = env.get("CLICKHOUSE_HOST", "localhost")
        self.port = env.get("CLICKHOUSE_HTTP_PORT", "8123")
        self.user = env.get("CLICKHOUSE_USER", "default")
        self.password = env.get("CLICKHOUSE_PASSWORD", "")
        self.base = f"http://{self.host}:{self.port}/"

    def url(self, query: str) -> str:
        params = {"query": query}
        if self.password:
            params["user"] = self.user
            params["password"] = self.password
        return self.base + "?" + urllib.parse.urlencode(params)

    def execute(self, query: str, data: bytes = b"") -> str:
        request = urllib.request.Request(self.url(query), data=data, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", "replace")
            raise RuntimeError(f"ClickHouse error {err.code}: {body}") from err
