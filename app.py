from flask import Flask, render_template, request, jsonify
from dataclasses import dataclass
from typing import List
import math

app = Flask(__name__)


@dataclass
class YearlyData:
    year: int
    deposit: float
    interest: float
    ending_balance: float
    phase: int  # 1 = contribution phase, 2 = growth-only phase


@dataclass
class InvestmentResult:
    end_balance: float
    starting_amount: float
    total_contributions: float
    total_interest: float
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
) -> InvestmentResult:
    """
    Calculate investment growth in two phases:
    Phase 1: Starting amount + regular contributions
    Phase 2: Growth only (no contributions), pure compounding
    """
    # Convert annual rate to decimal
    r = return_rate / 100

    schedule = []
    balance = starting_amount
    total_contributions = 0
    total_interest = 0
    phase1_end_balance = 0

    total_years = contribution_years + growth_years

    for year in range(1, total_years + 1):
        year_interest = 0
        year_deposits = 0

        # Determine which phase we're in
        in_contribution_phase = year <= contribution_years
        phase = 1 if in_contribution_phase else 2

        # Monthly calculations for precision
        for month in range(12):
            # Add contribution at beginning of period if applicable (Phase 1 only)
            if in_contribution_phase and contribution_timing == "beginning":
                if contribution_frequency == "monthly":
                    balance += contribution
                    year_deposits += contribution
                elif contribution_frequency == "yearly" and month == 0:
                    balance += contribution
                    year_deposits += contribution

            # Calculate monthly interest (monthly compounding)
            monthly_interest = balance * (r / 12)
            balance += monthly_interest
            year_interest += monthly_interest

            # Add contribution at end of period if applicable (Phase 1 only)
            if in_contribution_phase and contribution_timing == "end":
                if contribution_frequency == "monthly":
                    balance += contribution
                    year_deposits += contribution
                elif contribution_frequency == "yearly" and month == 11:
                    balance += contribution
                    year_deposits += contribution

        # First year includes starting amount in deposits
        if year == 1:
            year_deposits += starting_amount

        total_contributions += year_deposits - (starting_amount if year == 1 else 0)
        total_interest += year_interest

        # Record phase 1 end balance
        if year == contribution_years:
            phase1_end_balance = balance

        schedule.append(
            YearlyData(
                year=year,
                deposit=year_deposits,
                interest=year_interest,
                ending_balance=balance,
                phase=phase,
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

        result = calculate_investment(
            starting_amount=starting_amount,
            contribution_years=contribution_years,
            growth_years=growth_years,
            return_rate=return_rate,
            contribution=contribution,
            contribution_frequency=contribution_frequency,
            contribution_timing=contribution_timing,
        )

        return jsonify(
            {
                "success": True,
                "end_balance": round(result.end_balance, 2),
                "starting_amount": round(result.starting_amount, 2),
                "total_contributions": round(result.total_contributions, 2),
                "total_interest": round(result.total_interest, 2),
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
                    }
                    for item in result.schedule
                ],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
