"""Analytics, commentary, and sensitivity analysis for the Debt Payoff Simulator."""

from __future__ import annotations

from datetime import date

from src.simulator import Debt, SimulationResult, simulate


def debt_free_countdown(result: SimulationResult) -> dict:
    """Headline payoff stats for a simulation result.

    ``interest_share`` is the percentage of every dollar paid over the plan
    that goes to interest rather than principal.
    """
    principal = result.total_paid - result.total_interest
    interest_share = (
        result.total_interest / result.total_paid * 100 if result.total_paid > 0 else 0.0
    )

    return {
        "payoff_date": result.payoff_date,
        "months_remaining": result.months_to_payoff,
        "interest_share": round(interest_share, 1),
        "total_debt_start": round(principal, 2),
    }


def sensitivity_analysis(
    debts: list[Debt],
    income: float,
    expenses: float,
    extra_range: list[float] | None = None,
    start_date: date | None = None,
    payment_frequency: str = "monthly",
) -> list[dict]:
    """Run simulations across a range of extra payment amounts."""
    if extra_range is None:
        extra_range = [0, 50, 100, 150, 200, 300, 500]

    results = []
    for extra in extra_range:
        aval = simulate(debts, income, expenses, "avalanche", extra, start_date, payment_frequency)
        snow = simulate(debts, income, expenses, "snowball", extra, start_date, payment_frequency)
        results.append({
            "extra": extra,
            "avalanche": {
                "total_interest": aval.total_interest,
                "months": aval.months_to_payoff,
                "debt_growing": aval.debt_growing,
            },
            "snowball": {
                "total_interest": snow.total_interest,
                "months": snow.months_to_payoff,
                "debt_growing": snow.debt_growing,
            },
        })
    return results


def fun_savings_comparisons(savings_amount: float) -> list[str]:
    """Generate fun comparisons for a given savings amount."""
    comparisons = []
    items = [
        ("fancy coffees", 5.0),
        ("months of Netflix", 15.49),
        ("months of Spotify", 11.99),
        ("tanks of gas", 55.0),
        ("nice dinners out", 75.0),
        ("new pairs of shoes", 120.0),
        ("months of gym membership", 40.0),
        ("concert tickets", 85.0),
    ]
    for name, cost in items:
        count = int(savings_amount / cost)
        if count > 0:
            comparisons.append(f"{count:,} {name}")
    return comparisons


def payoff_commentary(result: SimulationResult) -> str:
    """Generate roast/commentary text for a simulation result."""
    lines = []
    payoff = result.payoff_date
    lines.append(
        f"At this rate, you'll be debt-free by **{payoff.strftime('%B %Y')}**. "
        f"Your future self just high-fived you. 🙌"
    )

    if result.total_interest > 5000:
        lines.append(
            f"You'll pay **${result.total_interest:,.2f}** in interest alone. "
            f"That's basically a vacation you're giving to the banks. ✈️"
        )
    elif result.total_interest > 1000:
        lines.append(
            f"Interest total: **${result.total_interest:,.2f}**. "
            f"Not catastrophic, but not cute either. 💸"
        )
    else:
        lines.append(
            f"Only **${result.total_interest:,.2f}** in interest? You're doing great. 🌟"
        )

    if result.months_to_payoff > 60:
        lines.append("That's a 5+ year journey. Buckle up. 🎢")
    elif result.months_to_payoff > 24:
        lines.append("A couple years of hustle and you're free. Let's go. 💪")
    else:
        lines.append("Under two years? Speed demon. 🏎️")

    return "\n\n".join(lines)


def debt_health_score(debts: list[Debt], income: float, expenses: float) -> dict:
    """Calculate a debt health score from 0-100."""
    if not debts or income <= 0:
        return {"score": 100, "grade": "A+", "description": "No debt? Living the dream. 🌈"}

    total_debt = sum(d.balance for d in debts)
    total_min = sum(d.min_payment for d in debts)
    disposable = income - expenses

    # Debt-to-income ratio (monthly)
    dti = (total_min / income * 100) if income > 0 else 100
    # Coverage ratio
    coverage = (disposable / total_min * 100) if total_min > 0 else 100
    # Weighted average APR
    if total_debt > 0:
        avg_apr = sum(d.apr * d.balance for d in debts) / total_debt
    else:
        avg_apr = 0

    score = 100
    # Penalize high DTI
    if dti > 50:
        score -= 40
    elif dti > 35:
        score -= 25
    elif dti > 20:
        score -= 10

    # Penalize low coverage
    if coverage < 100:
        score -= 30
    elif coverage < 150:
        score -= 15

    # Penalize high APR
    if avg_apr > 25:
        score -= 20
    elif avg_apr > 18:
        score -= 10

    # Penalize high total debt relative to income
    debt_months = total_debt / disposable if disposable > 0 else 999
    if debt_months > 60:
        score -= 15
    elif debt_months > 36:
        score -= 5

    score = max(0, min(100, score))

    if score >= 90:
        grade, desc = "A+", "You're in great shape. Keep it up! 🌟"
    elif score >= 80:
        grade, desc = "A", "Solid financial health. A few tweaks and you're golden. 👍"
    elif score >= 70:
        grade, desc = "B", "Not bad, but there's room for improvement. 📈"
    elif score >= 60:
        grade, desc = "C", "Getting a bit dicey. Time to make a plan. 📋"
    elif score >= 40:
        grade, desc = "D", f"Your debt-to-income ratio is {dti:.0f}%. Banks are sweating just looking at this. 😰"
    else:
        grade, desc = "F", "Emergency mode. Let's figure this out together. 🚨"

    return {"score": score, "grade": grade, "description": desc, "dti": round(dti, 1)}
