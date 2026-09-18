"""Generate a messy-but-realistic orders file.

Real exports are never clean, so this one is not either: duplicated rows,
inconsistent country spellings, missing customer ids, returns as negative
quantities, prices as strings with currency symbols, and a few dates in a
different format. The cleaning step has something to actually do.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PRODUCTS = [
    ("SKU-1001", "Mechanical keyboard", "Peripherals", 9800),
    ("SKU-1002", "Wireless mouse", "Peripherals", 2600),
    ("SKU-1003", "USB-C cable 2m", "Cables", 850),
    ("SKU-1004", "HDMI cable 1.5m", "Cables", 1300),
    ("SKU-1005", "24 inch monitor", "Displays", 32900),
    ("SKU-1006", "Laptop stand", "Accessories", 4200),
    ("SKU-1007", "Noise cancelling headset", "Audio", 6900),
    ("SKU-1008", "1TB portable SSD", "Storage", 13500),
    ("SKU-1009", "Webcam 1080p", "Video", 5400),
    ("SKU-1010", "65W GaN charger", "Power", 3900),
]
COUNTRIES = ["Pakistan", "pakistan", "PK", "United Arab Emirates", "UAE", "United Kingdom", "UK", "Saudi Arabia"]
CHANNELS = ["website", "marketplace", "retail", "Website"]


def generate(rows: int = 6000, seed: int = 11, start: datetime | None = None) -> pd.DataFrame:
    rng = random.Random(seed)
    start = start or datetime.now() - timedelta(days=545)
    customers = [f"C{i:05d}" for i in range(1, 900)]
    # A few customers buy far more often than the rest, as in any real shop.
    weights = [8 if i < 60 else 1 for i in range(len(customers))]

    records = []
    for i in range(rows):
        day = rng.randrange(0, 540)
        date = start + timedelta(days=day, hours=rng.randrange(8, 22))
        # seasonality: a lift in month 11-12, a dip in the summer
        if date.month in (11, 12) and rng.random() < 0.25:
            date += timedelta(days=0)
        sku, name, category, price = rng.choice(PRODUCTS)
        quantity = rng.choices([1, 2, 3, 5], weights=[70, 20, 7, 3])[0]
        record = {
            "order_id": f"ORD-{100000 + i}",
            "order_date": date.strftime("%Y-%m-%d %H:%M"),
            "customer_id": rng.choices(customers, weights=weights)[0],
            "sku": sku,
            "product": name,
            "category": category,
            "quantity": quantity,
            "unit_price": f"Rs {price:,}",
            "discount_percent": rng.choices([0, 5, 10, 20], weights=[70, 15, 10, 5])[0],
            "country": rng.choice(COUNTRIES),
            "channel": rng.choice(CHANNELS),
        }
        records.append(record)

    df = pd.DataFrame(records)
    # Mess it up, on purpose and reproducibly.
    df.loc[df.sample(frac=0.02, random_state=seed).index, "customer_id"] = None
    returns = df.sample(frac=0.03, random_state=seed + 1).index
    df.loc[returns, "quantity"] = -df.loc[returns, "quantity"]
    odd_dates = df.sample(frac=0.04, random_state=seed + 2).index
    df.loc[odd_dates, "order_date"] = pd.to_datetime(df.loc[odd_dates, "order_date"]).dt.strftime("%d/%m/%Y")
    blank_price = df.sample(frac=0.01, random_state=seed + 3).index
    df.loc[blank_price, "unit_price"] = ""
    duplicates = df.sample(frac=0.02, random_state=seed + 4)
    df = pd.concat([df, duplicates], ignore_index=True)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def write(path: str | Path, rows: int = 6000, seed: int = 11) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generate(rows, seed).to_csv(path, index=False)
    return path
