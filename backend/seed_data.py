from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.auth import seed_branches_and_demo_users
from backend.database import get_connection, initialize_database

# (product_code, product_name, category, expiry_tier, default_units_per_box)
PRODUCT_CATALOG: List[Tuple[str, str, str, str, int]] = [
    # E01 — 2 to 7 Days
    ("E01-MKT-01", "Pasteurized pouch milk (500ml)", "Dairy products", "E01", 20),
    ("E01-MKT-02", "Pasteurized PET milk 1L", "Dairy products", "E01", 12),
    ("E01-BRD-01", "Bread (sealed loaf)", "Eatables", "E01", 10),
    ("E01-BRD-02", "Packaged cake/brownie", "Packaged foods", "E01", 12),
    ("E01-DRY-01", "Paneer (vacuum sealed 200g)", "Dairy products", "E01", 20),
    ("E01-DRY-02", "Curd/Dahi (cup-packed 400g)", "Dairy products", "E01", 16),
    ("E01-DRY-03", "Rasgulla/Gulab Jamun (jar)", "Eatables", "E01", 12),
    # E02 — 1 to 4 Weeks
    ("E02-DRY-01", "Buttermilk (packed 200ml)", "Beverages", "E02", 24),
    ("E02-DRY-02", "Yogurt/Lassi (sealed cup)", "Dairy products", "E02", 20),
    ("E02-JUC-01", "Fresh juice (chilled, sealed 300ml)", "Beverages", "E02", 12),
    ("E02-SWE-01", "Peda/Laddu (pack)", "Eatables", "E02", 15),
    ("E02-SWE-02", "Kheer (cup-packed)", "Eatables", "E02", 15),
    ("E02-SWE-03", "Barfi (sealed box)", "Eatables", "E02", 10),
    # E03 — 1 to 3 Months
    ("E03-SNK-01", "Potato chips (sealed 52g)", "Packaged foods", "E03", 40),
    ("E03-SNK-02", "Namkeen/Mixture (sealed 200g)", "Packaged foods", "E03", 25),
    ("E03-BIS-01", "Cookies (packaged 200g)", "Packaged foods", "E03", 30),
    ("E03-BIS-02", "Marie biscuits (pack 300g)", "Packaged foods", "E03", 50),
    ("E03-DRV-01", "Carbonated drink (bottle 750ml)", "Beverages", "E03", 12),
    ("E03-MKT-01", "UHT milk (Tetra Pak 1L)", "Dairy products", "E03", 12),
    ("E03-MKT-02", "Flavoured UHT milk (Tetra Pak)", "Beverages", "E03", 24),
    # E04 — 6 Months to 1 Year
    ("E04-RCE-01", "Rice (sealed 5kg bag)", "Pulses", "E04", 4),
    ("E04-FLR-01", "Whole wheat atta (sealed 1kg)", "Eatables", "E04", 10),
    ("E04-FLR-02", "Maida (sealed 1kg)", "Eatables", "E04", 10),
    ("E04-JUC-01", "Shelf-stable juice (carton 1L)", "Beverages", "E04", 12),
    ("E04-PWD-01", "Powdered milk SMP (sealed 500g)", "Dairy products", "E04", 12),
    ("E04-NDL-01", "Instant noodles (pack)", "Packaged foods", "E04", 48),
    ("E04-NDL-02", "Pasta (sealed 500g)", "Packaged foods", "E04", 20),
    ("E04-BIS-01", "Parle-G (300g)", "Packaged foods", "E04", 50),
    ("E04-CSM-01", "Herbal Face Wash (100ml)", "Cosmetics", "E04", 24),
    # E05 — 1 to 3+ Years
    ("E05-CAN-01", "Canned pineapple (400g)", "Packaged foods", "E05", 12),
    ("E05-CAN-02", "Canned tuna/sardines", "Packaged foods", "E05", 12),
    ("E05-CAN-03", "Canned beans/pulses (400g)", "Pulses", "E05", 12),
    ("E05-SPC-01", "Turmeric (sealed 100g)", "Eatables", "E05", 25),
    ("E05-SPC-02", "Cumin (sealed 100g)", "Eatables", "E05", 25),
    ("E05-SPC-03", "Baking powder/soda (sealed 200g)", "Eatables", "E05", 20),
    ("E05-SND-01", "Hard candy/Toffee (sealed 100g)", "Packaged foods", "E05", 40),
    ("E05-SND-02", "Jaggery cubes (sealed 250g)", "Eatables", "E05", 20),
    ("E05-CSM-01", "Moisturizer Cream (100g)", "Cosmetics", "E05", 20),
]

# Undirected Mangalore branch distances (km, estimated_minutes)
BRANCH_DISTANCES: Dict[Tuple[str, str], Tuple[float, int]] = {
    ("HK", "KD"): (4.2, 18),
    ("HK", "BJ"): (4.8, 20),
    ("HK", "KK"): (3.5, 15),
    ("HK", "UR"): (5.6, 24),
    ("KD", "BJ"): (2.9, 12),
    ("KD", "KK"): (3.8, 16),
    ("KD", "UR"): (4.1, 18),
    ("BJ", "KK"): (4.5, 19),
    ("BJ", "UR"): (2.8, 12),
    ("KK", "UR"): (6.4, 26),
}

GODOWN_ROUTES: Dict[str, Tuple[float, int]] = {
    "HK": (11.5, 35),
    "KD": (9.8, 30),
    "BJ": (8.6, 26),
    "KK": (10.2, 32),
    "UR": (9.4, 28),
}

MANUFACTURER_ROUTES: Dict[str, Tuple[float, int]] = {
    "HK": (18.0, 50),
    "KD": (16.5, 45),
    "BJ": (15.2, 42),
    "KK": (17.0, 48),
    "UR": (16.0, 44),
}


def _seed_logistics(conn) -> None:
    cost_per_km = 14.0
    handling_fee = 45.0

    for (b1, b2), (dist, mins) in BRANCH_DISTANCES.items():
        total_cost = round(dist * cost_per_km + handling_fee, 2)
        for src, dst in [(b1, b2), (b2, b1)]:
            conn.execute(
                """
                INSERT OR IGNORE INTO branch_logistics (
                    from_location, to_location, location_type,
                    distance_km, estimated_minutes, vehicle_capacity_units,
                    transport_cost, cost_per_km
                )
                VALUES (?, ?, 'inter_branch', ?, ?, 800, ?, ?);
                """,
                (src, dst, dist, mins, total_cost, cost_per_km),
            )

    for branch, (dist, mins) in GODOWN_ROUTES.items():
        total_cost = round(dist * 16.0 + 120.0, 2)
        conn.execute(
            """
            INSERT OR IGNORE INTO branch_logistics (
                from_location, to_location, location_type,
                distance_km, estimated_minutes, vehicle_capacity_units,
                transport_cost, cost_per_km
            )
            VALUES ('GODOWN', ?, 'godown_supply', ?, ?, 2500, ?, 16.0);
            """,
            (branch, dist, mins, total_cost),
        )

    for branch, (dist, mins) in MANUFACTURER_ROUTES.items():
        total_cost = round(dist * 18.0 + 150.0, 2)
        conn.execute(
            """
            INSERT OR IGNORE INTO branch_logistics (
                from_location, to_location, location_type,
                distance_km, estimated_minutes, vehicle_capacity_units,
                transport_cost, cost_per_km
            )
            VALUES (?, 'MANUFACTURER', 'manufacturer_return', ?, ?, 1500, ?, 18.0);
            """,
            (branch, dist, mins, total_cost),
        )


def _seed_products_and_return_rules(conn) -> None:
    for code, name, category, tier, units_per_box in PRODUCT_CATALOG:
        conn.execute(
            """
            INSERT OR IGNORE INTO products (
                product_code, product_name, category,
                expiry_tier, default_units_per_box
            )
            VALUES (?, ?, ?, ?, ?);
            """,
            (code, name, category, tier, units_per_box),
        )

        if tier == "E01":
            rule = ("Not Eligible", 0, "Perishable cold-chain item", 0.0, "No distributor buyback")
        elif tier == "E02":
            rule = ("Requires Verification", 5, "Unopened chilled packs", 40.0, "Subject to distributor inspection")
        elif code in {"E04-CSM-01", "E05-CSM-01", "E04-BIS-01", "E03-BIS-02", "E04-NDL-01", "E05-CAN-03"}:
            rule = ("Eligible", 7, "Unopened sealed outer cartons", 70.0, "Standard distributor credit note")
        else:
            rule = ("Eligible", 10, "Original undamaged packaging", 55.0, "Standard return policy")

        conn.execute(
            """
            INSERT OR IGNORE INTO distributor_return_rules (
                product_code, eligible, return_deadline_days,
                accepted_condition, refund_percentage, notes
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (code, *rule),
        )


def _seed_demo_batches_and_sales(conn) -> None:
    existing_batches = conn.execute(
        "SELECT COUNT(*) AS cnt FROM inventory_batches;"
    ).fetchone()["cnt"]
    if existing_batches > 0:
        return

    today = date.today()

    # (batch_id, product_code, branch, boxes, units_per_box, days_offset, unit_cost, selling_price)
    demo_batches = [
        ("BATCH-HK-001", "E03-BIS-02", "HK", 4, 50, 14, 22.0, 35.0),
        ("BATCH-HK-002", "E01-DRY-01", "HK", 3, 20, 2, 72.0, 95.0),
        ("BATCH-HK-003", "E04-BIS-01", "HK", 5, 50, 180, 18.0, 28.0),
        ("BATCH-KD-001", "E02-JUC-01", "KD", 4, 12, 6, 38.0, 55.0),
        ("BATCH-KD-002", "E04-CSM-01", "KD", 3, 24, 22, 95.0, 145.0),
        ("BATCH-BJ-001", "E03-SNK-02", "BJ", 4, 25, 11, 40.0, 60.0),
        ("BATCH-BJ-002", "E01-BRD-02", "BJ", 3, 12, -2, 28.0, 45.0),  # Expired sample
        ("BATCH-KK-001", "E04-FLR-01", "KK", 6, 10, 18, 42.0, 58.0),
        ("BATCH-KK-002", "E02-SWE-01", "KK", 3, 15, 3, 65.0, 95.0),
        ("BATCH-UR-001", "E03-BIS-02", "UR", 5, 50, 12, 22.0, 35.0),  # Low UR demand -> Transfer candidate
        ("BATCH-UR-002", "E04-NDL-01", "UR", 3, 48, 25, 11.0, 15.0),
        ("BATCH-UR-003", "E05-CAN-03", "UR", 4, 12, 20, 68.0, 98.0),
    ]

    for batch_id, pcode, branch, boxes, upb, days_off, cost, price in demo_batches:
        qty = boxes * upb
        exp_date = (today + timedelta(days=days_off)).isoformat()
        conn.execute(
            """
            INSERT INTO inventory_batches (
                batch_id, product_code, branch_code, boxes, units_per_box,
                quantity, expiry_date, unit_cost, selling_price, is_demo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
            """,
            (batch_id, pcode, branch, boxes, upb, qty, exp_date, cost, price),
        )

    # Reproducible 30-day sales history ending yesterday (no future dates)
    rng = np.random.default_rng(42)
    demand_profiles: Dict[Tuple[str, str], float] = {
        ("E03-BIS-02", "HK"): 22.0,
        ("E03-BIS-02", "KD"): 24.0,
        ("E03-BIS-02", "BJ"): 14.0,
        ("E03-BIS-02", "KK"): 12.0,
        ("E03-BIS-02", "UR"): 3.0,   # Slow at Urwa, high at HK/KD!
        ("E01-DRY-01", "HK"): 12.0,
        ("E04-BIS-01", "HK"): 16.0,
        ("E04-BIS-01", "KD"): 15.0,
        ("E02-JUC-01", "KD"): 5.0,
        ("E04-CSM-01", "KD"): 2.0,
        ("E03-SNK-02", "BJ"): 4.0,
        ("E04-FLR-01", "KK"): 3.0,
        ("E02-SWE-01", "KK"): 8.0,
        ("E04-NDL-01", "UR"): 6.0,
        # Intentionally omit ("E05-CAN-03", "UR") to test cross-branch/fallback logic!
        ("E05-CAN-03", "HK"): 4.0,
    }

    sale_times = ["10:30:00", "13:15:00", "17:45:00", "20:10:00"]
    for day_offset in range(1, 31):
        sale_day = (today - timedelta(days=day_offset)).isoformat()
        for (pcode, branch), mean_demand in demand_profiles.items():
            units = int(rng.poisson(mean_demand))
            stime = sale_times[day_offset % len(sale_times)]
            conn.execute(
                """
                INSERT INTO sales_history (
                    product_code, branch_code, sale_date, sale_time,
                    units_sold, source, is_demo
                )
                VALUES (?, ?, ?, ?, ?, 'demo', 1);
                """,
                (pcode, branch, sale_day, stime, units),
            )


def seed_all_demo_data(db_path: Optional[Path] = None) -> None:
    """Populate branches, demo users, product catalog, logistics, rules, and demo data."""
    initialize_database(db_path)
    seed_branches_and_demo_users(db_path)

    with get_connection(db_path) as conn:
        _seed_logistics(conn)
        _seed_products_and_return_rules(conn)
        _seed_demo_batches_and_sales(conn)


if __name__ == "__main__":
    seed_all_demo_data()
    with get_connection() as conn:
        p_cnt = conn.execute("SELECT COUNT(*) FROM products;").fetchone()[0]
        l_cnt = conn.execute("SELECT COUNT(*) FROM branch_logistics;").fetchone()[0]
        b_cnt = conn.execute("SELECT COUNT(*) FROM inventory_batches;").fetchone()[0]
        s_cnt = conn.execute("SELECT COUNT(*) FROM sales_history;").fetchone()[0]
    print(f"Seeded -> Products: {p_cnt}, Logistics: {l_cnt}, Batches: {b_cnt}, Sales: {s_cnt}")