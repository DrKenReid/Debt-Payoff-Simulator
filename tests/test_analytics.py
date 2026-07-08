"""Tests for analytics: countdown stats, sensitivity analysis, health score."""

from datetime import date

import pytest

from src.analytics import (
    debt_free_countdown,
    debt_health_score,
    fun_savings_comparisons,
    payoff_commentary,
    sensitivity_analysis,
)
from src.simulator import Debt, simulate


def _sample_debts() -> list[Debt]:
    return [
        Debt("Card A", 5000, 24.99, 100),
        Debt("Card B", 8500, 18.99, 170),
    ]


class TestDebtFreeCountdown:
    def test_fields_and_interest_share(self):
        debts = [Debt("Loan", 1200, 12.0, 200)]
        r = simulate(debts, 5000, 4800, "avalanche", start_date=date(2025, 1, 1))
        c = debt_free_countdown(r)
        assert c["payoff_date"] == r.payoff_date
        assert c["months_remaining"] == r.months_to_payoff
        # Principal paid is the original balance
        assert c["total_debt_start"] == pytest.approx(1200, abs=0.01)
        # Interest share matches total_interest / total_paid
        expected = r.total_interest / r.total_paid * 100
        assert c["interest_share"] == pytest.approx(expected, abs=0.1)
        assert 0 < c["interest_share"] < 100

    def test_no_payments(self):
        r = simulate([], 5000, 2000)
        c = debt_free_countdown(r)
        assert c["interest_share"] == 0.0
        assert c["total_debt_start"] == 0.0


class TestSensitivityAnalysis:
    def test_returns_one_row_per_extra(self):
        rows = sensitivity_analysis(_sample_debts(), 4500, 2200, [0, 100, 200], date(2025, 1, 1))
        assert len(rows) == 3
        assert [r["extra"] for r in rows] == [0, 100, 200]

    def test_more_extra_never_worse(self):
        rows = sensitivity_analysis(_sample_debts(), 4500, 2200, [0, 100, 200], date(2025, 1, 1))
        interests = [r["avalanche"]["total_interest"] for r in rows]
        assert interests == sorted(interests, reverse=True)

    def test_respects_payment_frequency(self):
        monthly = sensitivity_analysis(
            _sample_debts(), 4500, 2200, [0], date(2025, 1, 1), "monthly"
        )
        biweekly = sensitivity_analysis(
            _sample_debts(), 4500, 2200, [0], date(2025, 1, 1), "biweekly"
        )
        assert (
            biweekly[0]["avalanche"]["total_interest"]
            < monthly[0]["avalanche"]["total_interest"]
        )


class TestDebtHealthScore:
    def test_no_debt_is_perfect(self):
        assert debt_health_score([], 5000, 2000)["score"] == 100

    def test_score_bounds(self):
        bad = debt_health_score([Debt("Huge", 100000, 29.99, 2000)], 3000, 2500)
        good = debt_health_score([Debt("Tiny", 500, 5.0, 25)], 8000, 3000)
        assert 0 <= bad["score"] <= 100
        assert 0 <= good["score"] <= 100
        assert good["score"] > bad["score"]


class TestTextHelpers:
    def test_fun_savings_comparisons(self):
        out = fun_savings_comparisons(500)
        assert out
        assert all(isinstance(s, str) for s in out)
        assert fun_savings_comparisons(0) == []

    def test_payoff_commentary_is_text(self):
        r = simulate(_sample_debts(), 4500, 2200, "avalanche", start_date=date(2025, 1, 1))
        text = payoff_commentary(r)
        assert isinstance(text, str)
        assert "debt-free" in text
