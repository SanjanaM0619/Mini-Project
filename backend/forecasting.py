from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backend.database import get_connection


def estimate_daily_demand(
    product_code: str,
    branch_code: str,
    lookback_days: int = 30,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Estimate daily sales demand using the 3-Tier Fallback Hierarchy:
    1. Recent branch sales history.
    2. Cross-branch fallback (same product_code across other branches).
    3. Clearly labeled illustrative fallback.
    """
    clean_code = (product_code or "").strip().upper()
    clean_branch = (branch_code or "").strip().upper()

    if not clean_code or not clean_branch:
        raise ValueError("Product Code and Branch Code are required.")

    today = date.today()
    cutoff_date = (today - timedelta(days=lookback_days)).isoformat()

    with get_connection(db_path) as conn:
        # Tier 1: Check branch-specific sales history
        branch_rows = conn.execute(
            """
            SELECT sale_date, SUM(units_sold) AS daily_units
            FROM sales_history
            WHERE UPPER(product_code) = ?
              AND UPPER(branch_code) = ?
              AND sale_date >= ?
              AND sale_date <= ?
            GROUP BY sale_date
            ORDER BY sale_date ASC;
            """,
            (clean_code, clean_branch, cutoff_date, today.isoformat()),
        ).fetchall()

        if branch_rows:
            daily_sales = [float(r["daily_units"]) for r in branch_rows]
            avg_daily = sum(daily_sales) / max(1, len(daily_sales))
            return {
                "product_code": clean_code,
                "branch_code": clean_branch,
                "daily_demand": round(max(0.0, avg_daily), 2),
                "prediction_source": "Branch sales history",
                "days_observed": len(daily_sales),
                "is_fallback": False,
            }

        # Tier 2: Cross-branch fallback (same product at other branches)
        other_rows = conn.execute(
            """
            SELECT branch_code, sale_date, SUM(units_sold) AS daily_units
            FROM sales_history
            WHERE UPPER(product_code) = ?
              AND UPPER(branch_code) != ?
              AND sale_date >= ?
              AND sale_date <= ?
            GROUP BY branch_code, sale_date;
            """,
            (clean_code, clean_branch, cutoff_date, today.isoformat()),
        ).fetchall()

        if other_rows:
            other_sales = [float(r["daily_units"]) for r in other_rows]
            avg_cross = sum(other_sales) / max(1, len(other_sales))
            return {
                "product_code": clean_code,
                "branch_code": clean_branch,
                "daily_demand": round(max(0.0, avg_cross), 2),
                "prediction_source": "Cross-branch fallback",
                "days_observed": len(other_sales),
                "is_fallback": True,
            }

        # Tier 3: Illustrative fallback when no historical data exists
        return {
            "product_code": clean_code,
            "branch_code": clean_branch,
            "daily_demand": 1.0,
            "prediction_source": "Illustrative fallback (no sales data)",
            "days_observed": 0,
            "is_fallback": True,
        }


def get_all_branch_demands(
    product_code: str,
    branches: Optional[List[str]] = None,
    lookback_days: int = 30,
    db_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compare daily demand for the same product across branches."""
    target_branches = branches or ["HK", "KD", "BJ", "KK", "UR"]
    results = {}
    for branch in target_branches:
        results[branch] = estimate_daily_demand(
            product_code=product_code,
            branch_code=branch,
            lookback_days=lookback_days,
            db_path=db_path,
        )
    return results


if __name__ == "__main__":
    # Test Tier 1: Branch sales history (E03-BIS-02 at HK has 30 days of sales)
    t1 = estimate_daily_demand("E03-BIS-02", "HK")
    assert t1["prediction_source"] == "Branch sales history"
    assert t1["daily_demand"] > 0
    assert not t1["is_fallback"]

    # Test Tier 2: Cross-branch fallback (E05-CAN-03 has sales at HK, but NOT at UR)
    t2 = estimate_daily_demand("E05-CAN-03", "UR")
    assert t2["prediction_source"] == "Cross-branch fallback"
    assert t2["daily_demand"] > 0
    assert t2["is_fallback"]

    # Test Tier 3: Product with zero sales anywhere in history
    t3 = estimate_daily_demand("NON-EXISTENT-SKU", "HK")
    assert t3["prediction_source"] == "Illustrative fallback (no sales data)"
    assert t3["daily_demand"] == 1.0
    assert t3["is_fallback"]

    print("Forecasting engine verification passed!")