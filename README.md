# FraudLens v2 — AI Fraud Risk Intelligence

Proactive fraud scenario generation, deep analysis, and board-ready reporting — powered by Claude AI.

## Features

- **Synthetic Data Mode** — 12 pre-built fictional companies with realistic data across 9 departments, embedded anomalies included
- **Real Data Upload Mode** — Upload your own CSV or Excel files per department; AI analyses actual patterns
- **9 Departments** — Finance, Procurement, HR, Vendor, IT, Expenses, Sales, Legal, Marketing
- **AI Analysis** — Attack vectors, detection difficulty, controls assessment, recommendations, quick wins
- **Executive Report** — Board-ready summary + risk register, downloadable as TXT and CSV
- **Professional UI** — Clean, dark-sidebar design with Syne + DM Sans typography

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

You need an Anthropic API key from https://console.anthropic.com

## Deploy to Streamlit Cloud (Free)

1. Create a new GitHub repository
2. Push these files:
   - `app.py`
   - `synthetic_data.py`
   - `requirements.txt`
   - `README.md`
3. Go to https://share.streamlit.io
4. Click "New app" → connect your GitHub repo
5. Set main file path to `app.py`
6. Click Deploy

Deployment takes ~2 minutes. You get a public URL to share.

## File Structure

```
fraudlens_v2/
├── app.py              # Main Streamlit application
├── synthetic_data.py   # Fake company + department data generators
├── requirements.txt    # Python dependencies
└── README.md
```

## Departments & Upload Format

| Department              | Key Columns Expected                                      |
|-------------------------|-----------------------------------------------------------|
| Finance & Accounting    | Date, Vendor, Amount_USD, GL_Account, Approved_By        |
| Procurement & Purchasing| Vendor, Item_Description, Total_Amount_USD, Approved_By  |
| HR & Payroll            | Employee_ID, Name, Annual_Salary_USD, Bank, Active       |
| Vendor & Supply Chain   | Vendor_Name, Country, Annual_Spend_USD, Contracts_On_File|
| IT & Cybersecurity      | Asset_Name, Cost_USD, License_Count_Purchased/Used       |
| Expenses & Reimbursement| Submitted_By, Category, Amount_USD, Receipt_Attached     |
| Sales & Revenue         | Sales_Rep, Deal_Value_USD, Commission_USD, Discount_Pct  |
| Legal & Contracts       | Counterparty, Contract_Type, Value_USD, Signed_By        |
| Marketing & Agencies    | Agency, Budget_USD, Actual_Spend_USD, Competitive_Bids   |

Columns are flexible — the AI adapts to whatever columns you provide.
