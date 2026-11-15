from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.distributor_returns import evaluate_distributor_return
from backend.forecasting import estimate_daily_demand, get_all_branch_demands
from backend.transport import calculate_interbranch_cost, check_transfer_feasibility

MANGALORE_BRANCHES = ["HK", "KD", "BJ", "KK", "UR"]


def evaluate_keep(
    quantity: int,
    selling_price: float,
    days_left: int,
    daily_demand: float,
) -> Dict[str, Any]:
    """Estimate recovery by keeping stock at the current branch and price."""
    if days_left < 0:
        return {
            "action": "KEEP",
            "feasible": False,
            "destination": "",
            "estimated_units_sold": 0,
            "estimated_unsold_units": quantity,
            "expected_revenue": 0.0,
            "net_recovery_value": 0.0,
            "reason": "Product is already expired.",
        }

    potential_sales = int(daily_demand * days_left)
    units_sold = min(quantity, potential_sales)
    unsold = quantity - units_sold
    revenue = round(units_sold * selling_price, 2)

    return {
        "action": "KEEP",
        "feasible": units_sold > 0,
        "destination": "",
        "estimated_units_sold": units_sold,
        "estimated_unsold_units": unsold,
        "expected_revenue": revenue,
        "net_recovery_value": revenue,
        "reason": (
            f"Expected to sell ~{units_sold} of {quantity} units before expiry at full price."
            if units_sold > 0
            else "Local demand too low to sell any units before expiry."
        ),
    }


def evaluate_markdown(
    quantity: int,
    selling_price: float,
    days_left: int,
    daily_demand: float,
    discount_percentage: float = 25.0,
    demand_uplift: float = 0.35,
) -> Dict[str, Any]:
    """Estimate recovery by discounting price to increase daily sales."""
    if days_left < 0:
        return {
            "action": "MARKDOWN",
            "feasible": False,
            "destination": "",
            "estimated_units_sold": 0,
            "estimated_unsold_units": quantity,
            "expected_revenue": 0.0,
            "net_recovery_value": 0.0,
            "reason": "Product is already expired.",
        }

    discounted_price = round(selling_price * (1.0 - discount_percentage / 100.0), 2)
    boosted_demand = daily_demand * (1.0 + demand_uplift)
    potential_sales = int(boosted_demand * days_left)
    units_sold = min(quantity, potential_sales)
    unsold = quantity - units_sold
    revenue = round(units_sold * discounted_price, 2)

    return {
        "action": "MARKDOWN",
        "feasible": units_sold > 0,
        "destination": "",
        "estimated_units_sold": units_sold,
        "estimated_unsold_units": unsold,
        "expected_revenue": revenue,
        "net_recovery_value": revenue,
        "discount_percentage": discount_percentage,
        "discounted_price": discounted_price,
        "reason": (
            f"Apply {discount_percentage}% discount (₹{discounted_price}); expect {units_sold} units sold."
            if units_sold > 0
            else "Discounting still will not clear units before expiry."
        ),
    }


def evaluate_best_transfer(
    product_code: str,
    source_branch: str,
    quantity: int,
    selling_price: float,
    days_left: int,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Compare all alternative branches and find the best destination branch based
    on destination demand, transport costs, and travel feasibility.
    """
    clean_source = source_branch.strip().upper()
    best_option: Optional[Dict[str, Any]] = None

    for dest in MANGALORE_BRANCHES:
        if dest == clean_source:
            continue

        transport = calculate_interbranch_cost(clean_source, dest, quantity, db_path)
        feas = check_transfer_feasibility(
            days_left=days_left,
            estimated_minutes=transport["estimated_minutes"],
            quantity=quantity,
            vehicle_capacity=transport["vehicle_capacity"],
        )

        if not feas["feasible"]:
            continue

        dest_demand_info = estimate_daily_demand(product_code, dest, db_path=db_path)
        dest_demand = dest_demand_info["daily_demand"]

        # Assume 1 day needed for transit & restock
        effective_selling_days = max(0, days_left - 1)
        potential_sales = int(dest_demand * effective_selling_days)
        units_sold = min(quantity, potential_sales)
        unsold = quantity - units_sold

        gross_revenue = units_sold * selling_price
        net_recovery = round(gross_revenue - transport["total_transport_cost"], 2)

        if units_sold > 0 and net_recovery > 0:
            if best_option is None or net_recovery > best_option["net_recovery_value"]:
                best_option = {
                    "action": "INTER-BRANCH TRANSFER",
                    "feasible": True,
                    "destination": dest,
                    "estimated_units_sold": units_sold,
                    "estimated_unsold_units": unsold,
                    "expected_revenue": round(gross_revenue, 2),
                    "transport_cost": transport["total_transport_cost"],
                    "net_recovery_value": net_recovery,
                    "reason": (
                        f"Transfer to {dest} (high demand: {dest_demand}/d). "
                        f"Gross ₹{gross_revenue} - transport ₹{transport['total_transport_cost']}."
                    ),
                }

    if best_option:
        return best_option

    return {
        "action": "INTER-BRANCH TRANSFER",
        "feasible": False,
        "destination": "",
        "estimated_units_sold": 0,
        "estimated_unsold_units": quantity,
        "expected_revenue": 0.0,
        "transport_cost": 0.0,
        "net_recovery_value": 0.0,
        "reason": "No other branch has sufficient demand or time to absorb transport costs.",
    }


def compare_all_recovery_strategies(
    product_code: str,
    source_branch: str,
    quantity: int,
    unit_cost: float,
    selling_price: float,
    days_left: int,
    discount_percentage: float = 25.0,
    demand_uplift: float = 0.35,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Compare Keep, Markdown, Distributor Return, and Inter-Branch Transfer.
    Recommends the strategy yielding highest net recovery.
    """
    if days_left < 0:
        return {
            "recommended_action": "EXPIRED",
            "destination": "",
            "estimated_recovery": 0.0,
            "estimated_units_sold": 0,
            "estimated_unsold_units": quantity,
            "reason": "Product has passed its expiry date. Must be written off and removed from shelves.",
            "options": {},
        }

    # Get local demand
    local_demand_info = estimate_daily_demand(product_code, source_branch, db_path=db_path)
    local_demand = local_demand_info["daily_demand"]

    # 1. Keep
    opt_keep = evaluate_keep(quantity, selling_price, days_left, local_demand)

    # 2. Markdown
    opt_markdown = evaluate_markdown(
        quantity, selling_price, days_left, local_demand, discount_percentage, demand_uplift
    )

    # 3. Distributor Return
    opt_return = evaluate_distributor_return(product_code, quantity, unit_cost, days_left, db_path)
    return_option = {
        "action": "DISTRIBUTOR RETURN",
        "feasible": opt_return["feasible"],
        "destination": opt_return.get("destination", "Distributor") if opt_return["feasible"] else "",
        "estimated_units_sold": 0,
        "estimated_unsold_units": quantity - opt_return.get("units_refunded", 0),
        "expected_revenue": opt_return.get("estimated_recovery", 0.0),
        "net_recovery_value": opt_return.get("estimated_recovery", 0.0),
        "reason": opt_return["reason"],
    }

    # 4. Inter-Branch Transfer
    opt_transfer = evaluate_best_transfer(
        product_code, source_branch, quantity, selling_price, days_left, db_path
    )

    all_options = [opt_keep, opt_markdown, return_option, opt_transfer]
    feasible_options = [o for o in all_options if o["feasible"]]

    if not feasible_options:
        return {
            "recommended_action": "MANUAL REVIEW",
            "destination": "",
            "estimated_recovery": 0.0,
            "estimated_units_sold": 0,
            "estimated_unsold_units": quantity,
            "reason": "No automated recovery strategy is feasible. Flagged for manager manual review.",
            "options": {o["action"]: o for o in all_options},
            "prediction_source": local_demand_info["prediction_source"],
            "daily_demand": local_demand,
        }

    # Recommend option with highest net recovery value
    best = max(feasible_options, key=lambda x: x["net_recovery_value"])

    return {
        "recommended_action": best["action"],
        "destination": best.get("destination", ""),
        "estimated_recovery": best["net_recovery_value"],
        "estimated_units_sold": best.get("estimated_units_sold", 0),
        "estimated_unsold_units": best.get("estimated_unsold_units", 0),
        "reason": best["reason"],
        "options": {o["action"]: o for o in all_options},
        "prediction_source": local_demand_info["prediction_source"],
        "daily_demand": local_demand,
    }


if __name__ == "__main__":
    # Test batch with good local demand (should recommend KEEP or MARKDOWN)
    res1 = compare_all_recovery_strategies(
        product_code="E03-BIS-02",
        source_branch="HK",
        quantity=50,
        unit_cost=22.0,
        selling_price=35.0,
        days_left=10,
    )
    assert res1["recommended_action"] in ["KEEP", "MARKDOWN"]
    assert res1["destination"] == ""

    # Test batch at Urwa (low UR demand -> should recommend INTER-BRANCH TRANSFER)
    res2 = compare_all_recovery_strategies(
        product_code="E03-BIS-02",
        source_branch="UR",
        quantity=100,
        unit_cost=22.0,
        selling_price=35.0,
        days_left=12,
    )
    assert res2["recommended_action"] == "INTER-BRANCH TRANSFER"
    assert res2["destination"] in ["HK", "KD", "BJ"]
    assert res2["estimated_recovery"] > 0

    print("Recovery strategy decision engine verification passed!")