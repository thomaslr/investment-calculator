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
    contribution_years: int,  # Phase 1: years with contributions
    growth_years: int,  # Phase 2: years with growth only (no contributions)
    return_rate: float,
    contribution: float,
    contribution_frequency: str,  # 'monthly' or 'yearly'
    contribution_timing: str,  # 'beginning' or 'end'
    fund_fee: float = 0.0,  # Annual fund fee as percentage
    platform_fee: float = 0.0,  # Annual platform fee as percentage
    delay_years: int = 0,  # Phase 0: years of delay before starting
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

    # Phase 0: Delay years (no investment yet)
    for year in range(1, delay_years + 1):
        schedule.append(
            YearlyData(
                year=year,
                deposit=0,
                interest=0,
                ending_balance=0,
                phase=0,
                cumulative_starting=0,
                cumulative_contributions=0,
                cumulative_interest=0,
                fees_paid=0,
                balance_without_fees=0,
            )
        )

    balance = starting_amount
    balance_no_fees = starting_amount  # Track what balance would be without fees
    total_contributions = 0
    total_interest = 0
    total_fees = 0
    phase1_end_balance = 0

    # Track cumulative breakdown
    cumulative_starting = starting_amount
    cumulative_contributions = 0
    cumulative_interest = 0

    total_years = contribution_years + growth_years

    for year in range(1, total_years + 1):
        actual_year = year + delay_years  # Offset by delay years
        year_interest = 0
        year_interest_no_fees = 0
        year_deposits = 0
        year_fees = 0

        # Determine which phase we're in
        in_contribution_phase = year <= contribution_years
        phase = 1 if in_contribution_phase else 2

        # Monthly calculations for precision
        for month in range(12):
            # Add contribution at beginning of period if applicable (Phase 1 only)
            if in_contribution_phase and contribution_timing == "beginning":
                if contribution_frequency == "monthly":
                    balance += contribution
                    balance_no_fees += contribution
                    year_deposits += contribution
                    cumulative_contributions += contribution
                elif contribution_frequency == "yearly" and month == 0:
                    balance += contribution
                    balance_no_fees += contribution
                    year_deposits += contribution
                    cumulative_contributions += contribution

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

            # Add contribution at end of period if applicable (Phase 1 only)
            if in_contribution_phase and contribution_timing == "end":
                if contribution_frequency == "monthly":
                    balance += contribution
                    balance_no_fees += contribution
                    year_deposits += contribution
                    cumulative_contributions += contribution
                elif contribution_frequency == "yearly" and month == 11:
                    balance += contribution
                    balance_no_fees += contribution
                    year_deposits += contribution
                    cumulative_contributions += contribution

        total_contributions += year_deposits
        total_interest += year_interest

        # Record phase 1 end balance
        if year == contribution_years:
            phase1_end_balance = balance

        schedule.append(
            YearlyData(
                year=actual_year,
                deposit=year_deposits,
                interest=year_interest,
                ending_balance=balance,
                phase=phase,
                cumulative_starting=cumulative_starting,
                cumulative_contributions=cumulative_contributions,
                cumulative_interest=cumulative_interest,
                fees_paid=year_fees,
                balance_without_fees=balance_no_fees,
            )
        )

    # Handle case where there are no contribution years
    if contribution_years == 0:
        phase1_end_balance = starting_amount

    return InvestmentResult(
        end_balance=balance,
        starting_amount=starting_amount,
        total_contributions=total_contributions,
        total_interest=total_interest,
        total_fees=total_fees,
        balance_without_fees=balance_no_fees,
        phase1_end_balance=phase1_end_balance,
        phase1_years=contribution_years,
        phase2_years=growth_years,
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
        contribution_years = int(data.get("contribution_years", 10))
        growth_years = int(data.get("growth_years", 0))
        return_rate = float(data.get("return_rate", 6))
        contribution = float(data.get("contribution", 0))
        contribution_frequency = data.get("contribution_frequency", "monthly")
        contribution_timing = data.get("contribution_timing", "end")
        fund_fee = float(data.get("fund_fee", 0))
        platform_fee = float(data.get("platform_fee", 0))
        delay_years = int(data.get("delay_years", 0))

        result = calculate_investment(
            starting_amount=starting_amount,
            contribution_years=contribution_years,
            growth_years=growth_years,
            return_rate=return_rate,
            contribution=contribution,
            contribution_frequency=contribution_frequency,
            contribution_timing=contribution_timing,
            fund_fee=fund_fee,
            platform_fee=platform_fee,
            delay_years=delay_years,
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
    Returns percentile bands for visualization.
    """
    try:
        data = request.json

        starting_amount = float(data.get("starting_amount", 0))
        contribution_years = int(data.get("contribution_years", 10))
        growth_years = int(data.get("growth_years", 0))
        expected_return = float(data.get("return_rate", 6)) / 100
        volatility = float(data.get("volatility", 15)) / 100
        contribution = float(data.get("contribution", 0))
        contribution_frequency = data.get("contribution_frequency", "monthly")
        contribution_timing = data.get("contribution_timing", "end")
        fund_fee = float(data.get("fund_fee", 0)) / 100
        platform_fee = float(data.get("platform_fee", 0)) / 100
        delay_years = int(data.get("delay_years", 0))
        num_simulations = int(data.get("num_simulations", 500))

        total_fee_rate = fund_fee + platform_fee
        total_years = delay_years + contribution_years + growth_years

        # Convert contribution to monthly
        monthly_contribution = (
            contribution if contribution_frequency == "monthly" else contribution / 12
        )

        # Run simulations
        all_paths = []
        final_balances = []

        for sim in range(num_simulations):
            balance = 0
            path = []

            for year in range(1, total_years + 1):
                if year <= delay_years:
                    # Delay phase - no investment
                    path.append(0)
                    continue

                # Initialize balance at start of investment period
                if year == delay_years + 1:
                    balance = starting_amount

                in_contribution_phase = year <= (delay_years + contribution_years)

                # Monthly simulation for this year
                for month in range(12):
                    # Add contribution at beginning if applicable
                    if in_contribution_phase and contribution_timing == "beginning":
                        balance += monthly_contribution

                    # Generate random monthly return using log-normal distribution
                    # Convert annual parameters to monthly
                    monthly_expected = expected_return / 12
                    monthly_vol = volatility / math.sqrt(12)

                    # Log-normal return
                    monthly_return = (
                        np.random.lognormal(
                            mean=math.log(1 + monthly_expected) - (monthly_vol**2) / 2,
                            sigma=monthly_vol,
                        )
                        - 1
                    )

                    balance *= 1 + monthly_return

                    # Apply monthly fees
                    balance *= 1 - total_fee_rate / 12

                    # Add contribution at end if applicable
                    if in_contribution_phase and contribution_timing == "end":
                        balance += monthly_contribution

                path.append(max(0, balance))

            all_paths.append(path)
            final_balances.append(balance)

        # Convert to numpy for percentile calculation
        paths_array = np.array(all_paths)

        # Calculate percentiles for each year
        percentiles = {"p10": [], "p25": [], "p50": [], "p75": [], "p90": []}

        for year_idx in range(total_years):
            year_values = paths_array[:, year_idx]
            percentiles["p10"].append(round(float(np.percentile(year_values, 10)), 2))
            percentiles["p25"].append(round(float(np.percentile(year_values, 25)), 2))
            percentiles["p50"].append(round(float(np.percentile(year_values, 50)), 2))
            percentiles["p75"].append(round(float(np.percentile(year_values, 75)), 2))
            percentiles["p90"].append(round(float(np.percentile(year_values, 90)), 2))

        # Calculate summary statistics
        final_array = np.array(final_balances)
        total_invested = starting_amount + (
            monthly_contribution * 12 * contribution_years
        )

        return jsonify(
            {
                "success": True,
                "percentiles": percentiles,
                "years": list(range(1, total_years + 1)),
                "stats": {
                    "median_final": round(float(np.median(final_array)), 2),
                    "mean_final": round(float(np.mean(final_array)), 2),
                    "p10_final": round(float(np.percentile(final_array, 10)), 2),
                    "p90_final": round(float(np.percentile(final_array, 90)), 2),
                    "best_case": round(float(np.max(final_array)), 2),
                    "worst_case": round(float(np.min(final_array)), 2),
                    "total_invested": round(total_invested, 2),
                    "prob_double": round(
                        float(np.mean(final_array >= total_invested * 2) * 100), 1
                    ),
                    "prob_positive": round(
                        float(np.mean(final_array >= total_invested) * 100), 1
                    ),
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
