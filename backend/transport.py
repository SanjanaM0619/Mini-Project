from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.database import get_connection


def get_logistics_route(
    from_location: str,
    to_location: str,
    location_type: str = "inter_branch",
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve distance, estimated travel time, capacity, and cost for a route."""
    clean_from = (from_location or "").strip().upper()
    clean_to = (to_location or "").strip().upper()

    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT from_location, to_location, location_type,
                   distance_km, estimated_minutes, vehicle_capacity_units,
                   transport_cost, cost_per_km
            FROM branch_logistics
            WHERE UPPER(from_location) = ?
              AND UPPER(to_location) = ?
              AND location_type = ?;
            """,
            (clean_from, clean_to, location_type),
        ).fetchone()
        return dict(row) if row else None


def calculate_interbranch_cost(
    from_branch: str,
    to_branch: str,
    quantity: int = 1,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Calculate the transport cost and travel time between two branches."""
    if int(quantity) <= 0:
        raise ValueError("Quantity must be greater than zero.")

    clean_from = (from_branch or "").strip().upper()
    clean_to = (to_branch or "").strip().upper()

    if clean_from == clean_to:
        return {
            "from_branch": clean_from,
            "to_branch": clean_to,
            "distance_km": 0.0,
            "estimated_minutes": 0,
            "total_transport_cost": 0.0,
            "cost_per_unit": 0.0,
            "vehicle_capacity": 0,
        }

    route = get_logistics_route(clean_from, clean_to, "inter_branch", db_path)
    if not route:
        # Fallback calculation if route not found
        default_distance = 5.0
        default_cost = round(default_distance * 14.0 + 45.0, 2)
        return {
            "from_branch": clean_from,
            "to_branch": clean_to,
            "distance_km": default_distance,
            "estimated_minutes": 20,
            "total_transport_cost": default_cost,
            "cost_per_unit": round(default_cost / quantity, 2),
            "vehicle_capacity": 800,
        }

    total_cost = float(route["transport_cost"])
    return {
        "from_branch": clean_from,
        "to_branch": clean_to,
        "distance_km": float(route["distance_km"]),
        "estimated_minutes": int(route["estimated_minutes"]),
        "total_transport_cost": round(total_cost, 2),
        "cost_per_unit": round(total_cost / quantity, 2),
        "vehicle_capacity": int(route["vehicle_capacity_units"]),
    }


def check_transfer_feasibility(
    days_left: int,
    estimated_minutes: int,
    quantity: int,
    vehicle_capacity: int = 800,
) -> Dict[str, Any]:
    """Check if stock has enough shelf-life and vehicle capacity for the journey."""
    if days_left < 0:
        return {"feasible": False, "reason": "Batch is already expired."}

    # Estimate required days for transportation & shelf stocking
    transport_days = max(1, int(estimated_minutes / 1440) + 1)

    if days_left <= transport_days:
        return {
            "feasible": False,
            "reason": f"Insufficient shelf-life ({days_left}d left, transfer needs {transport_days}d).",
        }

    if quantity > vehicle_capacity:
        return {
            "feasible": False,
            "reason": f"Quantity ({quantity}) exceeds vehicle capacity ({vehicle_capacity}).",
        }

    return {"feasible": True, "reason": "Transfer is logistically feasible."}


def get_all_logistics_routes(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return all routes (inter-branch, godown, manufacturer) for admin viewing."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT from_location, to_location, location_type,
                   distance_km, estimated_minutes, vehicle_capacity_units,
                   transport_cost, cost_per_km
            FROM branch_logistics
            ORDER BY location_type, from_location, to_location;
            """
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    # Test route from Urwa to Hampankatta
    cost_info = calculate_interbranch_cost("UR", "HK", quantity=50)
    assert cost_info["distance_km"] == 5.6
    assert cost_info["estimated_minutes"] == 24
    assert cost_info["total_transport_cost"] > 0

    # Test feasibility for expired stock
    feas_expired = check_transfer_feasibility(days_left=-1, estimated_minutes=24, quantity=50)
    assert not feas_expired["feasible"]

    # Test feasibility for valid stock
    feas_valid = check_transfer_feasibility(days_left=10, estimated_minutes=24, quantity=50)
    assert feas_valid["feasible"]

    print("Transport & logistics calculator verification passed!")