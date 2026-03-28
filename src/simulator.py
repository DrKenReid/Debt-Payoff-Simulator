"""Debt payoff simulation engine — Avalanche & Snowball strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class Debt:
    name: str
    balance: float
    apr: float  # as percentage, e.g. 24.99
    min_payment: float
    promo_apr: Optional[float] = None
    promo_end_date: Optional[date] = None


@dataclass
class SimulationResult:
    method: str
    monthly_payments: list[dict] = field(default_factory=list)
    total_interest: float = 0.0
    total_paid: float = 0.0
    months_to_payoff: int = 0
    payoff_date: date = field(default_factory=date.today)
    debt_names: list[str] = field(default_factory=list)
    can_cover_minimums: bool = True
    monthly_shortfall: float = 0.0
    debt_growing: bool = False


def _effective_apr(debt: Debt, current_date: date) -> float:
    """Return the APR in effect for a debt on a given date."""
    if (
        debt.promo_apr is not None
        and debt.promo_end_date is not None
        and current_date < debt.promo_end_date
    ):
        return debt.promo_apr
    return debt.apr


def simulate(
    debts: list[Debt],
    monthly_income: float,
    monthly_expenses: float,
    method: str = "avalanche",
    extra_payment: float = 0.0,
    start_date: date | None = None,
    payment_frequency: str = "monthly",
) -> SimulationResult:
    """Run a debt payoff simulation.

    Args:
        debts: List of debts to pay off.
        monthly_income: Monthly take-home pay.
        monthly_expenses: Monthly fixed expenses (non-debt).
        method: "avalanche" (highest APR first) or "snowball" (lowest balance first).
        extra_payment: Additional monthly payment toward debt.
        start_date: Simulation start date (defaults to today).
        payment_frequency: "monthly" or "biweekly". Biweekly effectively
            makes 13 monthly payments per year (26 half-payments).

    Returns:
        SimulationResult with month-by-month breakdown.
    """
    if start_date is None:
        start_date = date.today()

    # Filter out zero-balance debts
    active = [
        {"name": d.name, "balance": d.balance, "apr": d.apr, "min_payment": d.min_payment,
         "promo_apr": d.promo_apr, "promo_end_date": d.promo_end_date}
        for d in debts if d.balance > 0
    ]

    if not active:
        return SimulationResult(
            method=method,
            months_to_payoff=0,
            payoff_date=start_date,
            debt_names=[d.name for d in debts],
        )

    result = SimulationResult(
        method=method,
        debt_names=[d["name"] for d in active],
    )

    max_months = 600
    total_interest = 0.0
    total_paid = 0.0

    # Check if payments can cover minimums
    sum_min = sum(d["min_payment"] for d in active)
    biweekly_boost = (1 / 12) if payment_frequency == "biweekly" else 0.0
    initial_available = monthly_income * (1 + biweekly_boost) - monthly_expenses + extra_payment
    result.can_cover_minimums = initial_available >= sum_min
    result.monthly_shortfall = max(0.0, sum_min - initial_available)
    result.debt_growing = False

    for month in range(1, max_months + 1):
        current_date = start_date + timedelta(days=30 * month)
        month_record: dict = {"month": month, "date": current_date.isoformat(), "debts": {}}

        # Apply interest
        for d in active:
            debt_obj = Debt(d["name"], d["balance"], d["apr"], d["min_payment"],
                           d["promo_apr"], d["promo_end_date"])
            apr = _effective_apr(debt_obj, current_date)
            interest = d["balance"] * (apr / 100 / 12)
            d["balance"] += interest
            d["_interest"] = interest
            total_interest += interest

        # Calculate available funds
        # Bi-weekly: 26 half-payments/year = 13/12 monthly payments
        biweekly_boost = (1 / 12) if payment_frequency == "biweekly" else 0.0
        effective_income = monthly_income * (1 + biweekly_boost)

        sum_min = sum(min(d["min_payment"], d["balance"]) for d in active)
        available = effective_income - monthly_expenses - sum_min + extra_payment
        available = max(available, 0.0)

        # Sort for strategy
        if method == "avalanche":
            order = sorted(range(len(active)), key=lambda i: (
                -_effective_apr(
                    Debt(active[i]["name"], active[i]["balance"], active[i]["apr"],
                         active[i]["min_payment"], active[i]["promo_apr"], active[i]["promo_end_date"]),
                    current_date),
                active[i]["balance"]
            ))
        else:  # snowball
            order = sorted(range(len(active)), key=lambda i: active[i]["balance"])

        # Pay minimums
        remaining = effective_income - monthly_expenses + extra_payment
        remaining = max(remaining, 0.0)
        payments = [0.0] * len(active)

        for i in range(len(active)):
            pay = min(active[i]["min_payment"], active[i]["balance"], remaining)
            payments[i] = pay
            remaining -= pay

        # Distribute extra to priority debt
        for i in order:
            if remaining <= 0:
                break
            extra = min(remaining, active[i]["balance"] - payments[i])
            if extra > 0:
                payments[i] += extra
                remaining -= extra

        # Apply payments
        month_total_payment = 0.0
        for i in range(len(active)):
            active[i]["balance"] -= payments[i]
            if active[i]["balance"] < 0.01:
                active[i]["balance"] = 0.0
            month_total_payment += payments[i]
            month_record["debts"][active[i]["name"]] = {
                "balance": round(active[i]["balance"], 2),
                "payment": round(payments[i], 2),
                "interest": round(active[i].get("_interest", 0), 2),
            }

        total_paid += month_total_payment
        month_record["total_payment"] = round(month_total_payment, 2)
        month_record["total_remaining"] = round(sum(d["balance"] for d in active), 2)
        result.monthly_payments.append(month_record)

        # Detect if debt is growing (balance higher than previous month)
        if month >= 3 and len(result.monthly_payments) >= 3:
            prev_remaining = result.monthly_payments[-2]["total_remaining"]
            curr_remaining = month_record["total_remaining"]
            prev2_remaining = result.monthly_payments[-3]["total_remaining"]
            if curr_remaining > prev_remaining > prev2_remaining:
                # Debt is growing for 3 consecutive months — flag and stop
                result.debt_growing = True
                result.months_to_payoff = max_months
                result.payoff_date = start_date + timedelta(days=30 * max_months)
                break

        # Remove paid-off debts
        active = [d for d in active if d["balance"] > 0]

        if not active:
            result.months_to_payoff = month
            result.payoff_date = current_date
            break
    else:
        result.months_to_payoff = max_months
        result.payoff_date = start_date + timedelta(days=30 * max_months)

    result.total_interest = round(total_interest, 2)
    result.total_paid = round(total_paid, 2)
    return result


def simulate_balance_transfer(
    debts: list[Debt],
    from_debt_idx: int,
    transfer_fee_pct: float,
    new_apr: float,
    promo_months: int,
    income: float,
    expenses: float,
    extra_payment: float = 0.0,
    method: str = "avalanche",
    start_date: date | None = None,
    payment_frequency: str = "monthly",
) -> SimulationResult:
    """Simulate paying off debts after a balance transfer.

    Moves the balance from debts[from_debt_idx] to a new card with
    the given APR/promo terms, adding the transfer fee to the new balance.
    """
    if start_date is None:
        start_date = date.today()

    import copy
    new_debts = [copy.copy(d) for d in debts]
    source = new_debts[from_debt_idx]
    transferred_balance = source.balance * (1 + transfer_fee_pct / 100)

    # Zero out the source debt
    source.balance = 0.0

    # Create new balance-transfer card
    promo_end = start_date + timedelta(days=30 * promo_months)
    bt_card = Debt(
        name=f"BT: {source.name}",
        balance=round(transferred_balance, 2),
        apr=new_apr,
        min_payment=source.min_payment,
        promo_apr=0.0 if new_apr > 0 else None,
        promo_end_date=promo_end if new_apr > 0 else None,
    )
    # If new_apr is 0 for the whole life, no promo needed
    if new_apr == 0:
        bt_card.promo_apr = 0.0
        bt_card.promo_end_date = start_date + timedelta(days=30 * 600)  # effectively forever

    new_debts.append(bt_card)

    return simulate(new_debts, income, expenses, method, extra_payment, start_date, payment_frequency)


def compare(
    debts: list[Debt],
    income: float,
    expenses: float,
    extra: float = 0.0,
    start_date: date | None = None,
    payment_frequency: str = "monthly",
) -> dict:
    """Compare Avalanche vs Snowball strategies.

    Returns:
        Dict with 'avalanche', 'snowball', 'interest_saved', 'months_saved', 'winner'.
    """
    avalanche = simulate(debts, income, expenses, "avalanche", extra, start_date, payment_frequency)
    snowball = simulate(debts, income, expenses, "snowball", extra, start_date, payment_frequency)

    interest_saved = round(snowball.total_interest - avalanche.total_interest, 2)
    months_saved = snowball.months_to_payoff - avalanche.months_to_payoff

    winner = "avalanche" if avalanche.total_interest <= snowball.total_interest else "snowball"

    return {
        "avalanche": avalanche,
        "snowball": snowball,
        "interest_saved": abs(interest_saved),
        "months_saved": abs(months_saved),
        "winner": winner,
    }
