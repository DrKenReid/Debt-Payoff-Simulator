"""Comprehensive tests for the debt simulation engine."""

from datetime import date

import pytest

from src.simulator import (
    BalanceTransfer,
    Debt,
    apply_balance_transfers,
    compare,
    simulate,
    simulate_balance_transfer,
    _effective_apr,
)


def _sample_debts() -> list[Debt]:
    return [
        Debt("Card A", 5000, 24.99, 100),
        Debt("Card B", 8500, 18.99, 170),
        Debt("Store Card", 1200, 29.99, 25),
    ]


class TestDebt:
    def test_debt_creation(self):
        d = Debt("Test", 1000, 20.0, 50)
        assert d.name == "Test"
        assert d.balance == 1000
        assert d.apr == 20.0
        assert d.min_payment == 50
        assert d.promo_apr is None
        assert d.promo_end_date is None

    def test_debt_with_promo(self):
        d = Debt("Promo", 2000, 25.0, 50, promo_apr=0.0, promo_end_date=date(2025, 6, 1))
        assert d.promo_apr == 0.0
        assert d.promo_end_date == date(2025, 6, 1)


class TestEffectiveAPR:
    def test_no_promo(self):
        d = Debt("X", 1000, 20.0, 50)
        assert _effective_apr(d, date(2025, 1, 1)) == 20.0

    def test_during_promo(self):
        d = Debt("X", 1000, 20.0, 50, promo_apr=0.0, promo_end_date=date(2025, 12, 1))
        assert _effective_apr(d, date(2025, 6, 1)) == 0.0

    def test_after_promo(self):
        d = Debt("X", 1000, 20.0, 50, promo_apr=0.0, promo_end_date=date(2025, 6, 1))
        assert _effective_apr(d, date(2025, 7, 1)) == 20.0


class TestSimulate:
    def test_empty_debts(self):
        r = simulate([], 5000, 2000, "avalanche")
        assert r.months_to_payoff == 0
        assert r.total_interest == 0

    def test_zero_balance_debt(self):
        debts = [Debt("Zero", 0, 20.0, 50)]
        r = simulate(debts, 5000, 2000, "avalanche")
        assert r.months_to_payoff == 0

    def test_single_debt(self):
        debts = [Debt("Only", 1000, 12.0, 50)]
        r = simulate(debts, 5000, 2000, "avalanche", start_date=date(2025, 1, 1))
        assert r.months_to_payoff > 0
        assert r.total_interest > 0
        assert r.total_paid > 1000

    def test_avalanche_payoff(self):
        debts = _sample_debts()
        r = simulate(debts, 4500, 2200, "avalanche", start_date=date(2025, 1, 1))
        assert r.months_to_payoff > 0
        assert r.method == "avalanche"
        assert r.total_paid > 0

    def test_snowball_payoff(self):
        debts = _sample_debts()
        r = simulate(debts, 4500, 2200, "snowball", start_date=date(2025, 1, 1))
        assert r.months_to_payoff > 0
        assert r.method == "snowball"

    def test_extra_payment_reduces_interest(self):
        debts = _sample_debts()
        r0 = simulate(debts, 4500, 2200, "avalanche", 0, date(2025, 1, 1))
        r200 = simulate(debts, 4500, 2200, "avalanche", 200, date(2025, 1, 1))
        assert r200.months_to_payoff <= r0.months_to_payoff
        assert r200.total_interest < r0.total_interest

    def test_promo_apr_effect(self):
        debts = [
            Debt("Promo", 5000, 24.99, 100, promo_apr=0.0, promo_end_date=date(2026, 1, 1)),
        ]
        r = simulate(debts, 5000, 2000, "avalanche", start_date=date(2025, 1, 1))
        # During promo period, interest should be much lower
        debts_no_promo = [Debt("NoPromo", 5000, 24.99, 100)]
        r2 = simulate(debts_no_promo, 5000, 2000, "avalanche", start_date=date(2025, 1, 1))
        assert r.total_interest < r2.total_interest

    def test_monthly_payments_structure(self):
        debts = [Debt("Test", 500, 12.0, 50)]
        r = simulate(debts, 5000, 2000, "avalanche", start_date=date(2025, 1, 1))
        assert len(r.monthly_payments) > 0
        m = r.monthly_payments[0]
        assert "month" in m
        assert "date" in m
        assert "debts" in m
        assert "total_payment" in m
        assert "total_remaining" in m

    def test_max_months_safety(self):
        # Debt where the budget can't even cover interest
        debts = [Debt("Stuck", 100000, 30.0, 10)]
        r = simulate(debts, 2500, 2480, "avalanche", start_date=date(2025, 1, 1))
        assert r.months_to_payoff == 600
        assert r.debt_growing is True
        assert r.payoff_date == date(2075, 1, 1)

    def test_known_amortization(self):
        """Hand-computed amortization: $1,200 at 12% APR, $200/month budget.

        Monthly rate is 1%; interest accrues before each payment. Worked by
        hand, this pays off in 7 months with $43.86 total interest.
        """
        debts = [Debt("Loan", 1200, 12.0, 200)]
        r = simulate(debts, 5000, 4800, "avalanche", start_date=date(2025, 1, 1))
        assert r.months_to_payoff == 7
        assert r.total_interest == pytest.approx(43.86, abs=0.01)
        assert r.total_paid == pytest.approx(1243.86, abs=0.01)
        assert r.payoff_date == date(2025, 8, 1)

    def test_calendar_month_dates(self):
        # Payoff dates advance by calendar months, not 30-day blocks
        debts = [Debt("Loan", 1000, 0.0, 100)]
        r = simulate(debts, 5000, 4900, "avalanche", start_date=date(2025, 1, 31))
        assert r.months_to_payoff == 10
        assert r.payoff_date == date(2025, 11, 30)

    def test_shortfall_detection(self):
        debts = [Debt("A", 5000, 20.0, 150), Debt("B", 3000, 15.0, 50)]
        r = simulate(debts, 2500, 2350, "avalanche", start_date=date(2025, 1, 1))
        assert r.can_cover_minimums is False
        assert r.monthly_shortfall == pytest.approx(50.0)

    def test_biweekly_boosts_budget_not_income(self):
        """Bi-weekly = 13/12 of the debt budget, not 13/12 of gross income."""
        debts = [Debt("Loan", 12000, 18.0, 250)]
        monthly = simulate(debts, 4000, 3400, "avalanche", start_date=date(2025, 1, 1))
        biweekly = simulate(debts, 4000, 3400, "avalanche",
                            start_date=date(2025, 1, 1), payment_frequency="biweekly")
        assert biweekly.total_interest < monthly.total_interest
        assert biweekly.months_to_payoff <= monthly.months_to_payoff
        # First month's payment is exactly the budget × 13/12
        budget = 4000 - 3400
        assert biweekly.monthly_payments[0]["total_payment"] == pytest.approx(
            round(budget * 13 / 12, 2)
        )


class TestCompare:
    def test_compare_returns_both(self):
        debts = _sample_debts()
        result = compare(debts, 4500, 2200, 0, date(2025, 1, 1))
        assert "avalanche" in result
        assert "snowball" in result
        assert "interest_saved" in result
        assert "months_saved" in result
        assert "winner" in result

    def test_avalanche_usually_wins_on_interest(self):
        debts = _sample_debts()
        result = compare(debts, 4500, 2200, 0, date(2025, 1, 1))
        # Avalanche should save on interest (or tie)
        assert result["avalanche"].total_interest <= result["snowball"].total_interest


class TestBalanceTransfer:
    def test_apply_transfers(self):
        debts = _sample_debts()
        transfers = [BalanceTransfer("Card A", fee_pct=3.0, new_apr=15.99, promo_months=12)]
        new_debts = apply_balance_transfers(debts, transfers, date(2025, 1, 1))

        # Originals are untouched
        assert debts[0].balance == 5000

        source = next(d for d in new_debts if d.name == "Card A")
        bt_card = next(d for d in new_debts if d.name == "BT: Card A")
        assert source.balance == 0.0
        assert bt_card.balance == pytest.approx(5150.0)  # 5000 × 1.03
        assert bt_card.promo_apr == 0.0
        assert bt_card.promo_end_date == date(2026, 1, 1)
        assert bt_card.apr == 15.99

    def test_unknown_debt_skipped(self):
        debts = _sample_debts()
        transfers = [BalanceTransfer("Nonexistent", 3.0, 0.0, 12)]
        new_debts = apply_balance_transfers(debts, transfers, date(2025, 1, 1))
        assert len(new_debts) == len(debts)

    def test_zero_promo_transfer_saves_interest(self):
        debts = _sample_debts()
        baseline = simulate(debts, 4500, 2200, "avalanche", start_date=date(2025, 1, 1))
        transfers = [BalanceTransfer("Card A", fee_pct=3.0, new_apr=24.99, promo_months=18)]
        with_bt = simulate_balance_transfer(
            debts, transfers, 4500, 2200, method="avalanche", start_date=date(2025, 1, 1)
        )
        assert with_bt.total_interest < baseline.total_interest
