import csv
import os
import random
from datetime import date, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

PERIOD_START = date(2023, 11, 1)
PERIOD_END = date(2026, 10, 31)

REALTIES = 1000
REPLACEMENTS = 100
REPLACED_FROM = 51
CORRECTION_RATE = 0.03

TARIFF_V1_FROM = date(2023, 11, 1)
TARIFF_V2_FROM = date(2026, 11, 1)
TARIFF_OPEN_END = date(2099, 1, 1)
PRICE_DAY_V1, PRICE_NIGHT_V1 = 620, 310
PRICE_DAY_V2, PRICE_NIGHT_V2 = 680, 340

SURNAMES = [
    "Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Васильев", "Попов",
    "Соколов", "Михайлов", "Новиков", "Фёдоров", "Морозов", "Волков", "Зайцев",
    "Павлов", "Семёнов", "Голубев", "Виноградов", "Богданов", "Воробьёв",
]
NAMES = [
    "Иван", "Пётр", "Анна", "Мария", "Сергей", "Ольга", "Дмитрий", "Екатерина",
    "Алексей", "Наталья", "Андрей", "Елена", "Светлана", "Николай", "Татьяна",
]
PATRONYMICS = [
    "Иванович", "Ивановна", "Петрович", "Петровна", "Сергеевич", "Сергеевна",
    "Дмитриевич", "Дмитриевна", "Алексеевич", "Алексеевна", "Николаевич", "Николаевна",
]
CITIES = ["г. Москва", "г. Санкт-Петербург", "г. Казань", "г. Новосибирск"]
STREETS = [
    "улица Пушкина", "улица Лермонтова", "проспект Мира", "улица Гагарина",
    "набережная Реки", "бульвар Славы", "переулок Тихий",
]
GAUGE_MODELS = [
    ("Меркурий 230", "Россия"), ("Энергомера CE308", "Россия"),
    ("НЕВА 303", "Россия"), ("Инкотекс Меркурий 231", "Россия"),
    ("ZPA E-31x", "Чехия"), ("Gama P3", "Чехия"),
]


def all_days(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def month_key(day: date) -> date:
    return day.replace(day=1)


def active_gauge(realty_id: int, day: date) -> int:
    if REPLACED_FROM <= realty_id < REPLACED_FROM + REPLACEMENTS:
        if day >= date(2025, (realty_id % 12) + 1, (realty_id % 27) + 1):
            return REALTIES + realty_id - REPLACED_FROM
    return realty_id


def generate_realty() -> None:
    with open(os.path.join(DATA_DIR, "dim_realty.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for realty_id in range(1, REALTIES + 1):
            address = (
                f"{random.choice(CITIES)}, {random.choice(STREETS)}, "
                f"дом {realty_id % 12 + 1}"
            )
            if realty_id % 20 == 0:
                row = [realty_id, address, random.randint(20, 500), "nrcp", "",
                       1, realty_id % 15 + 1, realty_id % 5 + 1]
            else:
                row = [realty_id, address, random.randint(18, 120), "flat",
                       f"{realty_id % 200 + 1:04d}", random.randint(1, 4),
                       realty_id % 15 + 1, realty_id % 5 + 1]
            row.append(f"2023-11-01 09:{realty_id % 60:02d}:00")
            writer.writerow(row)


def generate_users() -> None:
    with open(os.path.join(DATA_DIR, "dim_users.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for user_id in range(1, REALTIES + 1):
            fio = f"{random.choice(SURNAMES)} {random.choice(NAMES)} {random.choice(PATRONYMICS)}"
            phone = f"+79{random.randint(10, 99):02d}{random.randint(0, 9999999):07d}"
            phone_prev = ""
            if user_id % 10 == 0:
                phone_prev = f"+79{random.randint(10, 99):02d}{random.randint(0, 9999999):07d}"
            created = f"2023-11-01 10:{user_id % 60:02d}:00"
            writer.writerow([user_id, fio, phone, phone_prev, created, created])


def generate_gauges() -> None:
    total = REALTIES + REPLACEMENTS
    with open(os.path.join(DATA_DIR, "dim_gauges.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for gauge_id in range(1, total + 1):
            name, country = random.choice(GAUGE_MODELS)
            writer.writerow([
                gauge_id, name, country,
                f"2023-10-{gauge_id % 27 + 1:02d} 08:{gauge_id % 60:02d}:00",
            ])


def generate_tariffs() -> None:
    with open(os.path.join(DATA_DIR, "dim_tariffs.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            1, "День–Ночь", PRICE_DAY_V1, PRICE_NIGHT_V1,
            f"{TARIFF_V1_FROM} 00:00:00", f"{TARIFF_V2_FROM} 00:00:00",
            f"{TARIFF_V1_FROM} 00:00:00", f"{TARIFF_V1_FROM} 00:00:00",
        ])
        writer.writerow([
            1, "День–Ночь", PRICE_DAY_V2, PRICE_NIGHT_V2,
            f"{TARIFF_V2_FROM} 00:00:00", f"{TARIFF_OPEN_END} 00:00:00",
            f"{TARIFF_V2_FROM} 00:00:00", f"{TARIFF_V2_FROM} 00:00:00",
        ])


def generate_bindings() -> None:
    with open(os.path.join(DATA_DIR, "fact_gauge_bindings.csv"), "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for realty_id in range(1, REALTIES + 1):
            writer.writerow([realty_id, realty_id, "2023-10-30 12:00:00", 1, 1])
        for i in range(REPLACEMENTS):
            realty_id = REPLACED_FROM + i
            when = f"2025-{realty_id % 12 + 1:02d}-{realty_id % 27 + 1:02d}"
            writer.writerow([realty_id, realty_id, f"{when} 10:00:00", -1, 1])
            writer.writerow([realty_id, REALTIES + i, f"{when} 10:05:00", 1, 2])


def generate_readings(days: list) -> None:
    with open(os.path.join(DATA_DIR, "fact_meter_readings.csv"), "w", encoding="utf-8") as fh:
        buf = []
        for realty_id in range(1, REALTIES + 1):
            day_kw = random.randint(5000, 50000)
            night_kw = random.randint(2000, 20000)
            for day in days:
                day_kw += random.randint(2, 18)
                night_kw += random.randint(1, 12)
                reading_date = day.isoformat()
                gauge_id = active_gauge(realty_id, day)
                buf.append(
                    f"{realty_id},{realty_id},1,{gauge_id},{reading_date},"
                    f"{day_kw},{night_kw},{reading_date} 12:00:00\n"
                )
                if random.random() < CORRECTION_RATE:
                    buf.append(
                        f"{realty_id},{realty_id},1,{gauge_id},{reading_date},"
                        f"{day_kw + random.randint(1, 5)},{night_kw + random.randint(1, 5)},"
                        f"{reading_date} 23:30:00\n"
                    )
                if len(buf) >= 200000:
                    fh.writelines(buf)
                    buf = []
        fh.writelines(buf)


def generate_invoices(months: list, days: list) -> None:
    random.seed(4242)
    daily = {
        realty_id: (random.randint(2, 18), random.randint(1, 12))
        for realty_id in range(1, REALTIES + 1)
    }
    with open(os.path.join(DATA_DIR, "fact_invoice.csv"), "w", encoding="utf-8") as fh:
        buf = []
        for month in months:
            month_days = [d for d in days if month_key(d) == month]
            last = month_days[-1]
            deadline = (month.replace(day=28) + timedelta(days=14)).replace(day=10)
            for realty_id in range(1, REALTIES + 1):
                day_used = daily[realty_id][0] * len(month_days)
                night_used = daily[realty_id][1] * len(month_days)
                price = day_used * PRICE_DAY_V1 + night_used * PRICE_NIGHT_V1
                buf.append(
                    f"{realty_id},{realty_id},1,{active_gauge(realty_id, last)},{day_used},"
                    f"{night_used},{price},{deadline.isoformat()},{last.isoformat()} 10:00:00\n"
                )
                if len(buf) >= 100000:
                    fh.writelines(buf)
                    buf = []
        fh.writelines(buf)


def main() -> None:
    random.seed(42)
    os.makedirs(DATA_DIR, exist_ok=True)

    days = list(all_days(PERIOD_START, PERIOD_END))
    months = []
    month = month_key(PERIOD_START)
    while month <= month_key(PERIOD_END):
        months.append(month)
        month = (month + timedelta(days=32)).replace(day=1)

    generate_realty()
    generate_users()
    generate_gauges()
    generate_tariffs()
    generate_bindings()
    generate_readings(days)
    generate_invoices(months, days)
    print("Datasets generated in", DATA_DIR)


if __name__ == "__main__":
    main()
