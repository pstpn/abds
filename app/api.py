import json
import re
import traceback
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.ch import ClickHouse, ClickHouseError
from app.config import Config

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
MAX_BODY = 1 << 20


class BodyError(Exception):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def next_timestamp(previous: str | None) -> str:
    now = utcnow()
    if previous:
        try:
            prev = datetime.strptime(previous, DATETIME_FMT)
        except ValueError:
            prev = None
        if prev is not None and now <= prev:
            now = prev + timedelta(seconds=1)
    return now.strftime(DATETIME_FMT)


def valid_date(value) -> str | None:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return value


def valid_uint(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def parse_pagination(value: str) -> int | None:
    if not re.match(r"^\d+$", value):
        return None
    return int(value)


class Api:
    def __init__(self, ch: ClickHouse) -> None:
        self.ch = ch

    def ping(self) -> tuple[int, dict | None]:
        return 200, None

    def user_get(self, user_id: int) -> tuple[int, dict | None]:
        rows = self.ch.query(
            "SELECT id, fio, phone, phone_prev FROM dim_users FINAL WHERE id = {id:UInt64}",
            {"id": user_id},
        )
        if not rows:
            return 404, {"message": "Not found"}
        return 200, rows[0]

    def user_patch(self, user_id: int, body: dict) -> tuple[int, dict | None]:
        fio = body.get("fio")
        phone = body.get("phone")
        if fio is not None and (not isinstance(fio, str) or not fio.strip()):
            return 400, {"message": 'invalid "fio" field'}
        if phone is not None and (not isinstance(phone, str) or not phone.strip()):
            return 400, {"message": 'invalid "phone" field'}
        if fio is None and phone is None:
            return 400, {"message": 'at least one of "fio" or "phone" is required'}
        rows = self.ch.query(
            "SELECT fio, phone, phone_prev, toString(created_at) AS created_at, "
            "toString(updated_at) AS updated_at "
            "FROM dim_users FINAL WHERE id = {id:UInt64}",
            {"id": user_id},
        )
        if not rows:
            return 404, {"message": "Not found"}
        current = rows[0]
        if phone is not None:
            new_phone, phone_prev = phone, current["phone"]
        else:
            new_phone, phone_prev = current["phone"], current["phone_prev"]
        self.ch.insert("dim_users", [{
            "id": user_id,
            "fio": fio if fio is not None else current["fio"],
            "phone": new_phone,
            "phone_prev": phone_prev,
            "created_at": current["created_at"],
            "updated_at": next_timestamp(current["updated_at"]),
        }])
        return 204, None

    def realty_get(self, realty_id: int) -> tuple[int, dict | None]:
        rows = self.ch.query(
            "SELECT id, address, square, type, number, rooms, floor, porch "
            "FROM dim_realty WHERE id = {id:UInt64}",
            {"id": realty_id},
        )
        if not rows:
            return 404, {"message": "Not found"}
        return 200, rows[0]

    def realty_exists(self, realty_id: int) -> bool:
        return bool(self.ch.query(
            "SELECT id FROM dim_realty WHERE id = {id:UInt64}",
            {"id": realty_id},
        ))

    def readings_post(self, realty_id: int, body: dict) -> tuple[int, dict | None]:
        for field in ("user_id", "gauge_id", "tariff_id"):
            if valid_uint(body.get(field)) is None or body.get(field) == 0:
                return 400, {"message": f'invalid "{field}" field'}
        if valid_uint(body.get("day_kw")) is None:
            return 400, {"message": 'invalid "day_kw" field'}
        if valid_uint(body.get("night_kw")) is None:
            return 400, {"message": 'invalid "night_kw" field'}
        reading_date = valid_date(body.get("reading_date"))
        if reading_date is None:
            return 400, {"message": 'invalid "reading_date" field'}
        if not self.realty_exists(realty_id):
            return 404, {"message": "Not found"}
        for table, field in (
            ("dim_users", "user_id"),
            ("dim_gauges", "gauge_id"),
            ("dim_tariffs", "tariff_id"),
        ):
            rows = self.ch.query(
                f"SELECT id FROM {table} WHERE id = {{{field}:UInt64}}",
                {field: body[field]},
            )
            if not rows:
                return 404, {"message": "Not found"}
        previous = self.ch.query(
            "SELECT toString(max(created_at)) AS created_at FROM fact_meter_readings "
            "WHERE realty_id = {r:UInt64} AND reading_date = {d:Date}",
            {"r": realty_id, "d": reading_date},
        )
        created_at = next_timestamp(previous[0]["created_at"] if previous else None)
        self.ch.insert("fact_meter_readings", [{
            "realty_id": realty_id,
            "user_id": body["user_id"],
            "tariff_id": body["tariff_id"],
            "gauge_id": body["gauge_id"],
            "reading_date": reading_date,
            "day_kw": body["day_kw"],
            "night_kw": body["night_kw"],
            "created_at": created_at,
        }])
        return 201, None

    def readings_list(self, realty_id: int, params: dict) -> tuple[int, dict | None]:
        if not self.realty_exists(realty_id):
            return 404, {"message": "Not found"}
        date_from = params.get("date_from", [None])[0]
        date_to = params.get("date_to", [None])[0]
        if date_from is None or valid_date(date_from) is None:
            return 400, {"message": 'invalid "date_from" parameter'}
        if date_to is None or valid_date(date_to) is None:
            return 400, {"message": 'invalid "date_to" parameter'}
        if date_from > date_to:
            return 400, {"message": 'invalid "date_from" parameter'}
        rows = self.ch.query(
            "SELECT reading_date, user_id, tariff_id, gauge_id, day_kw, night_kw "
            "FROM fact_meter_readings FINAL "
            "WHERE realty_id = {r:UInt64} AND reading_date BETWEEN {df:Date} AND {dt:Date} "
            "ORDER BY reading_date ASC",
            {"r": realty_id, "df": date_from, "dt": date_to},
        )
        return 200, {"readings": rows, "count": len(rows)}

    def invoices_list(self, realty_id: int, params: dict) -> tuple[int, dict | None]:
        if not self.realty_exists(realty_id):
            return 404, {"message": "Not found"}
        limit_raw = params.get("limit", [None])[0]
        offset_raw = params.get("offset", [None])[0]
        limit = 10 if limit_raw is None else parse_pagination(limit_raw)
        offset = 0 if offset_raw is None else parse_pagination(offset_raw)
        if limit is None:
            return 400, {"message": 'invalid "limit" parameter'}
        if offset is None:
            return 400, {"message": 'invalid "offset" parameter'}
        total = self.ch.query(
            "SELECT count() AS count FROM fact_invoice WHERE realty_id = {r:UInt64}",
            {"r": realty_id},
        )[0]["count"]
        rows = self.ch.query(
            "SELECT tariff_id, gauge_id, day_kw, night_kw, price, deadline, created_at "
            "FROM fact_invoice WHERE realty_id = {r:UInt64} "
            f"ORDER BY created_at DESC, deadline DESC LIMIT {limit} OFFSET {offset}",
            {"r": realty_id},
        )
        return 200, {"invoices": rows, "count": total}

    def tariffs_get(self, params: dict) -> tuple[int, dict | None]:
        day = params.get("date", [None])[0]
        if day is None or valid_date(day) is None:
            return 400, {"message": 'invalid "date" parameter'}
        rows = self.ch.query(
            "SELECT id, name, price_day_kwph, price_night_kwph, valid_from, valid_to "
            "FROM dim_tariffs FINAL "
            "WHERE toDate({d:String}) >= valid_from AND toDate({d:String}) < valid_to "
            "ORDER BY valid_from DESC LIMIT 1",
            {"d": day},
        )
        if not rows:
            return 404, {"message": "Not found"}
        return 200, rows[0]

    def gauges_post(self, realty_id: int, body: dict) -> tuple[int, dict | None]:
        gauge_id = valid_uint(body.get("gauge_id"))
        if gauge_id is None or gauge_id == 0:
            return 400, {"message": 'invalid "gauge_id" field'}
        if not self.realty_exists(realty_id):
            return 404, {"message": "Not found"}
        if not self.ch.query(
            "SELECT id FROM dim_gauges WHERE id = {id:UInt64}",
            {"id": gauge_id},
        ):
            return 404, {"message": "Not found"}
        active = self.ch.query(
            "SELECT gauge_id, version FROM fact_gauge_bindings FINAL "
            "WHERE realty_id = {r:UInt64} AND sign = 1 "
            "ORDER BY version DESC LIMIT 1",
            {"r": realty_id},
        )
        created_at = utcnow().strftime(DATETIME_FMT)
        rows = []
        version = 1
        if active:
            version = active[0]["version"] + 1
            rows.append({
                "gauge_id": active[0]["gauge_id"],
                "realty_id": realty_id,
                "created_at": created_at,
                "sign": -1,
                "version": active[0]["version"],
            })
        rows.append({
            "gauge_id": gauge_id,
            "realty_id": realty_id,
            "created_at": created_at,
            "sign": 1,
            "version": version,
        })
        self.ch.insert("fact_gauge_bindings", rows)
        return 201, None


ROUTES = [
    ("GET", re.compile(r"^/ping$"), lambda api, m, q, b: api.ping()),
    ("GET", re.compile(r"^/users/(\d+)$"), lambda api, m, q, b: api.user_get(int(m.group(1)))),
    ("PATCH", re.compile(r"^/users/(\d+)$"), lambda api, m, q, b: api.user_patch(int(m.group(1)), b)),
    ("GET", re.compile(r"^/realty/(\d+)$"), lambda api, m, q, b: api.realty_get(int(m.group(1)))),
    ("POST", re.compile(r"^/realty/(\d+)/readings$"), lambda api, m, q, b: api.readings_post(int(m.group(1)), b)),
    ("GET", re.compile(r"^/realty/(\d+)/readings$"), lambda api, m, q, b: api.readings_list(int(m.group(1)), q)),
    ("GET", re.compile(r"^/realty/(\d+)/invoices$"), lambda api, m, q, b: api.invoices_list(int(m.group(1)), q)),
    ("GET", re.compile(r"^/tariffs$"), lambda api, m, q, b: api.tariffs_get(q)),
    ("POST", re.compile(r"^/realty/(\d+)/gauges$"), lambda api, m, q, b: api.gauges_post(int(m.group(1)), b)),
]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    api = None

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def do_PATCH(self) -> None:
        self.dispatch("PATCH")

    def dispatch(self, method: str) -> None:
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            body = self.read_body() if method in ("POST", "PATCH") else {}
            if isinstance(body, dict):
                for route_method, pattern, handler in ROUTES:
                    if route_method != method:
                        continue
                    match = pattern.match(parsed.path)
                    if match:
                        status, payload = handler(self.api, match, query, body)
                        self.respond(status, payload)
                        return
            self.respond(404, {"message": "Not found"})
        except BodyError:
            self.respond(400, {"message": "invalid request body"})
        except ClickHouseError as err:
            self.respond(503, {"message": str(err)})
        except Exception:
            traceback.print_exc()
            self.respond(500, {"message": "internal server error"})

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, MAX_BODY)) if length else b""
        if not raw:
            raise BodyError
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise BodyError from None
        if not isinstance(body, dict):
            raise BodyError
        return body

    def respond(self, status: int, payload: dict | None) -> None:
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


def run() -> None:
    cfg = Config()
    Handler.api = Api(ClickHouse(
        host=cfg.ch_host,
        http_port=cfg.ch_http_port,
        user=cfg.ch_user,
        password=cfg.ch_password,
        database=cfg.ch_database,
    ))
    server = ThreadingHTTPServer(("0.0.0.0", cfg.port), Handler)
    print(f"energosbyt service listening on port {cfg.port}", flush=True)
    server.serve_forever()
