"""Plotly chart builders for the Debt Payoff Simulator (dark theme)."""

from __future__ import annotations

import plotly.graph_objects as go
from src.simulator import SimulationResult

COLORS = {
    "green": "#2ecc71",
    "red": "#e74c3c",
    "blue": "#3498db",
    "gold": "#f39c12",
    "purple": "#9b59b6",
    "cyan": "#1abc9c",
    "orange": "#e67e22",
    "pink": "#e91e63",
}

PALETTE = list(COLORS.values())

PLOT_CONFIG = {
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"],
    "toImageButtonOptions": {"format": "png", "height": 700, "width": 1200, "scale": 2},
    "displaylogo": False,
}

_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font=dict(color="#fafafa"),
    margin=dict(l=40, r=40, t=50, b=40),
)


def _base_fig(title: str, **kwargs) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=title, **_LAYOUT, **kwargs)
    return fig


def total_debt_chart(avalanche: SimulationResult, snowball: SimulationResult) -> go.Figure:
    """Dual line chart of total remaining debt over time."""
    fig = _base_fig("📈 Total Debt Over Time")
    for res, name, color in [
        (avalanche, "Avalanche", COLORS["green"]),
        (snowball, "Snowball", COLORS["blue"]),
    ]:
        months = [m["month"] for m in res.monthly_payments]
        remaining = [m["total_remaining"] for m in res.monthly_payments]
        fig.add_trace(go.Scatter(
            x=months, y=remaining, mode="lines", name=name,
            line=dict(color=color, width=2),
            hovertemplate="Month: %{x} | Remaining: $%{y:,.2f}<extra>" + name + "</extra>",
        ))
    fig.update_layout(xaxis_title="Month", yaxis_title="Remaining Debt ($)",
                      yaxis_tickprefix="$", yaxis_tickformat=",")
    return fig


def per_debt_chart(result: SimulationResult, method_name: str) -> go.Figure:
    """Stacked area chart showing each debt's balance over time."""
    fig = _base_fig(f"💳 Per-Debt Breakdown ({method_name.title()})")
    debt_names = result.debt_names
    months = [m["month"] for m in result.monthly_payments]

    for i, name in enumerate(debt_names):
        balances = []
        for m in result.monthly_payments:
            bal = m["debts"].get(name, {}).get("balance", 0)
            balances.append(bal)
        fig.add_trace(go.Scatter(
            x=months, y=balances, mode="lines", name=name,
            stackgroup="one", line=dict(color=PALETTE[i % len(PALETTE)]),
            hovertemplate="Month: %{x} | " + name + " | Balance: $%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(xaxis_title="Month", yaxis_title="Balance ($)",
                      yaxis_tickprefix="$", yaxis_tickformat=",")
    return fig


def cumulative_interest_chart(avalanche: SimulationResult, snowball: SimulationResult) -> go.Figure:
    """Cumulative interest paid over time for both methods."""
    fig = _base_fig("💰 Cumulative Interest Paid")

    for res, name, color in [
        (avalanche, "Avalanche", COLORS["green"]),
        (snowball, "Snowball", COLORS["red"]),
    ]:
        months = [m["month"] for m in res.monthly_payments]
        cum_interest = []
        running = 0.0
        for m in res.monthly_payments:
            for d in m["debts"].values():
                running += d.get("interest", 0)
            cum_interest.append(round(running, 2))
        fig.add_trace(go.Scatter(
            x=months, y=cum_interest, mode="lines", name=name,
            line=dict(color=color, width=2),
            hovertemplate="Month: %{x} | Total Interest: $%{y:,.2f}<extra>" + name + "</extra>",
        ))
    fig.update_layout(xaxis_title="Month", yaxis_title="Cumulative Interest ($)",
                      yaxis_tickprefix="$", yaxis_tickformat=",")
    return fig


def payoff_timeline_chart(result: SimulationResult) -> go.Figure:
    """Horizontal bar chart showing when each debt gets paid off."""
    fig = _base_fig(f"📅 Payoff Timeline ({result.method.title()})")
    debt_names = result.debt_names
    payoff_months = {}

    for m in result.monthly_payments:
        for name in debt_names:
            if name not in payoff_months:
                bal = m["debts"].get(name, {}).get("balance", None)
                if bal is not None and bal <= 0:
                    payoff_months[name] = m["month"]
            if name not in payoff_months and name not in m["debts"]:
                payoff_months[name] = m["month"]

    names = []
    months_vals = []
    for name in debt_names:
        names.append(name)
        months_vals.append(payoff_months.get(name, result.months_to_payoff))

    fig.add_trace(go.Bar(
        y=names, x=months_vals, orientation="h",
        marker_color=[PALETTE[i % len(PALETTE)] for i in range(len(names))],
        text=[f"Month {m}" for m in months_vals], textposition="auto",
        hovertemplate="Debt: %{y} | Paid off: Month %{x}<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Month Paid Off", yaxis_title="")
    return fig


def sensitivity_chart(scenarios: list[dict]) -> go.Figure:
    """Line chart of total interest vs extra payment amount."""
    fig = _base_fig("🔍 Interest vs Extra Payment")
    # Filter out scenarios where debt is growing (can't pay off)
    viable = [s for s in scenarios if not s["avalanche"].get("debt_growing") or not s["snowball"].get("debt_growing")]
    if not viable:
        viable = scenarios  # show all if none are viable
    extras = [s["extra"] for s in viable]
    for method, color in [("avalanche", COLORS["green"]), ("snowball", COLORS["blue"])]:
        interest = []
        months = []
        x_vals = []
        for s in viable:
            if not s[method].get("debt_growing"):
                x_vals.append(s["extra"])
                interest.append(s[method]["total_interest"])
                months.append(s[method]["months"])
        if x_vals:
            fig.add_trace(go.Scatter(
                x=x_vals, y=interest, mode="lines+markers", name=method.title(),
                line=dict(color=color, width=2),
                customdata=months,
                hovertemplate="Extra $%{x:,.0f}/mo | Interest: $%{y:,.2f} | Months: %{customdata}<extra>" + method.title() + "</extra>",
            ))
    fig.update_layout(xaxis_title="Extra Monthly Payment ($)", yaxis_title="Total Interest ($)",
                      xaxis_tickprefix="$", yaxis_tickprefix="$", yaxis_tickformat=",")
    return fig


def strategy_comparison_chart(avalanche: SimulationResult, snowball: SimulationResult) -> go.Figure:
    """Grouped bar chart comparing key metrics."""
    fig = _base_fig("📊 Strategy Comparison")
    metrics = ["Total Interest", "Total Paid", "Months"]
    aval_vals = [avalanche.total_interest, avalanche.total_paid, avalanche.months_to_payoff]
    snow_vals = [snowball.total_interest, snowball.total_paid, snowball.months_to_payoff]

    fig.add_trace(go.Bar(name="Avalanche", x=metrics, y=aval_vals, marker_color=COLORS["green"]))
    fig.add_trace(go.Bar(name="Snowball", x=metrics, y=snow_vals, marker_color=COLORS["blue"]))
    fig.update_layout(barmode="group")
    return fig


def balance_transfer_comparison_chart(
    original: SimulationResult, transferred: SimulationResult
) -> go.Figure:
    """Compare total debt over time: original plan vs balance transfer."""
    fig = _base_fig("🔄 Balance Transfer Comparison")
    for res, name, color in [
        (original, "Current Plan", COLORS["red"]),
        (transferred, "With Transfer", COLORS["green"]),
    ]:
        months = [m["month"] for m in res.monthly_payments]
        remaining = [m["total_remaining"] for m in res.monthly_payments]
        fig.add_trace(go.Scatter(
            x=months, y=remaining, mode="lines", name=name,
            line=dict(color=color, width=2),
            hovertemplate="Month: %{x} | Remaining: $%{y:,.2f}<extra>" + name + "</extra>",
        ))
    fig.update_layout(xaxis_title="Month", yaxis_title="Remaining Debt ($)",
                      yaxis_tickprefix="$", yaxis_tickformat=",")
    return fig
