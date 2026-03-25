# Debt Payoff Simulator

A simulator that compares the **Avalanche** and **Snowball** debt repayment strategies using your own financial data stored in Google Sheets. Calculates optimal payment distribution, tracks cumulative interest, and visualises payoff timelines.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DrKenReid/Debt-Payoff-Simulator/blob/main/Debt_Payoff_Simulator.ipynb)

## Techniques Demonstrated

| Category | Details |
|---|---|
| **Financial Modelling** | Monthly interest accrual, APR expiry handling, minimum payment logic |
| **Strategy Comparison** | Avalanche (highest APR first) vs. Snowball (lowest balance first) |
| **Google Sheets Integration** | Automated folder/spreadsheet creation, data read/write via Sheets API |
| **Visualisation** | Line plots, stacked area charts, cumulative interest comparison (Matplotlib/Seaborn) |
| **OOP Design** | Single `DebtSimulator` class encapsulating setup, simulation, plotting, and export |

## How to Use

1. Open the notebook in Google Colab using the badge above.
2. Authenticate with your Google account when prompted.
3. The notebook automatically creates a **Debt Repayment Simulator** folder in your Google Drive with a sample spreadsheet.
4. Edit the spreadsheet with your own debts, income, and expenses — or run with the provided example data.
5. Run the second cell to simulate both repayment methods and view the comparison.

The simulator outputs detailed month-by-month payment plans back to Google Sheets for reference.

## Example Outputs

| | |
|---|---|
| ![Total Debt Over Time](img/plot_1.png) | ![Cumulative Interest](img/plot_3.png) |
| ![Debt Per Card — Avalanche vs. Snowball](img/plot_2.png) | |

## A Note on Strategy Choice

In the example data, the Avalanche method saves roughly $795 in interest (28%) compared to Snowball, while both pay off debt in the same number of months. This is typical: Avalanche almost always wins on total cost. However, the Snowball method's psychological advantage — eliminating smaller debts quickly for motivation — is real and well-documented. The best strategy is the one you'll actually stick with.

## License

This project is licensed under [CC BY 4.0](LICENSE).
