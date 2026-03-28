"""Comprehensive tests for the debt simulation engine."""

from datetime import date
from src.simulator import Debt, simulate, compare, _effective_apr


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
        # Debt where min payment barely covers interest
        debts = [Debt("Stuck", 100000, 30.0, 10)]
        r = simulate(debts, 2500, 2480, "avalanche", start_date=date(2025, 1, 1))
        assert r.months_to_payoff <= 600


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
