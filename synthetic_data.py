import pandas as pd
import random
from datetime import datetime, timedelta
import hashlib

# ── Deterministic seed per company name ───────────────────────────────────────
def seed_from_name(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest(), 16) % (2**32)

# ── Fake company names pool ───────────────────────────────────────────────────
COMPANY_NAMES = [
    "Veridian Corp", "Nexlar Industries", "Calibrant Group", "Stormgate Holdings",
    "Arclume Partners", "Duskfield Enterprises", "Halcyon Systems", "Meridex Global",
    "Troven Capital", "Solentris Ltd", "Brackford & Associates", "Onyxwell Corporation",
]

FIRST_NAMES = [
    "James","Sarah","Michael","Linda","Robert","Patricia","David","Barbara",
    "Richard","Susan","Thomas","Jessica","Charles","Karen","Daniel","Nancy",
    "Matthew","Lisa","Anthony","Betty","Mark","Dorothy","Paul","Sandra",
    "Andrew","Ashley","Joshua","Kimberly","Kenneth","Emily","Kevin","Donna",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
    "Taylor","Thomas","Moore","Jackson","Martin","Lee","Thompson","White","Harris",
]
VENDORS = [
    "Apex Supply Co","BlueStar Solutions","Cardinal Tech","Delta Logistics",
    "Echo Materials","Frontier Services","Global Parts Inc","Harbor Consulting",
    "Inland Resources","Jetstream Corp","Keystone Vendors","Luminary Supplies",
    "Meridian Goods","Nordic Contractors","Orbit Systems","Pinnacle Traders",
    "Quantum Supplies","Redstone Partners","Summit Providers","Titan Services",
    "Unified Materials","Vector Consulting","Westgate Supplies","Xenon Corp",
]
DEPARTMENTS = [
    "Finance","Procurement","HR","IT","Operations","Sales","Legal","Marketing"
]
GL_ACCOUNTS = [
    "6001 - Travel & Entertainment","6002 - Office Supplies","6003 - Consulting Fees",
    "6004 - Equipment Rental","6005 - Software Licenses","6006 - Marketing Expenses",
    "6007 - Training & Development","6008 - Maintenance & Repairs","6009 - Utilities",
    "6010 - Miscellaneous",
]
EXPENSE_CATEGORIES = [
    "Meals & Entertainment","Travel","Office Supplies","Client Gifts",
    "Conference Registration","Transportation","Accommodation","Equipment",
]
JOB_TITLES = [
    "Analyst","Senior Analyst","Manager","Senior Manager","Director",
    "VP","Associate","Coordinator","Specialist","Consultant",
]
BANKS = ["Chase","Wells Fargo","Bank of America","Citibank","TD Bank","PNC","US Bank"]
IT_ASSETS = [
    "Dell Laptop","MacBook Pro","HP Workstation","Cisco Switch","Juniper Router",
    "VMware License","Salesforce CRM","Microsoft 365","Adobe Creative Suite",
    "Oracle DB License","AWS Reserved Instance","Fortinet Firewall",
]
LEAVE_TYPES = ["Annual","Sick","Personal","Unpaid","Maternity","Paternity","Bereavement"]

def rnd_date(start_days_ago=365, end_days_ago=0, rng=None):
    rng = rng or random
    delta = rng.randint(end_days_ago, start_days_ago)
    return (datetime.today() - timedelta(days=delta)).strftime("%Y-%m-%d")

def rnd_name(rng):
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"

def rnd_vendor(rng):
    return rng.choice(VENDORS)

# ── Department generators ─────────────────────────────────────────────────────

def gen_finance(rng, n=120):
    rows = []
    for i in range(n):
        amount = round(rng.uniform(500, 95000), 2)
        # inject anomalies
        anomaly = rng.random() < 0.08
        if anomaly:
            amount = round(rng.uniform(95000, 199999), 2)  # just under approval threshold
        rows.append({
            "Transaction_ID": f"TXN-{10000+i}",
            "Date": rnd_date(rng=rng),
            "GL_Account": rng.choice(GL_ACCOUNTS),
            "Vendor": rnd_vendor(rng),
            "Amount_USD": amount,
            "Approved_By": rnd_name(rng),
            "Department": rng.choice(DEPARTMENTS),
            "Payment_Method": rng.choice(["ACH","Wire","Check","Credit Card"]),
            "Invoice_Number": f"INV-{rng.randint(1000,9999)}",
            "Flagged": "Yes" if anomaly else "No",
            "Notes": "Duplicate vendor" if (anomaly and rng.random()<0.4) else "",
        })
    return pd.DataFrame(rows)

def gen_procurement(rng, n=100):
    rows = []
    for i in range(n):
        unit_price = round(rng.uniform(10, 5000), 2)
        qty = rng.randint(1, 200)
        total = round(unit_price * qty, 2)
        split_order = rng.random() < 0.07
        rows.append({
            "PO_Number": f"PO-{5000+i}",
            "Date": rnd_date(rng=rng),
            "Vendor": rnd_vendor(rng),
            "Item_Description": rng.choice(["Office Chairs","Laptop Batteries","Safety Equipment",
                                             "Cleaning Supplies","Server Hardware","Cables & Connectors",
                                             "Stationery","Printer Toner","HVAC Parts","Furniture"]),
            "Quantity": qty,
            "Unit_Price_USD": unit_price,
            "Total_Amount_USD": total,
            "Requisitioned_By": rnd_name(rng),
            "Approved_By": rnd_name(rng) if total > 10000 else "Auto-approved",
            "Vendor_Registered_Days_Ago": rng.randint(1, 2000),
            "Competing_Bids": rng.randint(0, 4),
            "Split_Order_Flag": "Yes" if split_order else "No",
        })
    return pd.DataFrame(rows)

def gen_hr(rng, n=80):
    rows = []
    for i in range(n):
        salary = round(rng.choice([45000,55000,65000,75000,85000,95000,110000,130000]) * rng.uniform(0.9,1.1), 2)
        ghost = rng.random() < 0.05
        rows.append({
            "Employee_ID": f"EMP-{1000+i}",
            "Name": rnd_name(rng),
            "Department": rng.choice(DEPARTMENTS),
            "Job_Title": rng.choice(JOB_TITLES),
            "Annual_Salary_USD": salary,
            "Bank": rng.choice(BANKS),
            "Bank_Account_Changes_Last_90d": rng.choice([0,0,0,0,1,2]),
            "Leave_Days_Taken": rng.randint(0, 30),
            "Leave_Type": rng.choice(LEAVE_TYPES),
            "Hire_Date": rnd_date(start_days_ago=3650, end_days_ago=30, rng=rng),
            "Termination_Date": rnd_date(rng=rng) if ghost else "",
            "Active": "No" if ghost else "Yes",
            "Last_Payroll_Date": rnd_date(start_days_ago=30, rng=rng),
            "Ghost_Employee_Flag": "Yes" if ghost else "No",
        })
    return pd.DataFrame(rows)

def gen_vendor(rng, n=90):
    rows = []
    for i in range(n):
        amount = round(rng.uniform(2000, 150000), 2)
        shell = rng.random() < 0.06
        rows.append({
            "Vendor_ID": f"VND-{2000+i}",
            "Vendor_Name": rnd_vendor(rng),
            "Registration_Date": rnd_date(start_days_ago=1800, rng=rng),
            "Country": rng.choice(["USA","UK","Germany","Singapore","Cayman Islands","BVI","UAE","Canada"]),
            "Annual_Spend_USD": amount,
            "Contracts_On_File": rng.randint(0, 5),
            "PO_Box_Only": "Yes" if shell else "No",
            "Shared_Address_With_Employee": "Yes" if (shell and rng.random()<0.5) else "No",
            "Sole_Source_Justification": rng.choice(["Yes","No","Partial"]),
            "Invoices_Without_PO": rng.randint(0, 12),
            "Payment_Terms_Days": rng.choice([15, 30, 45, 60, 90]),
            "Shell_Company_Flag": "Yes" if shell else "No",
        })
    return pd.DataFrame(rows)

def gen_it(rng, n=100):
    rows = []
    for i in range(n):
        cost = round(rng.uniform(200, 80000), 2)
        phantom = rng.random() < 0.07
        rows.append({
            "Asset_ID": f"IT-{3000+i}",
            "Asset_Name": rng.choice(IT_ASSETS),
            "Assigned_To": rnd_name(rng) if not phantom else "Unassigned",
            "Department": rng.choice(DEPARTMENTS),
            "Purchase_Date": rnd_date(rng=rng),
            "Cost_USD": cost,
            "Vendor": rnd_vendor(rng),
            "License_Count_Purchased": rng.randint(1, 500),
            "License_Count_Used": rng.randint(1, 500),
            "Last_Audit_Date": rnd_date(start_days_ago=730, rng=rng),
            "Physical_Verified": rng.choice(["Yes","Yes","Yes","No"]),
            "Admin_Access_Users": rng.randint(1, 20),
            "Phantom_Asset_Flag": "Yes" if phantom else "No",
        })
    return pd.DataFrame(rows)

def gen_expenses(rng, n=150):
    rows = []
    for i in range(n):
        amount = round(rng.uniform(20, 4500), 2)
        personal = rng.random() < 0.09
        if personal:
            amount = round(rng.uniform(200, 4500), 2)
        rows.append({
            "Claim_ID": f"EXP-{7000+i}",
            "Submitted_By": rnd_name(rng),
            "Department": rng.choice(DEPARTMENTS),
            "Date_Incurred": rnd_date(rng=rng),
            "Date_Submitted": rnd_date(start_days_ago=30, rng=rng),
            "Category": rng.choice(EXPENSE_CATEGORIES),
            "Amount_USD": amount,
            "Receipt_Attached": rng.choice(["Yes","Yes","Yes","No"]),
            "Approved_By": rnd_name(rng),
            "Business_Purpose": rng.choice(["Client meeting","Team offsite","Training",
                                             "Conference","Vendor visit","Internal meeting",""]),
            "Weekend_Submission": "Yes" if rng.random()<0.15 else "No",
            "Duplicate_Claim_Flag": "Yes" if (personal and rng.random()<0.3) else "No",
            "Personal_Expense_Flag": "Yes" if personal else "No",
        })
    return pd.DataFrame(rows)

def gen_sales(rng, n=110):
    rows = []
    for i in range(n):
        deal_value = round(rng.uniform(5000, 500000), 2)
        commission = round(deal_value * rng.uniform(0.04, 0.12), 2)
        inflated = rng.random() < 0.06
        if inflated:
            deal_value = round(deal_value * rng.uniform(1.3, 2.0), 2)
        rows.append({
            "Deal_ID": f"DL-{4000+i}",
            "Sales_Rep": rnd_name(rng),
            "Client": f"Client_{rng.randint(100,999)}",
            "Close_Date": rnd_date(rng=rng),
            "Deal_Value_USD": deal_value,
            "Commission_USD": commission,
            "Discount_Pct": round(rng.uniform(0, 40), 1),
            "Contract_Signed": rng.choice(["Yes","Yes","Yes","No"]),
            "Revenue_Recognized": rng.choice(["Yes","No"]),
            "Quarter": rng.choice(["Q1","Q2","Q3","Q4"]),
            "Channel_Partner": rng.choice(["Direct","Partner A","Partner B","Online",""]),
            "Revenue_Inflation_Flag": "Yes" if inflated else "No",
        })
    return pd.DataFrame(rows)

def gen_legal(rng, n=60):
    rows = []
    for i in range(n):
        amount = round(rng.uniform(1000, 200000), 2)
        unauthorized = rng.random() < 0.07
        rows.append({
            "Contract_ID": f"LGL-{6000+i}",
            "Counterparty": rnd_vendor(rng),
            "Contract_Type": rng.choice(["NDA","Service Agreement","Licensing","Settlement","Consulting","Lease"]),
            "Signed_Date": rnd_date(rng=rng),
            "Expiry_Date": (datetime.today() + timedelta(days=rng.randint(30, 365))).strftime("%Y-%m-%d"),
            "Value_USD": amount,
            "Signed_By": rnd_name(rng),
            "Authority_Level": rng.choice(["Manager","Director","VP","C-Suite"]),
            "Legal_Review": rng.choice(["Yes","Yes","No"]),
            "Board_Approval_Required": "Yes" if amount > 100000 else "No",
            "Board_Approval_Obtained": rng.choice(["Yes","No"]) if amount > 100000 else "N/A",
            "Unauthorized_Commitment_Flag": "Yes" if unauthorized else "No",
        })
    return pd.DataFrame(rows)

def gen_marketing(rng, n=80):
    rows = []
    for i in range(n):
        budget = round(rng.uniform(1000, 80000), 2)
        spent = round(budget * rng.uniform(0.5, 1.4), 2)
        kickback = rng.random() < 0.06
        rows.append({
            "Campaign_ID": f"MKT-{8000+i}",
            "Campaign_Name": rng.choice(["Q4 Brand Push","Digital Awareness","Trade Show",
                                          "Influencer Collab","Email Nurture","PPC Retargeting",
                                          "Print Campaign","Webinar Series"]),
            "Agency": rnd_vendor(rng),
            "Start_Date": rnd_date(rng=rng),
            "Budget_USD": budget,
            "Actual_Spend_USD": spent,
            "Variance_USD": round(spent - budget, 2),
            "ROI_Pct": round(rng.uniform(-20, 300), 1),
            "Competitive_Bids": rng.randint(0, 4),
            "Contract_On_File": rng.choice(["Yes","Yes","No"]),
            "Deliverables_Verified": rng.choice(["Yes","Yes","No"]),
            "Agency_Employee_Relation_Flag": "Yes" if kickback else "No",
        })
    return pd.DataFrame(rows)


# ── Master generator ──────────────────────────────────────────────────────────
DEPT_GENERATORS = {
    "Finance & Accounting":     gen_finance,
    "Procurement & Purchasing": gen_procurement,
    "HR & Payroll":             gen_hr,
    "Vendor & Supply Chain":    gen_vendor,
    "IT & Cybersecurity":       gen_it,
    "Expenses & Reimbursement": gen_expenses,
    "Sales & Revenue":          gen_sales,
    "Legal & Contracts":        gen_legal,
    "Marketing & Agencies":     gen_marketing,
}

def generate_company_data(company_name: str) -> dict[str, pd.DataFrame]:
    rng = random.Random(seed_from_name(company_name))
    return {dept: gen_fn(rng) for dept, gen_fn in DEPT_GENERATORS.items()}

def pick_company_name(seed_extra: int = 0) -> str:
    idx = (seed_extra) % len(COMPANY_NAMES)
    return COMPANY_NAMES[idx]
