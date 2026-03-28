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
st.set_page_config(page_title="Debt Payoff Simulator", page_icon="💳", layout="wide")

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
    st.markdown("What if you transferred balances to low-APR cards? Add one or more scenarios below.")

    if len(debts) > 0:
        if "bt_scenarios" not in st.session_state:
            st.session_state.bt_scenarios = [
                {"debt": "", "fee": 3.0, "apr": 0.0, "promo": 15}
            ]

        debt_names_list = [d.name for d in debts if d.balance > 0]

        for i, scenario in enumerate(st.session_state.bt_scenarios):
            bt_cols = st.columns([3, 1.5, 1.5, 1.5, 0.5])
            with bt_cols[0]:
                default_idx = debt_names_list.index(scenario["debt"]) if scenario["debt"] in debt_names_list else 0
                st.session_state.bt_scenarios[i]["debt"] = st.selectbox(
                    "Transfer which debt?", debt_names_list, index=default_idx, key=f"bt_debt_{i}",
                )
            with bt_cols[1]:
                st.session_state.bt_scenarios[i]["fee"] = st.number_input(
                    "Fee (%)", min_value=0.0, value=scenario["fee"], step=0.5, key=f"bt_fee_{i}",
                )
            with bt_cols[2]:
                st.session_state.bt_scenarios[i]["apr"] = st.number_input(
                    "New APR (%)", min_value=0.0, value=scenario["apr"], step=0.5, key=f"bt_apr_{i}",
                )
            with bt_cols[3]:
                st.session_state.bt_scenarios[i]["promo"] = st.number_input(
                    "Promo (mo)", min_value=0, value=scenario["promo"], step=1, key=f"bt_promo_{i}",
                )
            with bt_cols[4]:
                st.markdown("<br>", unsafe_allow_html=True)
                if len(st.session_state.bt_scenarios) > 1:
                    if st.button("🗑️", key=f"bt_del_{i}"):
                        st.session_state.bt_scenarios.pop(i)
                        st.rerun()

        if st.button("➕ Add Another Transfer", key="bt_add"):
            st.session_state.bt_scenarios.append({"debt": debt_names_list[0], "fee": 3.0, "apr": 0.0, "promo": 15})
            st.rerun()

        if st.button("📊 Analyze Transfers", key="bt_run"):
            import copy
            # Apply all transfers sequentially
            modified_debts = [copy.copy(d) for d in debts]
            for scenario in st.session_state.bt_scenarios:
                bt_name = scenario["debt"]
                bt_idx = next((i for i, d in enumerate(modified_debts) if d.name == bt_name and d.balance > 0), None)
                if bt_idx is not None:
                    source = modified_debts[bt_idx]
                    transferred_balance = source.balance * (1 + scenario["fee"] / 100)
                    source.balance = 0.0
                    promo_end = start + timedelta(days=30 * scenario["promo"])
                    bt_card = Debt(
                        name=f"BT: {bt_name}",
                        balance=round(transferred_balance, 2),
                        apr=scenario["apr"],
                        min_payment=source.min_payment,
                        promo_apr=0.0 if scenario["apr"] > 0 else None,
                        promo_end_date=promo_end if scenario["apr"] > 0 else None,
                    )
                    if scenario["apr"] == 0:
                        bt_card.promo_apr = 0.0
                        bt_card.promo_end_date = start + timedelta(days=30 * 600)
                    modified_debts.append(bt_card)

            bt_result = simulate(modified_debts, income, expenses, winner, extra, start, freq_key)
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
                st.success(f"✅ The balance transfer(s) save you **${interest_diff:,.2f}**! Do it. 🎉")
            elif interest_diff == 0:
                st.info("🤷 Break-even. Transfer if you want the psychological win.")
            else:
                st.warning(f"⚠️ The transfer(s) cost you **${abs(interest_diff):,.2f}** more. Skip it.")

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

    # --- 9. Plain English Summary ---
    st.header("📝 What Does This Actually Mean?")

    total_debt = sum(d.balance for d in debts)

    def _payoff_order(res):
        """Return list of (name, month) in the order debts get paid off."""
        alive = set(res.debt_names)
        order = []
        for m in res.monthly_payments:
            still = set(n for n, info in m["debts"].items() if info["balance"] > 0)
            for name in (alive - still):
                order.append((name, m["month"]))
            alive = still
        return order

    aval_order = _payoff_order(avalanche)
    snow_order = _payoff_order(snowball)

    def _order_text(order_list):
        parts = []
        for name, mo in order_list:
            d_info = next((d for d in debts if d.name == name), None)
            apr_note = f" ({d_info.apr}% APR)" if d_info and d_info.apr > 0 else " (0% interest)"
            parts.append(f"**{name}**{apr_note} in month {mo}")
        return ", then ".join(parts)

    col_summary_a, col_summary_s = st.columns(2)

    with col_summary_a:
        st.subheader(f"{'🏆 ' if winner == 'avalanche' else ''}Avalanche")
        st.markdown(
            f"You'd be **debt-free in {avalanche.months_to_payoff} months** "
            f"({avalanche.payoff_date.strftime('%B %Y')}), "
            f"paying **${avalanche.total_interest:,.0f} in interest** on top of "
            f"your ${total_debt:,.0f} debt."
        )
        st.markdown(
            f"This method attacks your **highest interest rate first**, saving you the most money. "
            f"The trade-off: your smaller balances stick around longer, which can feel slow."
        )
        st.markdown(f"**Payoff order:** {_order_text(aval_order)}")

    with col_summary_s:
        st.subheader(f"{'🏆 ' if winner == 'snowball' else ''}Snowball")
        st.markdown(
            f"You'd be **debt-free in {snowball.months_to_payoff} months** "
            f"({snowball.payoff_date.strftime('%B %Y')}), "
            f"paying **${snowball.total_interest:,.0f} in interest** on top of "
            f"your ${total_debt:,.0f} debt."
        )
        st.markdown(
            f"This method attacks your **smallest balance first**, giving you quick wins. "
            f"The trade-off: high-interest debts grow in the background, costing more overall."
        )
        st.markdown(f"**Payoff order:** {_order_text(snow_order)}")

    interest_diff = abs(avalanche.total_interest - snowball.total_interest)
    months_diff = abs(avalanche.months_to_payoff - snowball.months_to_payoff)
    if interest_diff > 0:
        st.markdown("---")
        better = "Avalanche" if winner == "avalanche" else "Snowball"
        worse = "Snowball" if winner == "avalanche" else "Avalanche"
        months_note = f" and **{months_diff} month{'s' if months_diff != 1 else ''} sooner**" if months_diff > 0 else ""
        st.markdown(
            f"**Bottom line:** {better} saves you **${interest_diff:,.0f}**{months_note} "
            f"compared to {worse}. "
            f"If you want to save money, go with **{better}**. "
            f"If you need the motivation of crossing debts off the list quickly, "
            f"**Snowball** is psychologically easier — just know it costs a bit more."
        )

    # --- 10. Summary Card ---
    st.header("📸 Summary Card")
    st.markdown("Customize and share your debt payoff plan.")

    # Theme presets
    CARD_THEMES = {
        "Midnight": {"bg1": "#1a1a2e", "bg2": "#16213e", "accent": "#2ecc71", "text": "#fafafa", "interest": "#e74c3c", "total": "#3498db", "date": "#f39c12", "muted": "#888"},
        "Ocean": {"bg1": "#0f3460", "bg2": "#16213e", "accent": "#00d2ff", "text": "#e8e8e8", "interest": "#ff6b6b", "total": "#48dbfb", "date": "#feca57", "muted": "#7f8fa6"},
        "Sunset": {"bg1": "#2d1b69", "bg2": "#11052c", "accent": "#f97316", "text": "#fafafa", "interest": "#ef4444", "total": "#a78bfa", "date": "#fbbf24", "muted": "#9ca3af"},
        "Forest": {"bg1": "#1b2e1b", "bg2": "#0d1f0d", "accent": "#4ade80", "text": "#f0fdf4", "interest": "#f87171", "total": "#67e8f9", "date": "#fde047", "muted": "#6b7280"},
        "Minimal Light": {"bg1": "#ffffff", "bg2": "#f8f9fa", "accent": "#111827", "text": "#111827", "interest": "#dc2626", "total": "#2563eb", "date": "#d97706", "muted": "#6b7280"},
        "Rose": {"bg1": "#1a1a2e", "bg2": "#2d1f3d", "accent": "#f472b6", "text": "#fdf2f8", "interest": "#fb7185", "total": "#c084fc", "date": "#fbbf24", "muted": "#9ca3af"},
    }

    card_cols = st.columns([2, 2, 2])
    with card_cols[0]:
        theme_name = st.selectbox("Theme", list(CARD_THEMES.keys()), key="card_theme")
    theme = CARD_THEMES[theme_name]

    # Content options
    with card_cols[1]:
        card_title = st.text_input("Card Title", value="💳 Debt Payoff Plan", key="card_title")
    with card_cols[2]:
        card_strategy_display = st.selectbox(
            "Show strategy as",
            ["Winner only", "Both strategies", "None"],
            key="card_strategy",
        )

    content_cols = st.columns(4)
    with content_cols[0]:
        show_months = st.checkbox("Months to payoff", value=True, key="card_months")
    with content_cols[1]:
        show_interest = st.checkbox("Total interest", value=True, key="card_interest")
    with content_cols[2]:
        show_total_paid = st.checkbox("Total paid", value=True, key="card_total")
    with content_cols[3]:
        show_date = st.checkbox("Debt-free date", value=True, key="card_date")

    show_debt_list = st.checkbox("Show individual debts", value=False, key="card_debts")
    show_plan = st.checkbox("Show payment plan breakdown", value=False, key="card_plan")

    if show_plan:
        plan_strategy = st.radio("Strategy for plan", ["Avalanche", "Snowball"], horizontal=True, key="card_plan_strategy")
        plan_result = avalanche if plan_strategy == "Avalanche" else snowball
    else:
        plan_result = None

    # Build strategy line
    if card_strategy_display == "Winner only":
        strategy_line = f'<p style="text-align:center; color: {theme["muted"]}; margin-top: 0;">Best strategy: <b style="color:{theme["accent"]}">{winner.title()}</b></p>'
    elif card_strategy_display == "Both strategies":
        aval_tag = f'<b style="color:{theme["accent"]}">Avalanche</b> {avalanche.months_to_payoff}mo / ${avalanche.total_interest:,.0f} int'
        snow_tag = f'<b style="color:{theme["accent"]}">Snowball</b> {snowball.months_to_payoff}mo / ${snowball.total_interest:,.0f} int'
        strategy_line = f'<p style="text-align:center; color: {theme["muted"]}; margin-top: 0; font-size: 13px;">{aval_tag}&nbsp;&nbsp;•&nbsp;&nbsp;{snow_tag}</p>'
    else:
        strategy_line = ""

    # Build stats
    stat_blocks = []
    if show_months:
        stat_blocks.append(f'<div><div style="font-size: 28px; font-weight: bold; color: {theme["accent"]};">{best.months_to_payoff}</div><div style="color: {theme["muted"]};">months</div></div>')
    if show_interest:
        stat_blocks.append(f'<div><div style="font-size: 28px; font-weight: bold; color: {theme["interest"]};">${best.total_interest:,.0f}</div><div style="color: {theme["muted"]};">interest</div></div>')
    if show_total_paid:
        stat_blocks.append(f'<div><div style="font-size: 28px; font-weight: bold; color: {theme["total"]};">${best.total_paid:,.0f}</div><div style="color: {theme["muted"]};">total paid</div></div>')
    stats_html = "\n".join(stat_blocks)

    # Build debt list
    debt_list_html = ""
    if show_debt_list:
        debt_items = "".join(
            f'<div style="display:flex; justify-content:space-between; padding: 2px 0;">'
            f'<span>{d.name}</span><span style="color:{theme["accent"]}">${d.balance:,.0f}</span></div>'
            for d in debts if d.balance > 0
        )
        debt_list_html = f'<hr style="border-color: #333;"><div style="font-size: 13px; color: {theme["muted"]};">{debt_items}</div>'

    # Build payment plan breakdown
    plan_html = ""
    plan_rows = 0
    if show_plan and plan_result and plan_result.monthly_payments:
        # For each debt, find: months active, typical payment, and when paid off
        debt_plans = []
        for dname in plan_result.debt_names:
            payments_for_debt = []
            paid_off_month = None
            for m in plan_result.monthly_payments:
                info = m["debts"].get(dname)
                if info and info["balance"] > 0:
                    payments_for_debt.append(info["payment"])
                elif info and info["balance"] == 0 and payments_for_debt:
                    payments_for_debt.append(info["payment"])
                    paid_off_month = m["month"]
                    break
                elif not info and paid_off_month is None and payments_for_debt:
                    paid_off_month = m["month"] - 1
                    break
            if not paid_off_month and payments_for_debt:
                paid_off_month = len(plan_result.monthly_payments)
            if payments_for_debt:
                avg_payment = sum(payments_for_debt) / len(payments_for_debt)
                debt_plans.append((dname, len(payments_for_debt), avg_payment, paid_off_month))

        plan_strategy_name = "Avalanche" if plan_result.method == "avalanche" else "Snowball"
        plan_items = "".join(
            f'<div style="padding: 3px 0;">'
            f'<span style="color:{theme["accent"]}">→</span> '
            f'{name}: ~<b>${avg_pay:,.0f}/mo</b> for <b>{months}mo</b>'
            f'</div>'
            for name, months, avg_pay, _ in debt_plans
        )
        plan_rows = len(debt_plans)
        plan_html = (
            f'<hr style="border-color: #333;">'
            f'<div style="font-size: 13px; color: {theme["muted"]};">'
            f'<div style="text-align:center; margin-bottom:6px; color:{theme["text"]}; font-size:14px;">'
            f'<b>{plan_strategy_name} Plan</b></div>'
            f'{plan_items}</div>'
        )

    # Build date line
    date_html = ""
    if show_date:
        date_html = f'<hr style="border-color: #333;"><p style="text-align:center; color: {theme["muted"]}; font-size: 14px;">Debt-free by <b style="color:{theme["date"]}">{best.payoff_date.strftime("%B %Y")}</b></p>'

    card_html = f"""
    <div style="background: linear-gradient(135deg, {theme["bg1"]} 0%, {theme["bg2"]} 100%);
                border-radius: 16px; padding: 32px; max-width: 500px; margin: auto;
                border: 1px solid {theme["accent"]}; font-family: sans-serif; color: {theme["text"]};">
        <h2 style="text-align:center; margin-bottom: 8px;">{card_title}</h2>
        {strategy_line}
        <hr style="border-color: #333;">
        <div style="display: flex; justify-content: space-around; text-align: center;">
            {stats_html}
        </div>
        {debt_list_html}
        {plan_html}
        {date_html}
    </div>
    """
    card_height = 280 + (30 * len(debts) if show_debt_list else 0) + (35 * plan_rows + 40 if plan_rows > 0 else 0) + (40 if show_date else 0)
    st.components.v1.html(card_html, height=card_height)
