from flask import Flask, render_template, request, jsonify
from dataclasses import dataclass
from typing import List
import math
import random
import numpy as np

app = Flask(__name__)


@dataclass
class YearlyData:
    year: int
    deposit: float
    interest: float
    ending_balance: float
    phase: int  # 1 = contribution phase, 2 = growth-only phase
    cumulative_starting: float  # Running total of starting amount portion
    cumulative_contributions: float  # Running total of contributions
    cumulative_interest: float  # Running total of interest earned
    fees_paid: float  # Fees paid this year
    balance_without_fees: float  # What balance would be without fees


@dataclass
class InvestmentResult:
    end_balance: float
    starting_amount: float
    total_contributions: float
    total_interest: float
    total_fees: float
    balance_without_fees: float
    phase1_end_balance: float
    phase1_years: int
    phase2_years: int
    schedule: List[YearlyData]


def calculate_investment(
    starting_amount: float,
    start_age: int,
    end_age: int,
    contribution_phases: list,
    return_rate: float,
    fund_fee: float = 0.0,
    platform_fee: float = 0.0,
) -> InvestmentResult:
    """
    Calculate investment growth in three phases:
    Phase 0: Delay period (no investment, no growth)
    Phase 1: Starting amount + regular contributions
    Phase 2: Growth only (no contributions), pure compounding

    Fees are deducted monthly from the balance.
    """
    # Convert annual rates to decimal
    r = return_rate / 100
    total_fee_rate = (fund_fee + platform_fee) / 100

    schedule = []
    balance = starting_amount
    balance_no_fees = starting_amount
    total_contributions = 0
    total_interest = 0
    total_fees = 0
    cumulative_starting = starting_amount
    cumulative_contributions = 0
    cumulative_interest = 0
    phase1_end_balance = 0

    years = end_age - start_age
    for i in range(years):
        year = start_age + i
        year_interest = 0
        year_interest_no_fees = 0
        year_deposits = 0
        year_fees = 0

        # Find all phases active this year
        active_phases = [
            p for p in contribution_phases if p["start_age"] <= year < p["end_age"]
        ]

        # Monthly calculations
        for month in range(12):
            # Add contributions for all active phases
            for phase in active_phases:
                freq = phase.get("frequency", "monthly")
                amt = phase.get("amount", 0)
                # Assume contributions at beginning of month
                if freq == "monthly":
                    balance += amt
                    balance_no_fees += amt
                    year_deposits += amt
                    cumulative_contributions += amt
                elif freq == "yearly" and month == 0:
                    balance += amt
                    balance_no_fees += amt
                    year_deposits += amt
                    cumulative_contributions += amt

            # Calculate monthly interest (monthly compounding)
            monthly_interest = balance * (r / 12)
            monthly_interest_no_fees = balance_no_fees * (r / 12)
            balance += monthly_interest
            balance_no_fees += monthly_interest_no_fees
            year_interest += monthly_interest
            year_interest_no_fees += monthly_interest_no_fees
            cumulative_interest += monthly_interest

            # Deduct monthly fees (fees are applied to balance after interest)
            monthly_fee = balance * (total_fee_rate / 12)
            balance -= monthly_fee
            year_fees += monthly_fee
            total_fees += monthly_fee

        total_contributions += year_deposits
        total_interest += year_interest

        # Record phase 1 end balance (at end of last contribution phase)
        if i == years - 1:
            phase1_end_balance = balance

        schedule.append(
            YearlyData(
                year=year,
                deposit=year_deposits,
                interest=year_interest,
                ending_balance=balance,
                phase=1 if active_phases else 2,
                cumulative_starting=cumulative_starting,
                cumulative_contributions=cumulative_contributions,
                cumulative_interest=cumulative_interest,
                fees_paid=year_fees,
                balance_without_fees=balance_no_fees,
            )
        )

    return InvestmentResult(
        end_balance=balance,
        starting_amount=starting_amount,
        total_contributions=total_contributions,
        total_interest=total_interest,
        total_fees=total_fees,
        balance_without_fees=balance_no_fees,
        phase1_end_balance=phase1_end_balance,
        phase1_years=years,
        phase2_years=0,
        schedule=schedule,
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        data = request.json

        starting_amount = float(data.get("starting_amount", 0))
        start_age = int(data.get("start_age", 25))
        end_age = int(data.get("end_age", 65))
        contribution_phases = data.get("contribution_phases", [])
        return_rate = float(data.get("return_rate", 6))
        fund_fee = float(data.get("fund_fee", 0))
        platform_fee = float(data.get("platform_fee", 0))

        result = calculate_investment(
            starting_amount=starting_amount,
            start_age=start_age,
            end_age=end_age,
            contribution_phases=contribution_phases,
            return_rate=return_rate,
            fund_fee=fund_fee,
            platform_fee=platform_fee,
        )

        return jsonify(
            {
                "success": True,
                "end_balance": round(result.end_balance, 2),
                "starting_amount": round(result.starting_amount, 2),
                "total_contributions": round(result.total_contributions, 2),
                "total_interest": round(result.total_interest, 2),
                "total_fees": round(result.total_fees, 2),
                "balance_without_fees": round(result.balance_without_fees, 2),
                "phase1_end_balance": round(result.phase1_end_balance, 2),
                "phase1_years": result.phase1_years,
                "phase2_years": result.phase2_years,
                "schedule": [
                    {
                        "year": item.year,
                        "deposit": round(item.deposit, 2),
                        "interest": round(item.interest, 2),
                        "ending_balance": round(item.ending_balance, 2),
                        "phase": item.phase,
                        "cumulative_starting": round(item.cumulative_starting, 2),
                        "cumulative_contributions": round(
                            item.cumulative_contributions, 2
                        ),
                        "cumulative_interest": round(item.cumulative_interest, 2),
                        "fees_paid": round(item.fees_paid, 2),
                        "balance_without_fees": round(item.balance_without_fees, 2),
                    }
                    for item in result.schedule
                ],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/simulate", methods=["POST"])
def simulate():
    """
    Run Monte Carlo simulation using log-normal returns.
    Vectorized with numpy: all simulations run simultaneously per month,
    giving ~50-100x speedup over per-simulation Python loops.
    """
    try:
        data = request.json

        starting_amount = float(data.get("starting_amount", 0))
        start_age = int(data.get("start_age", 25))
        end_age = int(data.get("end_age", 65))
        contribution_phases = data.get("contribution_phases", [])
        expected_return = float(data.get("return_rate", 6)) / 100
        volatility = float(data.get("volatility", 15)) / 100
        fund_fee = float(data.get("fund_fee", 0)) / 100
        platform_fee = float(data.get("platform_fee", 0)) / 100
        num_simulations = int(data.get("num_simulations", 1000))

        total_fee_rate = fund_fee + platform_fee
        total_years = end_age - start_age
        total_months = total_years * 12

        # --- Precompute monthly contributions (deterministic, same for all sims) ---
        monthly_contributions = np.zeros(total_months)
        for month_idx in range(total_months):
            year_idx = month_idx // 12
            month_in_year = month_idx % 12
            current_age = start_age + year_idx
            for phase in contribution_phases:
                if phase["start_age"] <= current_age < phase["end_age"]:
                    freq = phase.get("frequency", "monthly")
                    amt = phase.get("amount", 0)
                    if freq == "monthly":
                        monthly_contributions[month_idx] += amt
                    elif freq == "yearly" and month_in_year == 0:
                        monthly_contributions[month_idx] += amt

        # --- Precompute cumulative contributions for response ---
        cumulative_contributions = []
        total_invested = starting_amount
        cumulative_contributions.append(total_invested)
        for year_idx in range(1, total_years):
            year_start_month = year_idx * 12
            year_contribs = float(np.sum(monthly_contributions[year_start_month:year_start_month + 12]))
            total_invested += year_contribs
            cumulative_contributions.append(total_invested)

        # --- Pre-generate ALL random returns at once: (num_simulations, total_months) ---
        monthly_expected = expected_return / 12
        monthly_vol = volatility / math.sqrt(12)
        log_mean = math.log(1 + monthly_expected) - (monthly_vol ** 2) / 2

        random_returns = np.random.lognormal(
            mean=log_mean,
            sigma=monthly_vol,
            size=(num_simulations, total_months),
        )

        fee_factor = 1 - total_fee_rate / 12

        # --- Vectorized simulation: loop over months, all sims run in parallel ---
        balances = np.full(num_simulations, starting_amount, dtype=np.float64)
        yearly_balances = np.zeros((num_simulations, total_years), dtype=np.float64)

        for month_idx in range(total_months):
            # Add this month's contribution to all simulations at once
            balances += monthly_contributions[month_idx]
            # Apply random return to all simulations at once
            balances *= random_returns[:, month_idx]
            # Apply fees to all simulations at once
            balances *= fee_factor

            # Record balance at end of each year
            if (month_idx + 1) % 12 == 0:
                year_idx = (month_idx + 1) // 12 - 1
                yearly_balances[:, year_idx] = np.maximum(0, balances)

        # --- Calculate percentiles for each year (vectorized) ---
        percentile_values = np.percentile(yearly_balances, [10, 25, 50, 75, 90], axis=0)
        percentiles = {
            "p10": np.round(percentile_values[0], 2).tolist(),
            "p25": np.round(percentile_values[1], 2).tolist(),
            "p50": np.round(percentile_values[2], 2).tolist(),
            "p75": np.round(percentile_values[3], 2).tolist(),
            "p90": np.round(percentile_values[4], 2).tolist(),
        }

        # --- Summary statistics (vectorized) ---
        final_balances = yearly_balances[:, -1]
        total_contributions = float(np.sum(monthly_contributions))
        total_invested_final = starting_amount + total_contributions

        return jsonify(
            {
                "success": True,
                "percentiles": percentiles,
                "cumulative_contributions": cumulative_contributions,
                "years": list(range(1, total_years + 1)),
                "ages": list(range(start_age, start_age + total_years)),
                "start_age": start_age,
                "stats": {
                    "median_final": round(float(np.median(final_balances)), 2),
                    "mean_final": round(float(np.mean(final_balances)), 2),
                    "p10_final": round(float(np.percentile(final_balances, 10)), 2),
                    "p90_final": round(float(np.percentile(final_balances, 90)), 2),
                    "best_case": round(float(np.max(final_balances)), 2),
                    "worst_case": round(float(np.min(final_balances)), 2),
                    "total_invested": round(total_invested_final, 2),
                    "prob_double": round(
                        float(np.mean(final_balances >= total_invested_final * 2) * 100), 1
                    ),
                    "prob_positive": round(
                        float(np.mean(final_balances >= total_invested_final) * 100), 1
                    ),
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
