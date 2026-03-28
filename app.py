"""Debt Payoff Simulator — Streamlit App."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.simulator import Debt, simulate, simulate_balance_transfer, compare
from src.charts import (
    PLOT_CONFIG,
    total_debt_chart,
    per_debt_chart,
    cumulative_interest_chart,
    payoff_timeline_chart,
    sensitivity_chart,
    strategy_comparison_chart,
    balance_transfer_comparison_chart,
)
from src.analytics import (
    comparison_summary,
    sensitivity_analysis,
    fun_savings_comparisons,
    payoff_commentary,
    debt_health_score,
    debt_free_countdown,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="💳 Debt Payoff Simulator", page_icon="💳", layout="wide")

st.title("💳 Debt Payoff Simulator")
st.markdown("Compare **Avalanche** vs **Snowball** repayment strategies and find your fastest path to $0.")

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "debts" not in st.session_state:
    st.session_state.debts = [
        {"name": "Store Card", "balance": 800.0, "apr": 29.99, "min_payment": 25.0,
         "promo_apr": None, "promo_end": None},
        {"name": "Credit Card A", "balance": 12000.0, "apr": 22.99, "min_payment": 240.0,
         "promo_apr": None, "promo_end": None},
        {"name": "Personal Loan", "balance": 6500.0, "apr": 11.99, "min_payment": 150.0,
         "promo_apr": None, "promo_end": None},
        {"name": "Credit Card B", "balance": 3200.0, "apr": 18.49, "min_payment": 65.0,
         "promo_apr": 0.0, "promo_end": "2026-09-01"},
        {"name": "Medical Bill", "balance": 2400.0, "apr": 0.0, "min_payment": 100.0,
         "promo_apr": None, "promo_end": None},
    ]

# ---------------------------------------------------------------------------
# Sidebar — Inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("💰 Income & Expenses")
    income = st.number_input("Monthly Take-Home Pay ($)", min_value=0.0, value=3800.0, step=100.0)
    expenses = st.number_input("Monthly Fixed Expenses ($)", min_value=0.0, value=2800.0, step=100.0)
    extra = st.number_input("Extra Monthly Payment ($)", min_value=0.0, value=0.0, step=25.0)

    st.divider()
    st.header("⏱️ Payment Frequency")
    payment_freq = st.radio(
        "How often do you pay?",
        ["Monthly", "Bi-weekly"],
        index=0,
        help="Bi-weekly = 26 half-payments/year = effectively 13 monthly payments. Saves interest!",
    )
    freq_key = "biweekly" if payment_freq == "Bi-weekly" else "monthly"

    st.divider()
    st.header("💳 Your Debts")

    # Add debt form
    with st.expander("➕ Add a Debt", expanded=False):
        new_name = st.text_input("Debt Name", value="", key="new_name")
        new_balance = st.number_input("Balance ($)", min_value=0.0, value=0.0, step=100.0, key="new_bal")
        new_apr = st.number_input("APR (%)", min_value=0.0, value=20.0, step=0.5, key="new_apr")
        new_min = st.number_input("Min Payment ($)", min_value=0.0, value=25.0, step=5.0, key="new_min")
        new_promo_apr = st.number_input("Promo APR (%, leave 0 for none)", min_value=0.0, value=0.0, step=0.5, key="new_promo")
        new_promo_end = st.date_input("Promo End Date", value=None, key="new_promo_end")

        if st.button("Add Debt"):
            if new_name and new_balance > 0:
                entry = {
                    "name": new_name, "balance": new_balance, "apr": new_apr, "min_payment": new_min,
                    "promo_apr": new_promo_apr if new_promo_apr > 0 else None,
                    "promo_end": new_promo_end.isoformat() if new_promo_end else None,
                }
                st.session_state.debts.append(entry)
                st.rerun()

    # Show current debts
    if st.session_state.debts:
        for i, d in enumerate(st.session_state.debts):
            cols = st.columns([3, 1])
            cols[0].markdown(f"**{d['name']}** — ${d['balance']:,.0f} @ {d['apr']}%")
            if cols[1].button("🗑️", key=f"del_{i}"):
                st.session_state.debts.pop(i)
                st.rerun()

# ---------------------------------------------------------------------------
# Build Debt objects
# ---------------------------------------------------------------------------
def _build_debts() -> list[Debt]:
    result = []
    for d in st.session_state.debts:
        promo_end = None
        if d.get("promo_end"):
            try:
                promo_end = date.fromisoformat(d["promo_end"])
            except (ValueError, TypeError):
                pass
        result.append(Debt(
            name=d["name"],
            balance=d["balance"],
            apr=d["apr"],
            min_payment=d["min_payment"],
            promo_apr=d.get("promo_apr"),
            promo_end_date=promo_end,
        ))
    return result

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
if not st.session_state.debts:
    st.info("Add some debts in the sidebar to get started!")
    st.stop()

debts = _build_debts()

# Debt health score
health = debt_health_score(debts, income, expenses)
h_col1, h_col2, h_col3 = st.columns(3)
h_col1.metric("Debt Health Score", f"{health['score']}/100 ({health['grade']})")
h_col2.metric("Debt-to-Income Ratio", f"{health.get('dti', 0):.1f}%")
h_col3.markdown(f"*{health['description']}*")

st.divider()

# Run simulation
if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
    st.session_state.run = True

if st.session_state.get("run"):
    start = date.today()
    comparison = compare(debts, income, expenses, extra, start, freq_key)
    avalanche = comparison["avalanche"]
    snowball = comparison["snowball"]
    summary = comparison_summary(avalanche, snowball)
    winner = summary["winner"]
    best = avalanche if winner == "avalanche" else snowball

    # --- Warning: debt growing / insufficient payments ---
    if best.debt_growing or not best.can_cover_minimums:
        shortfall = best.monthly_shortfall
        st.error(
            f"⚠️ **Your payments can't keep up with interest!** "
            f"You're **${shortfall:,.0f}/month short** of covering minimum payments. "
            f"Debt will grow indefinitely at these numbers. "
            f"Increase income, reduce expenses, or add extra payments to make progress."
        )
    elif avalanche.debt_growing or snowball.debt_growing:
        st.warning(
            "⚠️ One or both strategies can't pay off the debt at current payment levels. "
            "Try increasing your extra monthly payment."
        )

    # --- 0. Debt-Free Countdown ---
    countdown = debt_free_countdown(best)
    st.markdown("---")
    cd_col1, cd_col2, cd_col3 = st.columns(3)
    with cd_col1:
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<h1 style='color:#2ecc71; margin-bottom:0;'>🎯 {countdown['payoff_date'].strftime('%B %Y')}</h1>"
            f"<p style='color:#888; font-size:18px;'>Debt-free date ({winner.title()})</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with cd_col2:
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<h1 style='color:#3498db; margin-bottom:0;'>{countdown['months_remaining']} months</h1>"
            f"<p style='color:#888; font-size:18px;'>to freedom</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with cd_col3:
        pct = countdown["percent_complete"]
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<h1 style='color:#f39c12; margin-bottom:0;'>{pct:.0f}%</h1>"
            f"<p style='color:#888; font-size:18px;'>of journey mapped</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Bi-weekly impact note
    if freq_key == "biweekly":
        monthly_result = compare(debts, income, expenses, extra, start, "monthly")
        monthly_best = monthly_result["avalanche"] if winner == "avalanche" else monthly_result["snowball"]
        biweekly_saved = monthly_best.total_interest - best.total_interest
        biweekly_months = monthly_best.months_to_payoff - best.months_to_payoff
        if biweekly_saved > 0 or biweekly_months > 0:
            st.info(
                f"📅 **Bi-weekly boost:** Saves **${biweekly_saved:,.2f}** in interest "
                f"and **{biweekly_months}** month(s) vs monthly payments!"
            )

    st.divider()

    # --- 1. Strategy Comparison ---
    st.header("📊 Strategy Comparison")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"{'🏆 ' if winner == 'avalanche' else ''}Avalanche")
        st.metric("Months to Payoff", avalanche.months_to_payoff)
        st.metric("Total Interest", f"${avalanche.total_interest:,.2f}")
        st.metric("Total Paid", f"${avalanche.total_paid:,.2f}")
    with col2:
        st.subheader(f"{'🏆 ' if winner == 'snowball' else ''}Snowball")
        st.metric("Months to Payoff", snowball.months_to_payoff)
        st.metric("Total Interest", f"${snowball.total_interest:,.2f}")
        st.metric("Total Paid", f"${snowball.total_paid:,.2f}")

    if summary["interest_saved"] > 0:
        savings = summary["interest_saved"]
        fun = fun_savings_comparisons(savings)
        st.success(
            f"The **{winner.title()}** method saves you **${savings:,.2f}** in interest "
            f"and **{summary['months_saved']}** month(s). "
            + (f"That's {fun[0]}!" if fun else "")
        )

    st.plotly_chart(strategy_comparison_chart(avalanche, snowball), use_container_width=True, config=PLOT_CONFIG)

    # Commentary
    st.markdown("---")
    st.markdown(payoff_commentary(avalanche if winner == "avalanche" else snowball))

    # --- 2. Total Debt Over Time ---
    st.header("📈 Total Debt Over Time")
    st.plotly_chart(total_debt_chart(avalanche, snowball), use_container_width=True, config=PLOT_CONFIG)

    # --- 3. Per-Debt Breakdown ---
    st.header("💳 Per-Debt Breakdown")
    col_a, col_s = st.columns(2)
    with col_a:
        st.subheader("Avalanche")
        st.plotly_chart(per_debt_chart(avalanche, "Avalanche"), use_container_width=True, config=PLOT_CONFIG)
    with col_s:
        st.subheader("Snowball")
        st.plotly_chart(per_debt_chart(snowball, "Snowball"), use_container_width=True, config=PLOT_CONFIG)

    # --- 4. Cumulative Interest ---
    st.header("💰 Cumulative Interest")
    st.plotly_chart(cumulative_interest_chart(avalanche, snowball), use_container_width=True, config=PLOT_CONFIG)

    # --- 5. Payoff Timeline ---
    st.header("📅 Payoff Timeline")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("Avalanche")
        st.plotly_chart(payoff_timeline_chart(avalanche), use_container_width=True, config=PLOT_CONFIG)
    with col_t2:
        st.subheader("Snowball")
        st.plotly_chart(payoff_timeline_chart(snowball), use_container_width=True, config=PLOT_CONFIG)

    # --- 6. Sensitivity Analysis ---
    st.header("🔍 Sensitivity Analysis")
    st.markdown("What if you paid more each month?")
    scenarios = sensitivity_analysis(debts, income, expenses, [0, 50, 100, 150, 200, 300, 500], start)

    sens_data = []
    base_aval = scenarios[0]["avalanche"]
    for s in scenarios:
        aval_months = s["avalanche"]["months"]
        snow_months = s["snowball"]["months"]
        aval_interest = s["avalanche"]["total_interest"]
        # Flag impossible scenarios
        aval_label = f"{aval_months}" if aval_months < 600 else "Never ⚠️"
        snow_label = f"{snow_months}" if snow_months < 600 else "Never ⚠️"
        months_saved = (base_aval["months"] - aval_months) if base_aval["months"] < 600 and aval_months < 600 else 0
        interest_saved = (base_aval["total_interest"] - aval_interest) if base_aval["months"] < 600 and aval_months < 600 else 0
        sens_data.append({
            "Extra Payment": f"${s['extra']:,.0f}",
            "Avalanche Months": aval_label,
            "Snowball Months": snow_label,
            "Months Saved": months_saved if months_saved > 0 else "—",
            "Interest Saved": f"${interest_saved:,.2f}" if interest_saved > 0 else "—",
        })
    st.dataframe(pd.DataFrame(sens_data), use_container_width=True, hide_index=True)
    st.plotly_chart(sensitivity_chart(scenarios), use_container_width=True, config=PLOT_CONFIG)

    # --- 7. Balance Transfer Analysis ---
    st.header("🔄 Balance Transfer Analysis")
    st.markdown("What if you transferred a balance to a low-APR card?")

    if len(debts) > 0:
        bt_cols = st.columns(4)
        with bt_cols[0]:
            debt_names_list = [d.name for d in debts if d.balance > 0]
            bt_debt_name = st.selectbox("Transfer which debt?", debt_names_list, key="bt_debt")
        with bt_cols[1]:
            bt_fee = st.number_input("Transfer fee (%)", min_value=0.0, value=3.0, step=0.5, key="bt_fee")
        with bt_cols[2]:
            bt_apr = st.number_input("New card APR (%)", min_value=0.0, value=0.0, step=0.5, key="bt_apr")
        with bt_cols[3]:
            bt_promo = st.number_input("Promo period (months)", min_value=0, value=15, step=1, key="bt_promo")

        if st.button("📊 Analyze Transfer", key="bt_run"):
            # Find the index in the original debts list
            bt_idx = next(i for i, d in enumerate(debts) if d.name == bt_debt_name)
            bt_result = simulate_balance_transfer(
                debts, bt_idx, bt_fee, bt_apr, bt_promo, income, expenses,
                extra, winner, start, freq_key,
            )
            interest_diff = best.total_interest - bt_result.total_interest
            months_diff = best.months_to_payoff - bt_result.months_to_payoff

            r1, r2 = st.columns(2)
            with r1:
                st.metric("Interest Saved", f"${interest_diff:,.2f}",
                          delta=f"{'saved' if interest_diff > 0 else 'extra cost'}")
            with r2:
                st.metric("Months Saved", f"{months_diff}",
                          delta=f"{'faster' if months_diff > 0 else 'slower'}")

            if interest_diff > 0:
                st.success(f"✅ The balance transfer saves you **${interest_diff:,.2f}**! Do it. 🎉")
            elif interest_diff == 0:
                st.info("🤷 Break-even. Transfer if you want the psychological win.")
            else:
                st.warning(f"⚠️ The transfer costs you **${abs(interest_diff):,.2f}** more. Skip it.")

            st.plotly_chart(
                balance_transfer_comparison_chart(best, bt_result),
                use_container_width=True, config=PLOT_CONFIG,
            )

    # --- 8. Monthly Payment Schedule ---
    st.header("📋 Monthly Payment Schedule")
    method_choice = st.selectbox("View schedule for:", ["Avalanche", "Snowball"])
    chosen = avalanche if method_choice == "Avalanche" else snowball

    with st.expander("Show full schedule", expanded=False):
        schedule_rows = []
        for m in chosen.monthly_payments:
            row = {"Month": m["month"], "Date": m["date"]}
            for dname, dinfo in m["debts"].items():
                row[f"{dname} Payment"] = f"${dinfo['payment']:,.2f}"
                row[f"{dname} Balance"] = f"${dinfo['balance']:,.2f}"
            row["Total Payment"] = f"${m['total_payment']:,.2f}"
            row["Total Remaining"] = f"${m['total_remaining']:,.2f}"
            schedule_rows.append(row)
        st.dataframe(pd.DataFrame(schedule_rows), use_container_width=True, hide_index=True)

    # CSV Export
    csv_buffer = io.StringIO()
    if chosen.monthly_payments:
        # Build header dynamically from debt names
        sample = chosen.monthly_payments[0]
        debt_cols = list(sample["debts"].keys())
        header = ["Month", "Date"]
        for dn in debt_cols:
            header.extend([f"{dn} Payment", f"{dn} Balance"])
        header.extend(["Total Payment", "Total Remaining"])

        writer = csv.writer(csv_buffer)
        writer.writerow(header)
        for m in chosen.monthly_payments:
            row = [m["month"], m["date"]]
            for dn in debt_cols:
                info = m["debts"].get(dn, {"payment": 0, "balance": 0})
                row.extend([f"{info['payment']:.2f}", f"{info['balance']:.2f}"])
            row.extend([f"{m['total_payment']:.2f}", f"{m['total_remaining']:.2f}"])
            writer.writerow(row)

    st.download_button(
        "⬇️ Download Payment Plan (CSV)",
        data=csv_buffer.getvalue(),
        file_name=f"payment_plan_{method_choice.lower()}.csv",
        mime="text/csv",
    )

    # --- 9. Summary Card ---
    st.header("📸 Summary Card")
    card_html = f"""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 16px; padding: 32px; max-width: 500px; margin: auto;
                border: 1px solid #2ecc71; font-family: sans-serif; color: #fafafa;">
        <h2 style="text-align:center; margin-bottom: 8px;">💳 Debt Payoff Plan</h2>
        <p style="text-align:center; color: #888; margin-top: 0;">Best strategy: <b style="color:#2ecc71">{winner.title()}</b></p>
        <hr style="border-color: #333;">
        <div style="display: flex; justify-content: space-around; text-align: center;">
            <div>
                <div style="font-size: 28px; font-weight: bold; color: #2ecc71;">{best.months_to_payoff}</div>
                <div style="color: #888;">months</div>
            </div>
            <div>
                <div style="font-size: 28px; font-weight: bold; color: #e74c3c;">${best.total_interest:,.0f}</div>
                <div style="color: #888;">interest</div>
            </div>
            <div>
                <div style="font-size: 28px; font-weight: bold; color: #3498db;">${best.total_paid:,.0f}</div>
                <div style="color: #888;">total paid</div>
            </div>
        </div>
        <hr style="border-color: #333;">
        <p style="text-align:center; color: #888; font-size: 14px;">
            Debt-free by <b style="color:#f39c12">{best.payoff_date.strftime('%B %Y')}</b>
        </p>
    </div>
    """
    st.components.v1.html(card_html, height=320)
