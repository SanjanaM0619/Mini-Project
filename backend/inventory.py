from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.auth import assert_branch_access, authenticate_user
from backend.database import get_connection, log_audit

VALID_CATEGORIES = {
    "Eatables",
    "Dairy products",
    "Cosmetics",
    "Pulses",
    "Packaged foods",
    "Beverages",
}
VALID_TIERS = {"E01", "E02", "E03", "E04", "E05"}


def classify_expiry(days_left: int) -> str:
    """Return clear expiry status label from remaining shelf-life days."""
    if days_left < 0:
        return "Expired"
    if days_left <= 3:
        return "Critical (<=3d)"
    if days_left <= 30:
        return "At-Risk (4-30d)"
    return "Safe (>30d)"


def resolve_expiry_date(
    expiry_date: Optional[str] = None,
    days_left: Optional[int] = None,
) -> str:
    """Validate expiry_date (YYYY-MM-DD) or convert days_left into ISO date."""
    if expiry_date:
        parsed = date.fromisoformat(str(expiry_date).strip())
        return parsed.isoformat()
    if days_left is not None:
        days_int = int(days_left)
        return (date.today() + timedelta(days=days_int)).isoformat()
    raise ValueError("Provide either a valid expiry_date or days_left.")


def get_all_products(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return all products from the shared catalog."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT product_code, product_name, category,
                   expiry_tier, default_units_per_box
            FROM products
            ORDER BY expiry_tier, product_code;
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_product_by_code(
    product_code: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch a single product by its shared product_code."""
    clean_code = (product_code or "").strip().upper()
    if not clean_code:
        return None
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE UPPER(product_code) = ?;",
            (clean_code,),
        ).fetchone()
        return dict(row) if row else None


def create_product(
    product_code: str,
    product_name: str,
    category: str,
    expiry_tier: str,
    default_units_per_box: int = 1,
    username: str = "system",
    db_path: Optional[Path] = None,
) -> None:
    """Create a new product in the shared catalog after validation."""
    code = (product_code or "").strip().upper()
    name = (product_name or "").strip()
    if not code or not name:
        raise ValueError("Product Code and Product Name are required.")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {category}")
    if expiry_tier not in VALID_TIERS:
        raise ValueError(f"Invalid expiry tier: {expiry_tier}")
    if int(default_units_per_box) <= 0:
        raise ValueError("Default units per box must be positive.")

    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT 1 FROM products WHERE UPPER(product_code) = ?;",
            (code,),
        ).fetchone()
        if existing:
            raise ValueError(f"Product Code '{code}' already exists.")

        conn.execute(
            """
            INSERT INTO products (
                product_code, product_name, category,
                expiry_tier, default_units_per_box
            )
            VALUES (?, ?, ?, ?, ?);
            """,
            (code, name, category, expiry_tier, int(default_units_per_box)),
        )
        log_audit(conn, username, "CREATE_PRODUCT", "product", code, name)


def add_batch(
    user: Dict[str, Any],
    batch_id: str,
    product_code: str,
    branch_code: str,
    quantity: Optional[int] = None,
    boxes: Optional[int] = None,
    units_per_box: int = 1,
    expiry_date: Optional[str] = None,
    days_left: Optional[int] = None,
    unit_cost: float = 0.0,
    selling_price: float = 0.0,
    is_demo: int = 0,
    db_path: Optional[Path] = None,
) -> str:
    """Add a new unique batch to a branch with strict validation and RBAC."""
    assert_branch_access(user, branch_code)

    clean_batch_id = (batch_id or "").strip().upper()
    clean_product_code = (product_code or "").strip().upper()
    if not clean_batch_id:
        raise ValueError("Batch ID is required.")
    if not clean_product_code:
        raise ValueError("Product Code is required.")

    if boxes is not None and units_per_box is not None and quantity is None:
        if int(boxes) <= 0 or int(units_per_box) <= 0:
            raise ValueError("Boxes and units per box must be positive.")
        total_qty = int(boxes) * int(units_per_box)
        saved_boxes = int(boxes)
        saved_upb = int(units_per_box)
    else:
        total_qty = int(quantity or 0)
        saved_upb = max(1, int(units_per_box or 1))
        saved_boxes = max(1, total_qty // saved_upb) if total_qty > 0 else 0

    if total_qty <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if float(unit_cost) < 0 or float(selling_price) < 0:
        raise ValueError("Unit cost and selling price cannot be negative.")

    iso_expiry = resolve_expiry_date(expiry_date=expiry_date, days_left=days_left)

    with get_connection(db_path) as conn:
        prod = conn.execute(
            "SELECT product_name FROM products WHERE UPPER(product_code) = ?;",
            (clean_product_code,),
        ).fetchone()
        if prod is None:
            raise ValueError(f"Unknown Product Code '{clean_product_code}'.")

        dup = conn.execute(
            "SELECT 1 FROM inventory_batches WHERE UPPER(batch_id) = ?;",
            (clean_batch_id,),
        ).fetchone()
        if dup:
            raise ValueError(f"Batch ID '{clean_batch_id}' already exists.")

        conn.execute(
            """
            INSERT INTO inventory_batches (
                batch_id, product_code, branch_code, boxes, units_per_box,
                quantity, expiry_date, unit_cost, selling_price, is_demo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                clean_batch_id,
                clean_product_code,
                branch_code,
                saved_boxes,
                saved_upb,
                total_qty,
                iso_expiry,
                float(unit_cost),
                float(selling_price),
                int(is_demo),
            ),
        )
        log_audit(
            conn,
            username=str(user.get("username", "system")),
            action="ADD_BATCH",
            entity_type="inventory_batch",
            entity_id=clean_batch_id,
            details=f"{clean_product_code} @ {branch_code}, qty={total_qty}, exp={iso_expiry}",
        )

    return clean_batch_id


def update_batch(
    user: Dict[str, Any],
    batch_id: str,
    quantity: Optional[int] = None,
    unit_cost: Optional[float] = None,
    selling_price: Optional[float] = None,
    expiry_date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Edit batch quantity, prices, or expiry date with RBAC and validation."""
    clean_batch_id = (batch_id or "").strip().upper()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM inventory_batches WHERE UPPER(batch_id) = ?;",
            (clean_batch_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Batch '{clean_batch_id}' not found.")

        assert_branch_access(user, row["branch_code"])

        new_qty = int(row["quantity"]) if quantity is None else int(quantity)
        new_cost = float(row["unit_cost"]) if unit_cost is None else float(unit_cost)
        new_price = float(row["selling_price"]) if selling_price is None else float(selling_price)
        new_exp = (
            row["expiry_date"]
            if expiry_date is None
            else resolve_expiry_date(expiry_date=expiry_date)
        )

        if new_qty < 0:
            raise ValueError("Quantity cannot be negative.")
        if new_cost < 0 or new_price < 0:
            raise ValueError("Prices cannot be negative.")

        conn.execute(
            """
            UPDATE inventory_batches
            SET quantity = ?,
                unit_cost = ?,
                selling_price = ?,
                expiry_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE UPPER(batch_id) = ?;
            """,
            (new_qty, new_cost, new_price, new_exp, clean_batch_id),
        )
        log_audit(
            conn,
            username=str(user.get("username", "system")),
            action="UPDATE_BATCH",
            entity_type="inventory_batch",
            entity_id=clean_batch_id,
            details=f"qty={new_qty}, cost={new_cost}, price={new_price}, exp={new_exp}",
        )


def get_inventory(
    user: Dict[str, Any],
    branch_filter: Optional[str] = None,
    search_query: str = "",
    max_days_left: Optional[int] = None,
    include_zero_qty: bool = True,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Fetch role-scoped inventory batches with live days_left and status."""
    role = user.get("role")
    if role == "manager":
        target_branch = user.get("branch_code")
    elif branch_filter and branch_filter != "ALL":
        target_branch = branch_filter
    else:
        target_branch = None

    query = """
        SELECT b.id, b.batch_id, b.product_code, p.product_name, p.category,
               p.expiry_tier, b.branch_code, br.branch_name,
               b.boxes, b.units_per_box, b.quantity, b.expiry_date,
               b.unit_cost, b.selling_price, b.date_added, b.is_demo
        FROM inventory_batches b
        JOIN products p ON b.product_code = p.product_code
        JOIN branches br ON b.branch_code = br.branch_code
        WHERE 1 = 1
    """
    params: List[Any] = []

    if target_branch:
        query += " AND b.branch_code = ?"
        params.append(target_branch)
    if not include_zero_qty:
        query += " AND b.quantity > 0"

    query += " ORDER BY b.expiry_date ASC, b.batch_id ASC;"

    today = date.today()
    needle = (search_query or "").strip().casefold()
    results: List[Dict[str, Any]] = []

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    for row in rows:
        item = dict(row)
        exp_date = date.fromisoformat(item["expiry_date"])
        days_left = (exp_date - today).days
        item["days_left"] = days_left
        item["expiry_status"] = classify_expiry(days_left)
        item["branch_sku"] = f"{item['branch_code']}-{item['product_code']}"
        item["stock_value"] = round(item["quantity"] * item["selling_price"], 2)

        if max_days_left is not None and days_left > max_days_left:
            continue

        if needle:
            searchable = " ".join(
                [
                    item["batch_id"],
                    item["product_code"],
                    item["branch_sku"],
                    item["product_name"],
                    item["branch_name"],
                ]
            ).casefold()
            if needle not in searchable:
                continue

        results.append(item)

    return results


def get_expiry_summary(batches: List[Dict[str, Any]]) -> Dict[str, int]:
    """Compute dashboard expiry KPIs from a list of batch dicts."""
    active = [b for b in batches if b["quantity"] > 0]
    at_risk = [b for b in active if 0 <= b["days_left"] <= 30]
    critical = [b for b in active if 0 <= b["days_left"] <= 3]
    expired = [b for b in active if b["days_left"] < 0]

    return {
        "total_batches": len(active),
        "total_units": sum(int(b["quantity"]) for b in active),
        "at_risk_batches": len(at_risk),
        "at_risk_units": sum(int(b["quantity"]) for b in at_risk),
        "critical_batches": len(critical),
        "expired_batches": len(expired),
        "expired_units": sum(int(b["quantity"]) for b in expired),
    }


if __name__ == "__main__":
    admin = authenticate_user("admin", "Admin@123")
    hk_mgr = authenticate_user("hk_manager", "Branch@123")

    all_items = get_inventory(admin)
    hk_items = get_inventory(hk_mgr)
    summary = get_expiry_summary(all_items)

    assert len(all_items) >= 12
    assert all(item["branch_code"] == "HK" for item in hk_items)
    print(f"Inventory check passed! Total active batches: {summary['total_batches']}, At-risk(<=30d): {summary['at_risk_batches']}, Expired: {summary['expired_batches']}")