import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "inventory.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys and dict-like row access."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    """Safely add a column during upgrades without deleting existing data."""
    existing_cols = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    }
    if column_name not in existing_cols:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition};"
        )


def log_audit(
    conn: sqlite3.Connection,
    username: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: str = "",
) -> None:
    """Record an audit trail entry inside an active database connection."""
    conn.execute(
        """
        INSERT INTO audit_log (username, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?);
        """,
        (username, action, entity_type, str(entity_id), details),
    )


def initialize_database(db_path: Optional[Path] = None) -> Path:
    """Create all tables, constraints, and indexes if they do not exist."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    with get_connection(target_path) as conn:
        # 1. Branches
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS branches (
                branch_code TEXT PRIMARY KEY,
                branch_name TEXT UNIQUE NOT NULL,
                storage_capacity INTEGER NOT NULL DEFAULT 5000
                    CHECK (storage_capacity >= 0)
            );
            """
        )

        # 2. Users (1 Admin + 5 Branch Managers)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'manager')),
                branch_code TEXT REFERENCES branches(branch_code),
                is_demo INTEGER NOT NULL DEFAULT 1 CHECK (is_demo IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    (role = 'admin' AND branch_code IS NULL)
                    OR (role = 'manager' AND branch_code IS NOT NULL)
                )
            );
            """
        )

        # 3. Shared Product Catalog (Product Code reusable across branches)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_code TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL CHECK (
                    category IN (
                        'Eatables', 'Dairy products', 'Cosmetics',
                        'Pulses', 'Packaged foods', 'Beverages'
                    )
                ),
                expiry_tier TEXT NOT NULL CHECK (
                    expiry_tier IN ('E01', 'E02', 'E03', 'E04', 'E05')
                ),
                default_units_per_box INTEGER NOT NULL DEFAULT 1
                    CHECK (default_units_per_box > 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 4. Inventory Batches (Unique Batch ID, linked to Product Code & Branch)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT UNIQUE NOT NULL,
                product_code TEXT NOT NULL REFERENCES products(product_code),
                branch_code TEXT NOT NULL REFERENCES branches(branch_code),
                boxes INTEGER NOT NULL DEFAULT 1 CHECK (boxes >= 0),
                units_per_box INTEGER NOT NULL DEFAULT 1 CHECK (units_per_box > 0),
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                expiry_date TEXT NOT NULL,
                unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
                selling_price REAL NOT NULL CHECK (selling_price >= 0),
                date_added TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1))
            );
            """
        )

        # 5. Sales History (with date + time + demo marker)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL REFERENCES products(product_code),
                branch_code TEXT NOT NULL REFERENCES branches(branch_code),
                sale_date TEXT NOT NULL,
                sale_time TEXT NOT NULL DEFAULT '12:00:00',
                units_sold INTEGER NOT NULL CHECK (units_sold >= 0),
                source TEXT NOT NULL DEFAULT 'manual'
                    CHECK (source IN ('manual', 'csv_upload', 'demo')),
                is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 6. Branch & Godown/Manufacturer Logistics Log
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS branch_logistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_location TEXT NOT NULL,
                to_location TEXT NOT NULL,
                location_type TEXT NOT NULL CHECK (
                    location_type IN (
                        'inter_branch', 'godown_supply', 'manufacturer_return'
                    )
                ),
                distance_km REAL NOT NULL CHECK (distance_km >= 0),
                estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes >= 0),
                vehicle_capacity_units INTEGER NOT NULL
                    CHECK (vehicle_capacity_units > 0),
                transport_cost REAL NOT NULL CHECK (transport_cost >= 0),
                cost_per_km REAL NOT NULL DEFAULT 12.0 CHECK (cost_per_km >= 0),
                UNIQUE (from_location, to_location, location_type)
            );
            """
        )

        # 7. Distributor Return Rules
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS distributor_return_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT UNIQUE NOT NULL REFERENCES products(product_code),
                eligible TEXT NOT NULL CHECK (
                    eligible IN ('Eligible', 'Not Eligible', 'Requires Verification')
                ),
                return_deadline_days INTEGER NOT NULL DEFAULT 0
                    CHECK (return_deadline_days >= 0),
                accepted_condition TEXT NOT NULL,
                refund_percentage REAL NOT NULL DEFAULT 0.0
                    CHECK (refund_percentage >= 0 AND refund_percentage <= 100),
                notes TEXT DEFAULT ''
            );
            """
        )

        # 8. Transfer Requests (Manager submits; Admin sets destination_branch)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transfer_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL REFERENCES inventory_batches(batch_id),
                product_code TEXT NOT NULL REFERENCES products(product_code),
                source_branch TEXT NOT NULL REFERENCES branches(branch_code),
                destination_branch TEXT REFERENCES branches(branch_code),
                requested_quantity INTEGER NOT NULL CHECK (requested_quantity > 0),
                reason TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Pending'
                    CHECK (status IN ('Pending', 'Approved', 'Rejected')),
                requested_by TEXT NOT NULL,
                admin_note TEXT DEFAULT '',
                reviewed_by TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT
            );
            """
        )

        # 9. Transfer Transactions (Atomic execution log)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transfer_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL REFERENCES transfer_requests(id),
                source_batch_id TEXT NOT NULL REFERENCES inventory_batches(batch_id),
                destination_batch_id TEXT NOT NULL REFERENCES inventory_batches(batch_id),
                product_code TEXT NOT NULL REFERENCES products(product_code),
                from_branch TEXT NOT NULL REFERENCES branches(branch_code),
                to_branch TEXT NOT NULL REFERENCES branches(branch_code),
                quantity_transferred INTEGER NOT NULL CHECK (quantity_transferred > 0),
                transport_cost REAL NOT NULL DEFAULT 0 CHECK (transport_cost >= 0),
                approved_by TEXT NOT NULL,
                transferred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 10. Recovery Analysis History
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL REFERENCES inventory_batches(batch_id),
                recommended_action TEXT NOT NULL,
                destination_branch TEXT,
                estimated_units_sold REAL NOT NULL,
                estimated_unsold_units REAL NOT NULL,
                expected_recovery_value REAL NOT NULL,
                risk_level TEXT NOT NULL,
                analyzed_by TEXT NOT NULL,
                analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 11. Audit Log
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Safe future-proof migration checks (no-ops on fresh DB)
        ensure_column(conn, "inventory_batches", "is_demo", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "sales_history", "sale_time", "TEXT NOT NULL DEFAULT '12:00:00'")

        # Performance indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_branch ON inventory_batches(branch_code);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_product ON inventory_batches(product_code);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_expiry ON inventory_batches(expiry_date);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sales_lookup ON sales_history(product_code, branch_code, sale_date);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transfer_status ON transfer_requests(status);"
        )

    return target_path


if __name__ == "__main__":
    db_file = initialize_database()
    print(f"Database initialized at: {db_file}")