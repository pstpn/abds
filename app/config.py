import os


class Config:
    def __init__(self) -> None:
        self.port = int(os.environ.get("APP_PORT", "8080"))
        self.ch_host = os.environ.get("CLICKHOUSE_HOST", "localhost")
        self.ch_http_port = os.environ.get("CLICKHOUSE_HTTP_PORT", "8123")
        self.ch_user = os.environ.get("CLICKHOUSE_USER", "default")
        self.ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "")
        self.ch_database = os.environ.get("CLICKHOUSE_DATABASE", "energosbyt")
