"""Build the workshop's self-contained SQLite dataset: data/sales.db.

A small, fictional retail business ("Blue Ridge Outfitters") with four tables:

    customers   (customer_id, name, region, segment, signup_date)
    products    (product_id, name, category, unit_price)
    orders      (order_id, customer_id, order_date, channel, status)
    order_items (order_item_id, order_id, product_id, quantity, unit_price, discount)

The data is generated with a fixed random seed, so every attendee gets an
identical database and the same answers to the same questions.

Usage:
    python data/build_db.py            # writes data/sales.db (overwrites)
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sales.db"
SEED = 42

REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
SEGMENTS = ["Consumer", "Small Business", "Enterprise"]
CHANNELS = ["Web", "Mobile App", "Retail Store", "Phone"]
STATUSES = ["Delivered"] * 85 + ["Returned"] * 6 + ["Cancelled"] * 4 + ["Shipped"] * 5

FIRST = ["Ava", "Liam", "Maya", "Noah", "Priya", "Ethan", "Sofia", "Arjun", "Chloe",
         "Lucas", "Zara", "Owen", "Mei", "Caleb", "Nora", "Ravi", "Isla", "Mateo",
         "Hana", "Elijah", "Leah", "Kai", "Amara", "Jonah", "Grace"]
LAST = ["Patel", "Nguyen", "Smith", "Garcia", "Kim", "Johnson", "Chen", "Brown",
        "Singh", "Lopez", "Miller", "Davis", "Shah", "Wilson", "Moore", "Clark"]

PRODUCTS = [
    # (name, category, price)
    ("Trailhead 2P Tent", "Camping", 249.00),
    ("Ridgeline 4P Tent", "Camping", 399.00),
    ("Down Sleeping Bag 20F", "Camping", 189.00),
    ("Inflatable Sleeping Pad", "Camping", 79.00),
    ("Backpacking Stove", "Camping", 59.00),
    ("Camp Lantern", "Camping", 34.00),
    ("Daypack 24L", "Packs", 89.00),
    ("Overnight Pack 45L", "Packs", 179.00),
    ("Expedition Pack 65L", "Packs", 279.00),
    ("Hydration Bladder 2L", "Packs", 29.00),
    ("Rain Shell Jacket", "Apparel", 149.00),
    ("Fleece Pullover", "Apparel", 69.00),
    ("Merino Base Layer", "Apparel", 85.00),
    ("Hiking Pants", "Apparel", 74.00),
    ("Wool Hiking Socks", "Apparel", 22.00),
    ("Trail Running Shoes", "Footwear", 139.00),
    ("Waterproof Hiking Boots", "Footwear", 199.00),
    ("Camp Sandals", "Footwear", 49.00),
    ("Trekking Poles", "Accessories", 99.00),
    ("Headlamp 400lm", "Accessories", 39.00),
    ("Water Filter", "Accessories", 44.00),
    ("Insulated Bottle 32oz", "Accessories", 35.00),
    ("First Aid Kit", "Accessories", 27.00),
    ("GPS Watch", "Electronics", 329.00),
    ("Solar Power Bank", "Electronics", 64.00),
    ("Satellite Messenger", "Electronics", 299.00),
]

START = date(2025, 1, 1)
END = date(2026, 6, 30)


def build(db_path: Path = DB_PATH) -> Path:
    rng = random.Random(SEED)
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE customers (
            customer_id  INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            region       TEXT NOT NULL,
            segment      TEXT NOT NULL,
            signup_date  TEXT NOT NULL          -- ISO date
        );
        CREATE TABLE products (
            product_id   INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            category     TEXT NOT NULL,
            unit_price   REAL NOT NULL          -- list price, USD
        );
        CREATE TABLE orders (
            order_id     INTEGER PRIMARY KEY,
            customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
            order_date   TEXT NOT NULL,         -- ISO date
            channel      TEXT NOT NULL,
            status       TEXT NOT NULL
        );
        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id      INTEGER NOT NULL REFERENCES orders(order_id),
            product_id    INTEGER NOT NULL REFERENCES products(product_id),
            quantity      INTEGER NOT NULL,
            unit_price    REAL NOT NULL,        -- price actually charged per unit, USD
            discount      REAL NOT NULL         -- fraction, 0.0-0.3
        );
        CREATE INDEX idx_orders_customer ON orders(customer_id);
        CREATE INDEX idx_orders_date ON orders(order_date);
        CREATE INDEX idx_items_order ON order_items(order_id);
        """
    )

    # Customers: regions are deliberately uneven so the data has a story.
    region_weights = [30, 22, 18, 12, 18]
    customers = []
    for cid in range(1, 301):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        region = rng.choices(REGIONS, weights=region_weights)[0]
        segment = rng.choices(SEGMENTS, weights=[70, 22, 8])[0]
        signup = START - timedelta(days=rng.randint(0, 700))
        customers.append((cid, name, region, segment, signup.isoformat()))
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    cur.executemany(
        "INSERT INTO products VALUES (?,?,?,?)",
        [(i, n, c, p) for i, (n, c, p) in enumerate(PRODUCTS, start=1)],
    )

    # Orders: seasonality (spring/summer camping peak, Nov/Dec gift peak).
    month_weight = {1: 5, 2: 5, 3: 7, 4: 9, 5: 11, 6: 12, 7: 11, 8: 9,
                    9: 7, 10: 7, 11: 10, 12: 12}
    days = []
    d = START
    while d <= END:
        days.append(d)
        d += timedelta(days=1)
    day_weights = [month_weight[x.month] for x in days]

    orders, items = [], []
    item_id = 1
    for oid in range(1, 2501):
        cust = rng.choice(customers)
        odate = rng.choices(days, weights=day_weights)[0]
        channel = rng.choices(CHANNELS, weights=[45, 30, 18, 7])[0]
        status = rng.choice(STATUSES)
        orders.append((oid, cust[0], odate.isoformat(), channel, status))
        big_buyer = cust[3] != "Consumer"
        for _ in range(rng.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]):
            pid = rng.randint(1, len(PRODUCTS))
            price = PRODUCTS[pid - 1][2]
            qty = rng.choices([1, 2, 3, 5, 10], weights=[70, 18, 7, 3, 2] if not big_buyer
                              else [35, 25, 15, 15, 10])[0]
            discount = rng.choices([0.0, 0.1, 0.2, 0.3], weights=[70, 18, 9, 3])[0]
            items.append((item_id, oid, pid, qty, price, discount))
            item_id += 1

    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
    cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?,?)", items)
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    path = build()
    con = sqlite3.connect(path)
    for t in ["customers", "products", "orders", "order_items"]:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t:12s} {n:6d} rows")
    con.close()
    print(f"Wrote {path}")
