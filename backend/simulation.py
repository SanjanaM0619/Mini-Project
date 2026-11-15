from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from backend.recovery_engine import compare_all_recovery_strategies


def run_batch_monte_carlo(
    quantity: int,
    selling_price: float,
    days_left: int,
    mean_daily_demand: float,
    action: str = "KEEP",
    discount_percentage: float = 25.0,
    demand_uplift: float = 0.35,
    transport_cost: float = 0.0,
    refund_percentage: float = 0.0,
    simulations: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation for a specific recovery action to model
    demand uncertainty and calculate risk distributions.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if days_left < 0:
        return {
            "action": action,
            "mean_units_sold": 0.0,
            "mean_unsold_units": float(quantity),
            "mean_recovery_value": 0.0,
            "p5_worst_case": 0.0,
            "p50_median": 0.0,
            "p95_best_case": 0.0,
            "std_dev": 0.0,
            "risk_level": "Expired",
        }

    rng = np.random.default_rng(seed)

    if action == "DISTRIBUTOR RETURN":
        # Returns have deterministic recovery if accepted
        refund_val = round(quantity * (selling_price * 0.7) * (refund_percentage / 100.0), 2)
        return {
            "action": action,
            "mean_units_sold": 0.0,
            "mean_unsold_units": 0.0,
            "mean_recovery_value": refund_val,
            "p5_worst_case": refund_val,
            "p50_median": refund_val,
            "p95_best_case": refund_val,
            "std_dev": 0.0,
            "risk_level": "Low Risk (Contractual Refund)",
        }

    # Determine daily demand parameters based on action
    if action == "MARKDOWN":
        effective_demand = max(0.1, mean_daily_demand * (1.0 + demand_uplift))
        unit_recovery_price = selling_price * (1.0 - discount_percentage / 100.0)
        net_deduction = 0.0
    elif action == "INTER-BRANCH TRANSFER":
        effective_demand = max(0.1, mean_daily_demand)
        unit_recovery_price = selling_price
        net_deduction = transport_cost
    else:  # KEEP
        effective_demand = max(0.1, mean_daily_demand)
        unit_recovery_price = selling_price
        net_deduction = 0.0

    effective_days = max(1, days_left - 1 if action == "INTER-BRANCH TRANSFER" else days_left)

    # Simulate total demand over the remaining days using Poisson distribution
    daily_samples = rng.poisson(lam=effective_demand, size=(simulations, effective_days))
    total_demand_per_run = daily_samples.sum(axis=1)

    units_sold_runs = np.minimum(quantity, total_demand_per_run)
    unsold_runs = quantity - units_sold_runs
    recovery_runs = np.maximum(0.0, (units_sold_runs * unit_recovery_price) - net_deduction)

    mean_sold = float(np.mean(units_sold_runs))
    mean_unsold = float(np.mean(unsold_runs))
    mean_recovery = float(np.mean(recovery_runs))
    std_dev = float(np.std(recovery_runs))

    p5 = float(np.percentile(recovery_runs, 5))
    p50 = float(np.percentile(recovery_runs, 50))
    p95 = float(np.percentile(recovery_runs, 95))

    # Evaluate risk based on unsold ratio
    unsold_ratio = mean_unsold / quantity
    if unsold_ratio <= 0.15:
        risk_level = "Low Risk"
    elif unsold_ratio <= 0.45:
        risk_level = "Moderate Risk"
    else:
        risk_level = "High Risk"

    return {
        "action": action,
        "mean_units_sold": round(mean_sold, 1),
        "mean_unsold_units": round(mean_unsold, 1),
        "mean_recovery_value": round(mean_recovery, 2),
        "p5_worst_case": round(p5, 2),
        "p50_median": round(p50, 2),
        "p95_best_case": round(p95, 2),
        "std_dev": round(std_dev, 2),
        "risk_level": risk_level,
        "simulated_recoveries": recovery_runs.tolist()[:100],  # sample for UI histogram
    }


def simulate_batch_recommendation(
    product_code: str,
    source_branch: str,
    quantity: int,
    unit_cost: float,
    selling_price: float,
    days_left: int,
    discount_percentage: float = 25.0,
    demand_uplift: float = 0.35,
    simulations: int = 1000,
    seed: int = 42,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run recovery strategy decision comparison AND Monte Carlo risk simulation
    for the recommended action.
    """
    rec = compare_all_recovery_strategies(
        product_code=product_code,
        source_branch=source_branch,
        quantity=quantity,
        unit_cost=unit_cost,
        selling_price=selling_price,
        days_left=days_left,
        discount_percentage=discount_percentage,
        demand_uplift=demand_uplift,
        db_path=db_path,
    )

    action = rec["recommended_action"]
    if action in ["EXPIRED", "MANUAL REVIEW"]:
        rec["simulation"] = {
            "mean_units_sold": 0.0,
            "mean_unsold_units": float(quantity),
            "mean_recovery_value": 0.0,
            "risk_level": "High Risk",
            "p5_worst_case": 0.0,
            "p50_median": 0.0,
            "p95_best_case": 0.0,
            "std_dev": 0.0,
        }
        return rec

    # Extract parameters for the recommended action
    dest_branch = rec.get("destination", "")
    opt_details = rec["options"].get(action, {})
    transport_cost = opt_details.get("transport_cost", 0.0)
    refund_pct = opt_details.get("refund_percentage", 0.0)

    # Use destination demand if transfer, else local demand
    if action == "INTER-BRANCH TRANSFER" and dest_branch:
        from backend.forecasting import estimate_daily_demand
        sim_demand = estimate_daily_demand(product_code, dest_branch, db_path=db_path)["daily_demand"]
    else:
        sim_demand = rec.get("daily_demand", 1.0)

    sim_result = run_batch_monte_carlo(
        quantity=quantity,
        selling_price=selling_price,
        days_left=days_left,
        mean_daily_demand=sim_demand,
        action=action,
        discount_percentage=discount_percentage,
        demand_uplift=demand_uplift,
        transport_cost=transport_cost,
        refund_percentage=refund_pct,
        simulations=simulations,
        seed=seed,
    )

    rec["simulation"] = sim_result
    rec["risk_level"] = sim_result["risk_level"]
    return rec


if __name__ == "__main__":
    # Test 1,000 Monte Carlo runs on a batch
    sim = run_batch_monte_carlo(
        quantity=45,
        selling_price=20.0,
        days_left=10,
        mean_daily_demand=1.0,
        action="KEEP",
        simulations=1000,
        seed=42,
    )

    assert sim["mean_units_sold"] > 0
    assert sim["p95_best_case"] >= sim["p5_worst_case"]
    assert sim["risk_level"] in ["Low Risk", "Moderate Risk", "High Risk"]

    # Test full end-to-end recommendation + simulation
    full_rec = simulate_batch_recommendation(
        product_code="E03-BIS-02",
        source_branch="HK",
        quantity=50,
        unit_cost=22.0,
        selling_price=35.0,
        days_left=10,
    )
    assert "simulation" in full_rec
    assert full_rec["simulation"]["mean_recovery_value"] > 0

    print("Monte Carlo simulation engine verification passed!")