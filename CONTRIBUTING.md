# Contributing to Debt Payoff Simulator

Thanks for your interest! Here's how to help.

## Ways to Contribute

- **Report bugs**: Something broken in the app? Open an issue.
- **Suggest improvements**: Better models, visualizations, or UX.
- **Fix issues**: Check the [Issues](https://github.com/DrKenReid/Debt-Payoff-Simulator/issues) tab.
- **Improve docs**: Clarify explanations, fix typos, add examples.

## Setup

```bash
git clone https://github.com/DrKenReid/Debt-Payoff-Simulator.git
cd Debt-Payoff-Simulator
pip install -r requirements.txt -r requirements-dev.txt
streamlit run app.py
```

## Project Layout

- `app.py` — Streamlit UI
- `src/simulator.py` — payoff engine (no Streamlit imports; keep it that way)
- `src/analytics.py` — summaries and sensitivity analysis
- `src/charts.py` — Plotly chart builders
- `tests/` — pytest suite

## Before Opening a PR

- Run the tests: `pytest`
- Run the linter: `ruff check .`
- Add tests for any change to the simulation logic — it's a financial calculator, so numbers matter.
- Don't commit API keys or credentials.
