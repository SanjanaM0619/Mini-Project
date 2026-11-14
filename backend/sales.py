import io
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from backend.auth import assert_branch_access, authenticate_user
from backend.database import get_connection, log_audit
from backend.seed_data import seed_all_demo_data

BRANCH_LOOKUP = {
    "HK": "HK",
    "HAMPANKATTA": "HK",
    "KD": "KD",
    "KADRI": "KD",
    "BJ": "BJ",
    "BEJAI": "BJ",
    "KK": "KK",
    "KANKANADY": "KK",
    "UR": "UR",
    "URWA": "UR",
}


def _normalize_branch(raw_branch: Any) -> str:
    key = str(raw_branch or "").strip().upper()
    if key not in BRANCH_LOOKUP:
        raise ValueError(f"Unknown branch '{raw_branch}'. Use HK, KD, BJ, KK, UR or branch name.")
    return BRANCH_LOOKUP[key]


def _normalize_sale_date_and_time(
    sale_date: Any,
    sale_time: Any = None,
) -> tuple[str, str]:
    parsed_dt = pd.to_datetime(sale_date, errors="coerce")
    if pd.isna(parsed_dt):
        raise ValueError(f"Invalid sales date: '{sale_date}'.")

    clean_date = parsed_dt.date()
    if clean_date > date.today():
        raise ValueError(f"Future sales date '{clean_date.isoformat()}' is not allowed.")

    if sale_time is not None and str(sale_time).strip():
        raw_time = str(sale_time).strip()
        try:
            parsed_time = time.fromisoformat(raw_time)
            clean_time = parsed_time.strftime("%H:%M:%S")
        except ValueError:
            parsed_t = pd.to_datetime(raw_time, errors="coerce")
            if pd.isna(parsed_t):
                raise ValueError(f"Invalid sale time: '{sale_time}'.")
            clean_time = parsed_t.strftime("%H:%M:%S")
    elif parsed_dt.hour != 0 or parsed_dt.minute != 0 or parsed_dt.second != 0:
        clean_time = parsed_dt.strftime("%H:%M:%S")
    else:
        clean_time = "12:00:00"

    return clean_date.isoformat(), clean_time


def _resolve_product_code(conn, raw_code: Any) -> str:
    code = str(raw_code or "").strip().upper()
    if not code:
        raise ValueError("Product Code is required.")

    row = conn.execute(
        "SELECT product_code FROM products WHERE UPPER(product_code) = ?;",
        (code,),
    ).fetchone()
    if row:
        return row["product_code"]

    # Also support branch-prefixed SKU like HK-E04-BIS-01
    if len(code) > 3 and code[:2] in {"HK", "KD", "BJ", "KK", "UR"} and code[2] == "-":
        base_code = code[3:]
        row = conn.execute(
            "SELECT product_code FROM products WHERE UPPER(product_code) = ?;",
            (base_code,),
        ).fetchone()
        if row:
            return row["product_code"]

    raise ValueError(f"Unknown Product Code '{raw_code}'.")


def record_sale(
    user: Dict[str, Any],
    product_code: str,
    branch_code: str,
    sale_date: Union[str, date],
    units_sold: int,
    sale_time: Optional[str] = None,
    source: str = "manual",
    db_path: Optional[Path] = None,
) -> int:
    """Record a single validated sales entry into SQLite."""
    clean_branch = _normalize_branch(branch_code)
    assert_branch_access(user, clean_branch)

    qty = int(units_sold)
    if qty < 0:
        raise ValueError("Units sold cannot be negative.")

    clean_date, clean_time = _normalize_sale_date_and_time(sale_date, sale_time)

    with get_connection(db_path) as conn:
        clean_code = _resolve_product_code(conn, product_code)
        cursor = conn.execute(
            """
            INSERT INTO sales_history (
                product_code, branch_code, sale_date, sale_time,
                units_sold, source, is_demo
            )
            VALUES (?, ?, ?, ?, ?, ?, 0);
            """,
            (clean_code, clean_branch, clean_date, clean_time, qty, source),
        )
        sale_id = int(cursor.lastrowid)
        log_audit(
            conn,
            username=str(user.get("username", "system")),
            action="RECORD_SALE",
            entity_type="sales_history",
            entity_id=str(sale_id),
            details=f"{clean_code} @ {clean_branch}, date={clean_date}, units={qty}",
        )
        return sale_id


def import_sales_file(
    user: Dict[str, Any],
    file_obj: Any,
    filename: str,
    default_branch_code: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Import daily sales records from a CSV or Excel (.xlsx/.xls) file."""
    lower_name = (filename or "").lower()
    if lower_name.endswith(".csv"):
        df = pd.read_csv(file_obj)
    elif lower_name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError("Unsupported file format. Please upload a .csv or .xlsx file.")

    if df.empty:
        raise ValueError("Uploaded file contains no rows.")

    col_map = {str(c).strip().lower().replace("_", " "): c for c in df.columns}

    def pick_col(*candidates: str) -> Optional[str]:
        for cand in candidates:
            if cand in col_map:
                return col_map[cand]
        return None

    date_col = pick_col("sales date", "sale date", "date")
    time_col = pick_col("sale time", "sales time", "time")
    code_col = pick_col("product code", "sku", "code")
    branch_col = pick_col("branch", "branch code")
    units_col = pick_col("units sold", "quantity", "units", "qty")

    if not date_col or not code_col or not units_col:
        raise ValueError(
            "File must include columns for: Sales Date, Product Code, and Units Sold."
        )

    fallback_branch = (
        user.get("branch_code")
        if user.get("role") == "manager"
        else default_branch_code
    )

    valid_rows: List[tuple] = []
    errors: List[str] = []

    with get_connection(db_path) as conn:
        for idx, row in df.iterrows():
            row_num = idx + 2
            try:
                raw_branch = row[branch_col] if branch_col and pd.notna(row[branch_col]) else fallback_branch
                if not raw_branch:
                    raise ValueError("Missing Branch.")
                branch_code = _normalize_branch(raw_branch)
                assert_branch_access(user, branch_code)

                product_code = _resolve_product_code(conn, row[code_col])
                raw_time = row[time_col] if time_col and pd.notna(row[time_col]) else None
                clean_date, clean_time = _normalize_sale_date_and_time(row[date_col], raw_time)

                units_val = pd.to_numeric(row[units_col], errors="coerce")
                if pd.isna(units_val) or int(units_val) < 0:
                    raise ValueError(f"Invalid Units Sold '{row[units_col]}'.")

                valid_rows.append(
                    (product_code, branch_code, clean_date, clean_time, int(units_val), "csv_upload", 0)
                )
            except Exception as exc:
                errors.append(f"Row {row_num}: {exc}")

        if valid_rows:
            conn.executemany(
                """
                INSERT INTO sales_history (
                    product_code, branch_code, sale_date, sale_time,
                    units_sold, source, is_demo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                valid_rows,
            )
            log_audit(
                conn,
                username=str(user.get("username", "system")),
                action="UPLOAD_SALES_FILE",
                entity_type="sales_history",
                entity_id=filename,
                details=f"inserted={len(valid_rows)}, skipped={len(errors)}",
            )

    return {
        "inserted_count": len(valid_rows),
        "skipped_count": len(errors),
        "errors": errors,
    }


def get_sales_history(
    user: Dict[str, Any],
    branch_filter: Optional[str] = None,
    product_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Fetch role-scoped sales history joined with product and branch names."""
    role = user.get("role")
    if role == "manager":
        target_branch = user.get("branch_code")
    elif branch_filter and branch_filter != "ALL":
        target_branch = branch_filter
    else:
        target_branch = None

    query = """
        SELECT s.id, s.sale_date, s.sale_time, s.product_code, p.product_name,
               s.branch_code, b.branch_name, s.units_sold, s.source, s.is_demo
        FROM sales_history s
        JOIN products p ON s.product_code = p.product_code
        JOIN branches b ON s.branch_code = b.branch_code
        WHERE 1 = 1
    """
    params: List[Any] = []

    if target_branch:
        query += " AND s.branch_code = ?"
        params.append(target_branch)
    if product_code and product_code != "ALL":
        query += " AND UPPER(s.product_code) = ?"
        params.append(product_code.strip().upper())
    if start_date:
        query += " AND s.sale_date >= ?"
        params.append(str(start_date))
    if end_date:
        query += " AND s.sale_date <= ?"
        params.append(str(end_date))

    query += " ORDER BY s.sale_date DESC, s.sale_time DESC, s.id DESC;"

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        test_db = Path(tmpdir) / "test_sales.db"
        seed_all_demo_data(test_db)

        hk_mgr = authenticate_user("hk_manager", "Branch@123", db_path=test_db)
        today_str = date.today().isoformat()

        sale_id = record_sale(
            hk_mgr, "E04-BIS-01", "HK", today_str, 18, sale_time="15:30:00", db_path=test_db
        )
        assert sale_id > 0

        try:
            record_sale(
                hk_mgr,
                "E04-BIS-01",
                "HK",
                (date.today() + timedelta(days=2)).isoformat(),
                5,
                db_path=test_db,
            )
            raise AssertionError("Future date should fail")
        except ValueError:
            pass

        try:
            record_sale(hk_mgr, "E04-BIS-01", "KD", today_str, 5, db_path=test_db)
            raise AssertionError("Cross-branch insert should fail")
        except PermissionError:
            pass

        csv_sample = (
            f"Sales Date,Sale Time,Product Code,Branch,Units Sold\n"
            f"{today_str},11:00:00,E04-BIS-01,HK,12\n"
            f"{today_str},18:15:00,HK-E03-BIS-02,Hampankatta,20\n"
        )
        result = import_sales_file(
            hk_mgr, io.BytesIO(csv_sample.encode("utf-8")), "daily.csv", db_path=test_db
        )
        assert result["inserted_count"] == 2 and result["skipped_count"] == 0

    print("Sales module check passed!")