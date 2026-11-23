"""Bronze raw facts, Silver validated sales, Gold leakage-safe daily features."""

import sqlite3
from datetime import date
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    lead_time_days INTEGER NOT NULL CHECK(lead_time_days > 0)
);
CREATE TABLE IF NOT EXISTS raw_sales (
    record_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL,
    sku TEXT NOT NULL REFERENCES products(sku),
    day TEXT NOT NULL,
    units_sold INTEGER NOT NULL CHECK(units_sold >= 0),
    promo_planned INTEGER NOT NULL CHECK(promo_planned IN (0,1)),
    price_eur REAL NOT NULL CHECK(price_eur > 0),
    opening_stock INTEGER NOT NULL CHECK(opening_stock >= 0),
    UNIQUE(store_id,sku,day)
);
CREATE TABLE IF NOT EXISTS daily_features (
    store_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    day TEXT NOT NULL,
    units_sold INTEGER NOT NULL,
    promo_planned INTEGER NOT NULL,
    price_eur REAL NOT NULL,
    is_stockout INTEGER NOT NULL,
    lag_1 REAL,
    lag_7 REAL,
    rolling_7 REAL,
    weekday INTEGER NOT NULL,
    PRIMARY KEY(store_id,sku,day)
);
"""

MART_SQL = """
WITH lagged AS (
    SELECT store_id, sku, day, units_sold, promo_planned, price_eur,
           CASE WHEN units_sold >= opening_stock THEN 1 ELSE 0 END AS is_stockout,
           LAG(units_sold,1) OVER seq AS lag_1,
           LAG(units_sold,7) OVER seq AS lag_7,
           AVG(units_sold) OVER (PARTITION BY store_id,sku ORDER BY day
                ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS rolling_7
    FROM raw_sales
    WINDOW seq AS (PARTITION BY store_id,sku ORDER BY day)
)
INSERT INTO daily_features(store_id,sku,day,units_sold,promo_planned,price_eur,
                           is_stockout,lag_1,lag_7,rolling_7,weekday)
SELECT store_id,sku,day,units_sold,promo_planned,price_eur,is_stockout,
       lag_1,lag_7,rolling_7,CAST(strftime('%w',day) AS INTEGER)
FROM lagged
"""


def connect(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(DDL)
    return db


def load_product(db: sqlite3.Connection, sku: str, category: str, lead_time_days: int):
    if lead_time_days < 1 or not sku or not category:
        raise ValueError("Lead time must be positive")
    with db:
        db.execute("INSERT OR IGNORE INTO products VALUES (?,?,?)",
                   (sku, category, lead_time_days))
        stored = db.execute(
            "SELECT category,lead_time_days FROM products WHERE sku=?", (sku,)).fetchone()
        if tuple(stored) != (category, lead_time_days):
            raise ValueError("Conflicting product definition")


def load_sale(db: sqlite3.Connection, record_id: str, store_id: str, sku: str, day: date,
              units_sold: int, promo_planned: int, price_eur: float, opening_stock: int) -> bool:
    if units_sold < 0 or price_eur <= 0 or opening_stock < 0 or promo_planned not in (0, 1):
        raise ValueError("Invalid sales contract")
    if units_sold > opening_stock:
        raise ValueError("Observed sales cannot exceed stock in the local single-day model")
    with db:
        cursor = db.execute(
            """INSERT OR IGNORE INTO raw_sales
               VALUES (?,?,?,?,?,?,?,?)""",
            (record_id, store_id, sku, day.isoformat(), units_sold,
             promo_planned, price_eur, opening_stock))
    if cursor.rowcount != 1:
        existing = db.execute(
            """SELECT record_id,store_id,sku,day,units_sold,promo_planned,price_eur,opening_stock
               FROM raw_sales WHERE record_id=? OR (store_id=? AND sku=? AND day=?)""",
            (record_id, store_id, sku, day.isoformat())).fetchone()
        requested = (record_id, store_id, sku, day.isoformat(), units_sold,
                     promo_planned, price_eur, opening_stock)
        if existing is None or tuple(existing) != requested:
            raise ValueError("Conflicting identity or payload for sales fact")
    return cursor.rowcount == 1


def quality_report(db: sqlite3.Connection) -> dict:
    """Critical integrity assertions before features or decisions are published."""
    count = db.execute("SELECT COUNT(*) FROM raw_sales").fetchone()[0]
    gaps = db.execute(
        """WITH s AS (
          SELECT store_id,sku,day,LAG(day) OVER (
             PARTITION BY store_id,sku ORDER BY day) AS prior
          FROM raw_sales
        ) SELECT COUNT(*) FROM s WHERE prior IS NOT NULL
          AND CAST(julianday(day)-julianday(prior) AS INTEGER) <> 1"""
    ).fetchone()[0]
    stockouts = db.execute(
        "SELECT COUNT(*) FROM raw_sales WHERE units_sold=opening_stock").fetchone()[0]
    return {"raw_rows": count, "date_gaps": gaps, "stockout_rows": stockouts,
            "quality_pass": count > 0 and gaps == 0}


def materialize_features(db: sqlite3.Connection) -> int:
    """Fully recompute the local mart. A production warehouse would do partitioned MERGE."""
    report = quality_report(db)
    if not report["quality_pass"]:
        raise ValueError(f"Quality gate failed: {report}")
    with db:
        db.execute("DELETE FROM daily_features")
        db.execute(MART_SQL)
    return db.execute("SELECT COUNT(*) FROM daily_features").fetchone()[0]
