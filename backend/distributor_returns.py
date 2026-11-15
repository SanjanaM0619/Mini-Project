from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.database import get_connection


def get_return_rule(
    product_code: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Fetch return policy for a product code from the database."""
    clean_code = (product_code or "").strip().upper()

    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT product_code, eligible, return_deadline_days,
                   accepted_condition, refund_percentage, notes
            FROM distributor_return_rules
            WHERE UPPER(product_code) = ?;
            """,
            (clean_code,),
        ).fetchone()

        if row:
            return dict(row)

        # Default fallback if no explicit rule exists
        return {
            "product_code": clean_code,
            "eligible": "Requires Verification",
            "return_deadline_days": 7,
            "accepted_condition": "Original unopened packaging",
            "refund_percentage": 50.0,
            "notes": "No explicit distributor agreement recorded; requires verification.",
        }


def evaluate_distributor_return(
    product_code: str,
    quantity: int,
    unit_cost: float,
    days_left: int,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Evaluate whether a batch can be returned to the distributor and calculate recovery value.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if unit_cost < 0:
        raise ValueError("Unit cost cannot be negative.")

    if days_left < 0:
        return {
            "action": "DISTRIBUTOR RETURN",
            "feasible": False,
            "destination": "Distributor",
            "estimated_recovery": 0.0,
            "refund_percentage": 0.0,
            "units_refunded": 0,
            "reason": "Batch is already expired; distributor returns rejected.",
            "status": "Ineligible",
        }

    rule = get_return_rule(product_code, db_path)
    eligibility = rule["eligible"]
    deadline_days = int(rule["return_deadline_days"])
    refund_pct = float(rule["refund_percentage"])

    if eligibility == "Not Eligible":
        return {
            "action": "DISTRIBUTOR RETURN",
            "feasible": False,
            "destination": "Distributor",
            "estimated_recovery": 0.0,
            "refund_percentage": 0.0,
            "units_refunded": 0,
            "reason": f"Distributor does not accept returns for this item ({rule['notes']}).",
            "status": "Ineligible",
        }

    if days_left < deadline_days:
        return {
            "action": "DISTRIBUTOR RETURN",
            "feasible": False,
            "destination": "Distributor",
            "estimated_recovery": 0.0,
            "refund_percentage": 0.0,
            "units_refunded": 0,
            "reason": f"Past return deadline ({days_left}d left, deadline was {deadline_days}d before expiry).",
            "status": "Deadline Passed",
        }

    # Calculate expected refund value
    estimated_refund = round(quantity * unit_cost * (refund_pct / 100.0), 2)
    requires_verification = eligibility == "Requires Verification"

    return {
        "action": "DISTRIBUTOR RETURN",
        "feasible": True,
        "destination": "Distributor",
        "estimated_recovery": estimated_refund,
        "refund_percentage": refund_pct,
        "units_refunded": quantity,
        "accepted_condition": rule["accepted_condition"],
        "reason": (
            f"Eligible for {refund_pct}% refund ({rule['accepted_condition']})."
            if not requires_verification
            else f"Requires distributor verification ({refund_pct}% estimated refund)."
        ),
        "status": "Requires Verification" if requires_verification else "Eligible",
    }


def update_return_rule(
    product_code: str,
    eligible: str,
    return_deadline_days: int,
    accepted_condition: str,
    refund_percentage: float,
    notes: str = "",
    db_path: Optional[Path] = None,
) -> None:
    """Update or insert distributor return policy."""
    clean_code = (product_code or "").strip().upper()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO distributor_return_rules (
                product_code, eligible, return_deadline_days,
                accepted_condition, refund_percentage, notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_code) DO UPDATE SET
                eligible = excluded.eligible,
                return_deadline_days = excluded.return_deadline_days,
                accepted_condition = excluded.accepted_condition,
                refund_percentage = excluded.refund_percentage,
                notes = excluded.notes;
            """,
            (
                clean_code,
                eligible,
                return_deadline_days,
                accepted_condition,
                refund_percentage,
                notes,
            ),
        )


if __name__ == "__main__":
    # Test perishable product with No Return policy (E01 tier)
    r1 = evaluate_distributor_return(
        product_code="E01-MKT-01",
        quantity=20,
        unit_cost=25.0,
        days_left=4,
    )
    assert not r1["feasible"]

    # Test eligible product with valid shelf life
    r2 = evaluate_distributor_return(
        product_code="E04-BIS-01",
        quantity=50,
        unit_cost=18.0,
        days_left=20,
    )
    assert r2["feasible"]
    assert r2["estimated_recovery"] > 0
    assert r2["destination"] == "Distributor"

    # Test eligible product with deadline passed
    r3 = evaluate_distributor_return(
        product_code="E04-BIS-01",
        quantity=50,
        unit_cost=18.0,
        days_left=3,  # Deadline is 7 days
    )
    assert not r3["feasible"]

    print("Distributor return engine verification passed!")