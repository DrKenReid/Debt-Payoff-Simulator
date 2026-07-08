"""Debt payoff simulation engine — Avalanche & Snowball strategies."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from dateutil.relativedelta import relativedelta

MAX_MONTHS = 600


@dataclass
class Debt:
    name: str
    balance: float
    apr: float  # as percentage, e.g. 24.99
    min_payment: float
    promo_apr: float | None = None
    promo_end_date: date | None = None


@dataclass
class BalanceTransfer:
    """A single balance-transfer scenario applied to one debt."""

    debt_name: str
    fee_pct: float  # one-time fee, added to the transferred balance
    new_apr: float  # APR once the promo period ends
    promo_months: int  # months of 0% intro APR


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

    The model assumes the entire monthly budget (income − expenses + extra)
    goes toward debt: minimum payments first, then the remainder to the
    strategy's priority debt. Interest compounds monthly at APR / 12,
    applied before each payment.

    Args:
        debts: List of debts to pay off.
        monthly_income: Monthly take-home pay.
        monthly_expenses: Monthly fixed expenses (non-debt).
        method: "avalanche" (highest APR first) or "snowball" (lowest balance first).
        extra_payment: Additional monthly payment toward debt.
        start_date: Simulation start date (defaults to today).
        payment_frequency: "monthly" or "biweekly". Bi-weekly makes 26
            half-payments per year — 13 full payments — so the monthly
            debt budget is multiplied by 13/12.

    Returns:
        SimulationResult with month-by-month breakdown.
    """
    if start_date is None:
        start_date = date.today()

    active = [replace(d) for d in debts if d.balance > 0]

    if not active:
        return SimulationResult(
            method=method,
            months_to_payoff=0,
            payoff_date=start_date,
            debt_names=[d.name for d in debts],
        )

    result = SimulationResult(
        method=method,
        debt_names=[d.name for d in active],
    )

    total_interest = 0.0
    total_paid = 0.0

    # Bi-weekly: 26 half-payments/year = 13 full payments = 13/12 of the budget
    boost = 13 / 12 if payment_frequency == "biweekly" else 1.0
    monthly_budget = max((monthly_income - monthly_expenses + extra_payment) * boost, 0.0)

    sum_min = sum(d.min_payment for d in active)
    result.can_cover_minimums = monthly_budget >= sum_min
    result.monthly_shortfall = max(0.0, sum_min - monthly_budget)

    for month in range(1, MAX_MONTHS + 1):
        current_date = start_date + relativedelta(months=month)
        month_record: dict = {"month": month, "date": current_date.isoformat(), "debts": {}}

        # Apply interest
        interest_this_month: dict[str, float] = {}
        for d in active:
            apr = _effective_apr(d, current_date)
            interest = d.balance * (apr / 100 / 12)
            d.balance += interest
            interest_this_month[d.name] = interest
            total_interest += interest

        # Priority order for the strategy
        if method == "avalanche":
            order = sorted(active, key=lambda d: (-_effective_apr(d, current_date), d.balance))
        else:  # snowball
            order = sorted(active, key=lambda d: d.balance)

        # Pay minimums first
        remaining = monthly_budget
        payments = {d.name: 0.0 for d in active}
        for d in active:
            pay = min(d.min_payment, d.balance, remaining)
            payments[d.name] = pay
            remaining -= pay

        # Distribute the remainder to priority debts
        for d in order:
            if remaining <= 0:
                break
            extra = min(remaining, d.balance - payments[d.name])
            if extra > 0:
                payments[d.name] += extra
                remaining -= extra

        # Apply payments
        month_total_payment = 0.0
        for d in active:
            d.balance -= payments[d.name]
            if d.balance < 0.01:
                d.balance = 0.0
            month_total_payment += payments[d.name]
            month_record["debts"][d.name] = {
                "balance": round(d.balance, 2),
                "payment": round(payments[d.name], 2),
                "interest": round(interest_this_month[d.name], 2),
            }

        total_paid += month_total_payment
        month_record["total_payment"] = round(month_total_payment, 2)
        month_record["total_remaining"] = round(sum(d.balance for d in active), 2)
        result.monthly_payments.append(month_record)

        # Detect if debt is growing (balance higher than previous month)
        if month >= 3:
            prev_remaining = result.monthly_payments[-2]["total_remaining"]
            curr_remaining = month_record["total_remaining"]
            prev2_remaining = result.monthly_payments[-3]["total_remaining"]
            if curr_remaining > prev_remaining > prev2_remaining:
                # Debt is growing for 3 consecutive months — flag and stop
                result.debt_growing = True
                result.months_to_payoff = MAX_MONTHS
                result.payoff_date = start_date + relativedelta(months=MAX_MONTHS)
                break

        # Remove paid-off debts
        active = [d for d in active if d.balance > 0]

        if not active:
            result.months_to_payoff = month
            result.payoff_date = current_date
            break
    else:
        result.months_to_payoff = MAX_MONTHS
        result.payoff_date = start_date + relativedelta(months=MAX_MONTHS)

    result.total_interest = round(total_interest, 2)
    result.total_paid = round(total_paid, 2)
    return result


def apply_balance_transfers(
    debts: list[Debt],
    transfers: list[BalanceTransfer],
    start_date: date,
) -> list[Debt]:
    """Return a new debt list with each transfer applied in order.

    Each transfer zeroes out its source debt and adds a new card holding
    the balance plus the transfer fee, at 0% until the promo end date and
    the new APR afterwards. Transfers naming an unknown or already-zero
    debt are skipped.
    """
    new_debts = [replace(d) for d in debts]
    for t in transfers:
        source = next((d for d in new_debts if d.name == t.debt_name and d.balance > 0), None)
        if source is None:
            continue
        transferred_balance = source.balance * (1 + t.fee_pct / 100)
        source.balance = 0.0
        new_debts.append(Debt(
            name=f"BT: {t.debt_name}",
            balance=round(transferred_balance, 2),
            apr=t.new_apr,
            min_payment=source.min_payment,
            promo_apr=0.0,
            promo_end_date=start_date + relativedelta(months=t.promo_months),
        ))
    return new_debts


def simulate_balance_transfer(
    debts: list[Debt],
    transfers: list[BalanceTransfer],
    income: float,
    expenses: float,
    extra_payment: float = 0.0,
    method: str = "avalanche",
    start_date: date | None = None,
    payment_frequency: str = "monthly",
) -> SimulationResult:
    """Simulate paying off debts after one or more balance transfers."""
    if start_date is None:
        start_date = date.today()
    new_debts = apply_balance_transfers(debts, transfers, start_date)
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
