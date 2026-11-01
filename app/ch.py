import base64
import json
import urllib.error
import urllib.parse
import urllib.request


class ClickHouseError(Exception):
    pass


class ClickHouse:
    def __init__(self, host: str, http_port: str, user: str, password: str, database: str) -> None:
        self.base = f"http://{host}:{http_port}/"
        self.user = user
        self.password = password
        self.database = database

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        params = params or {}
        url = self._url(sql, {f"param_{k}": str(v) for k, v in params.items()})
        body = self._request(url, b"")
        return [json.loads(line) for line in body.splitlines() if line.strip()]

    def insert(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        url = self._url(f"INSERT INTO {self.database}.{table} FORMAT JSONEachRow", {})
        self._request(url, payload.encode("utf-8"))

    def _url(self, sql: str, params: dict[str, str]) -> str:
        query = {
            "query": sql,
            "database": self.database,
            "default_format": "JSONEachRow",
            "output_format_json_quote_64bit_integers": "0",
        }
        query.update(params)
        return self.base + "?" + urllib.parse.urlencode(query)

    def _request(self, url: str, data: bytes) -> str:
        request = urllib.request.Request(url, data=data, method="POST")
        if self.password:
            token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
            request.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")
            raise ClickHouseError(f"clickhouse {err.code}: {detail}") from err
        except urllib.error.URLError as err:
            raise ClickHouseError(f"clickhouse unreachable: {err}") from err
