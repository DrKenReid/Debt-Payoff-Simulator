# 💳 Debt Payoff Simulator

**[Launch the App →](https://debt-payoff-simulator.streamlit.app)**

Compare **Avalanche** vs **Snowball** debt repayment strategies. No signup, no data stored.

> *"You could be debt-free 14 months sooner and save $2,847 in interest. But that requires discipline, which is how you got here."*

[![CI](https://github.com/DrKenReid/Debt-Payoff-Simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/DrKenReid/Debt-Payoff-Simulator/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📊 **Strategy Comparison** | Side-by-side Avalanche vs Snowball with interactive charts |
| 🔄 **Balance Transfer Analysis** | Model multiple transfers to low-APR cards |
| 📈 **Sensitivity Analysis** | Impact of paying $50–$500 more per month |
| 📅 **Bi-Weekly Payments** | Toggle to see how 13 annual payments saves interest |
| 🏷️ **Promo APR Support** | Model 0% intro rates with expiry dates |
| ⚠️ **Insufficient Payment Detection** | Warns when payments can't keep up with interest |
| 💬 **Plain English Summary** | What each strategy actually means for you |
| 🎴 **Customizable Summary Card** | Themed, with toggleable content and payment plan breakdown |
| 📋 **CSV Export** | Download your month-by-month payment plan |

## 🚀 Try It

**[Use it live →](https://debt-payoff-simulator.streamlit.app)**

Or run locally:

```bash
git clone https://github.com/DrKenReid/Debt-Payoff-Simulator.git
cd Debt-Payoff-Simulator
pip install -r requirements.txt
streamlit run app.py
```

## 🧮 How the Math Works

The engine is deliberately simple and its assumptions are explicit:

- Interest compounds monthly at APR ÷ 12, applied before each payment.
- The simulator assumes **everything left after expenses goes toward debt** each month — minimum payments first, the remainder to the strategy's priority debt. "Extra Monthly Payment" adds on top of that budget.
- **Bi-weekly mode** models the classic trick: 26 half-payments = 13 full payments per year, i.e. your monthly debt budget × 13/12.
- **Promo APRs** apply until their end date, then revert to the standard APR. Balance transfers add the fee to the transferred balance and start a 0% promo window.
- Simulations cap at 600 months; if total debt grows three months in a row, the plan is flagged as never paying off.

> ⚠️ For educational purposes only — this is a simplified model, not financial advice.

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest
```

## 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

[MIT](LICENSE)

## Related

- [Steam Stats Visualized](https://github.com/DrKenReid/steam-stats-visualized) — Spotify Wrapped for your Steam library
- [Letterboxd Roasted](https://github.com/DrKenReid/Letterboxd-Roasted) — Spotify Wrapped for your Letterboxd

## Author

**Ken Reid** — Data Scientist, photographer, and avid reader.

- [kenreid.co.uk](https://www.kenreid.co.uk) — Portfolio & blog
- [@kenreid.co.uk](https://bsky.app/profile/kenreid.co.uk) — Bluesky
- [@DrKenReid](https://github.com/DrKenReid) — GitHub
