import streamlit as st
import anthropic
import httpx
import pandas as pd
import json
import re
import time
import io
from datetime import datetime
from synthetic_data import generate_company_data, pick_company_name, DEPT_GENERATORS, COMPANY_NAMES

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FraudSense — AI Risk Intelligence",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {
    --bg:        #f4f3ef;
    --surface:   #ffffff;
    --surface2:  #f9f8f5;
    --border:    #e2e0da;
    --border2:   #ccc9c0;
    --ink:       #1a1916;
    --ink2:      #4a4840;
    --ink3:      #7a7870;
    --accent:    #c8390a;
    --accent2:   #e84b18;
    --gold:      #b8860b;
    --green:     #1a6b3c;
    --orange:    #c05c00;
    --mono:      'DM Mono', monospace;
    --sans:      'DM Sans', sans-serif;
    --display:   'Syne', sans-serif;
}

html, body, [class*="css"] {
    font-family: var(--sans);
    background-color: var(--bg);
    color: var(--ink);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #1a1916;
    border-right: 1px solid #2e2c28;
}
section[data-testid="stSidebar"] * { color: #d4d0c8 !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stTextInput label,
section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] .stRadio label { color: #9a9890 !important; font-size:0.75rem !important; letter-spacing:0.8px; text-transform:uppercase; font-family:var(--mono) !important; }
section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > div > div,
section[data-testid="stSidebar"] div[data-testid="stTextInput"] > div > div > input {
    background:#252320 !important; border-color:#3a3830 !important; color:#d4d0c8 !important; border-radius:4px !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label { color:#d4d0c8 !important; font-size:0.85rem !important; text-transform:none !important; letter-spacing:0 !important; font-family:var(--sans) !important; }

/* Main */
.main .block-container { background: var(--bg); padding-top: 0; max-width: 1400px; }

/* Top bar */
.topbar {
    background: var(--ink);
    padding: 0 2.5rem;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: -1rem -1rem 2.5rem -1rem;
    border-bottom: 1px solid #2e2c28;
}
.topbar-logo {
    font-family: var(--display);
    font-size: 1.15rem;
    font-weight: 800;
    color: #f4f3ef;
    letter-spacing: -0.3px;
}
.topbar-logo span { color: var(--accent); }
.topbar-tag {
    font-family: var(--mono);
    font-size: 0.68rem;
    color: #5a5850;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

/* Section headings */
.section-label {
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--ink3);
    letter-spacing: 2px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
}

/* Stat cards */
.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 2rem; }
.stat-cell { background: var(--surface); padding: 1.4rem 1.6rem; }
.stat-cell-accent { background: var(--ink); }
.stat-num { font-family: var(--display); font-size: 2.2rem; font-weight: 800; color: var(--ink); line-height: 1; }
.stat-num-accent { color: var(--accent); }
.stat-lbl { font-family: var(--mono); font-size: 0.68rem; color: var(--ink3); letter-spacing: 1px; text-transform: uppercase; margin-top: 0.4rem; }
.stat-lbl-accent { color: #5a5850; }

/* Risk pills */
.pill { display: inline-block; font-family: var(--mono); font-size: 0.68rem; letter-spacing: 0.5px; padding: 3px 10px; border-radius: 2px; font-weight: 500; }
.pill-critical { background: #fde8e3; color: #8b1a08; border: 1px solid #f5c0b0; }
.pill-high     { background: #fef3e2; color: #854d00; border: 1px solid #f5d898; }
.pill-medium   { background: #fefae0; color: #7a6500; border: 1px solid #e8dc90; }
.pill-low      { background: #e6f4ee; color: #1a5c35; border: 1px solid #a8d8bc; }

/* Scenario card */
.sc-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 0.8rem;
    border-left: 3px solid transparent;
    transition: border-left-color 0.15s;
}
.sc-card:hover { border-left-color: var(--accent); }
.sc-title { font-family: var(--display); font-size: 0.95rem; font-weight: 700; color: var(--ink); margin-bottom: 0.4rem; }
.sc-desc { font-size: 0.85rem; color: var(--ink2); line-height: 1.65; margin-bottom: 0.9rem; }
.sc-meta { font-family: var(--mono); font-size: 0.72rem; color: var(--ink3); }
.sc-meta span { margin-right: 1.4rem; }
.sc-flags { margin-top: 0.8rem; }
.sc-flag { font-size: 0.78rem; color: var(--ink2); padding: 2px 0; }
.sc-flag::before { content: "— "; color: var(--accent); }

/* Analysis block */
.an-block {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.8rem;
}
.an-label { font-family: var(--mono); font-size: 0.65rem; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; }
.an-content { font-size: 0.86rem; color: var(--ink2); line-height: 1.7; }
.an-quickwin { background: #e6f4ee; border-color: #a8d8bc; }
.an-quickwin .an-label { color: var(--green); }

/* Table */
.risk-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.risk-table th { font-family: var(--mono); font-size: 0.65rem; letter-spacing: 1.5px; text-transform: uppercase; color: var(--ink3); border-bottom: 2px solid var(--ink); padding: 0.5rem 0.8rem 0.7rem; text-align: left; }
.risk-table td { padding: 0.7rem 0.8rem; border-bottom: 1px solid var(--border); color: var(--ink2); vertical-align: top; }
.risk-table tr:last-child td { border-bottom: none; }
.risk-table tr:hover td { background: var(--surface2); }
.risk-table .mono { font-family: var(--mono); font-size: 0.75rem; }

/* Data preview */
.data-info { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 1rem 1.2rem; margin-bottom: 1.2rem; font-family: var(--mono); font-size: 0.78rem; color: var(--ink2); }
.data-info strong { color: var(--ink); }

/* Exec summary */
.exec-block { background: var(--ink); border-radius: 8px; padding: 2rem 2.4rem; margin-bottom: 1.5rem; }
.exec-heading { font-family: var(--display); font-size: 0.72rem; font-weight: 700; color: var(--accent); letter-spacing: 3px; text-transform: uppercase; margin-bottom: 1.2rem; border-bottom: 1px solid #2e2c28; padding-bottom: 0.6rem; }
.exec-text { font-size: 0.9rem; color: #c8c4bc; line-height: 1.8; }

/* Upload area */
.upload-info { background: var(--surface); border: 1px dashed var(--border2); border-radius: 6px; padding: 1.2rem 1.4rem; margin-bottom: 1rem; }
.upload-title { font-family: var(--display); font-weight: 700; font-size: 0.88rem; color: var(--ink); margin-bottom: 0.3rem; }
.upload-sub { font-size: 0.78rem; color: var(--ink3); }

/* Sidebar logo block */
.sb-logo { padding: 1.4rem 1rem 1rem; border-bottom: 1px solid #2e2c28; margin-bottom: 1rem; }
.sb-logo-text { font-family: var(--display); font-size: 1.3rem; font-weight: 800; color: #f4f3ef; }
.sb-logo-text span { color: var(--accent); }
.sb-logo-sub { font-family: var(--mono); font-size: 0.62rem; color: #4a4840; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 0.2rem; }
.sb-section { font-family: var(--mono); font-size: 0.62rem; color: #4a4840; letter-spacing: 1.5px; text-transform: uppercase; padding: 1rem 0 0.4rem; }

/* Mode toggle */
.mode-active { background: var(--accent) !important; color: #fff !important; border-color: var(--accent) !important; }

/* Streamlit overrides */
.stButton > button {
    background: var(--ink); color: #f4f3ef; border: none; border-radius: 4px;
    font-family: var(--mono); font-size: 0.78rem; font-weight: 500;
    padding: 0.6rem 1.4rem; letter-spacing: 0.5px; width: 100%;
    transition: background 0.15s;
}
.stButton > button:hover { background: var(--accent) !important; border: none !important; }
.stProgress > div > div > div { background: var(--accent) !important; }
div[data-testid="stTab"] button { font-family: var(--mono) !important; font-size: 0.75rem !important; letter-spacing: 0.5px !important; text-transform: uppercase !important; }
div[data-testid="stTab"] button[aria-selected="true"] { border-bottom-color: var(--accent) !important; color: var(--accent) !important; }
.stDataFrame { border: 1px solid var(--border) !important; border-radius: 6px !important; }
.stDownloadButton > button { background: var(--surface) !important; color: var(--ink) !important; border: 1px solid var(--border2) !important; font-family: var(--mono) !important; font-size: 0.75rem !important; }
.stDownloadButton > button:hover { background: var(--ink) !important; color: #f4f3ef !important; border-color: var(--ink) !important; }
h1,h2,h3 { font-family: var(--display) !important; color: var(--ink) !important; }
.stAlert { border-radius: 4px !important; }
div[data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: 6px !important; background: var(--surface) !important; }
div[data-testid="stExpander"] summary { font-family: var(--display) !important; font-weight: 700 !important; font-size: 0.9rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DEPT_LIST = list(DEPT_GENERATORS.keys())

DEPT_UPLOAD_COLS = {
    "Finance & Accounting":     ["Date","Vendor","Amount_USD","GL_Account","Approved_By","Payment_Method","Invoice_Number"],
    "Procurement & Purchasing": ["Date","Vendor","Item_Description","Quantity","Unit_Price_USD","Total_Amount_USD","Approved_By","Competing_Bids"],
    "HR & Payroll":             ["Employee_ID","Name","Department","Annual_Salary_USD","Bank","Last_Payroll_Date","Active"],
    "Vendor & Supply Chain":    ["Vendor_Name","Country","Annual_Spend_USD","Contracts_On_File","PO_Box_Only","Invoices_Without_PO"],
    "IT & Cybersecurity":       ["Asset_Name","Assigned_To","Cost_USD","License_Count_Purchased","License_Count_Used","Physical_Verified"],
    "Expenses & Reimbursement": ["Submitted_By","Category","Amount_USD","Date_Incurred","Receipt_Attached","Business_Purpose"],
    "Sales & Revenue":          ["Sales_Rep","Deal_Value_USD","Commission_USD","Discount_Pct","Contract_Signed","Revenue_Recognized","Quarter"],
    "Legal & Contracts":        ["Counterparty","Contract_Type","Value_USD","Signed_By","Legal_Review","Board_Approval_Required"],
    "Marketing & Agencies":     ["Agency","Campaign_Name","Budget_USD","Actual_Spend_USD","Competitive_Bids","Deliverables_Verified"],
}

INDUSTRIES = ["Financial Services","Healthcare","Retail & E-commerce","Manufacturing","Technology","Government & Public Sector","Insurance","Real Estate","Professional Services"]
COMPANY_SIZES = ["Startup  (<50 employees)","SME  (50–500)","Mid-market  (500–5,000)","Enterprise  (5,000+)"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_client():
    key = st.session_state.get("api_key", "") or st.secrets.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    transport = httpx.HTTPTransport(retries=3)
    http_client = httpx.Client(
        transport=transport,
        timeout=httpx.Timeout(120.0, connect=15.0, read=90.0, write=15.0),
    )
    return anthropic.Anthropic(
        api_key=key,
        http_client=http_client,
        max_retries=3,
    )

def pill(level):
    cls = {"Critical":"pill-critical","High":"pill-high","Medium":"pill-medium","Low":"pill-low"}.get(level,"pill-low")
    return f'<span class="pill {cls}">{level}</span>'

def df_summary(df: pd.DataFrame, dept: str) -> str:
    lines = [f"Department dataset: {dept}",
             f"Records: {len(df)} rows x {len(df.columns)} columns",
             f"Columns: {', '.join(df.columns.tolist())}"]
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            lines.append(f"  {col}: min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f}")
        else:
            top = df[col].value_counts().head(3).to_dict()
            lines.append(f"  {col} (top values): {top}")
    # flag columns
    flag_cols = [c for c in df.columns if "Flag" in c or "flag" in c]
    for fc in flag_cols:
        flagged = (df[fc] == "Yes").sum()
        lines.append(f"  FLAGGED — {fc}: {flagged} of {len(df)} records")
    return "\n".join(lines)

def generate_scenarios(client, dept, company_name, company_size, industry, df_summary_text, n):
    prompt = f"""You are a senior fraud risk consultant at a Big-4 firm.

Company: {company_name}
Size: {company_size}
Industry: {industry}
Department under review: {dept}

Dataset summary (for context):
{df_summary_text[:1500]}

Generate {n} realistic, specific fraud scenarios for this department. Reference actual patterns visible in the data summary where relevant.

Return a JSON array of exactly {n} objects, each with:
- "id": integer
- "title": concise scenario name (max 8 words, no emojis)
- "description": 2-sentence explanation of how the fraud operates
- "risk_level": one of Critical / High / Medium / Low
- "red_flags": array of exactly 3 specific warning signs
- "estimated_loss": realistic dollar range (e.g. "$25K–$80K annually")
- "likelihood": percentage string (e.g. "72%")
- "fraud_type": one of Asset Misappropriation / Financial Statement Fraud / Corruption & Bribery / Cyber Fraud / Payroll Fraud / Procurement Fraud / Expense Fraud / Revenue Fraud

Return ONLY valid JSON. No markdown, no preamble."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role":"user","content":prompt}]
    )
    raw = resp.content[0].text.strip()
    # Strip markdown fences if model wraps JSON in ```json ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    return json.loads(raw)

def analyze_scenario(client, scenario, dept, company_name, company_size, industry, df_summary_text):
    prompt = f"""You are a senior fraud risk consultant preparing a client-facing analysis.

Company: {company_name} | {company_size} | {industry}
Department: {dept}
Scenario: {scenario['title']}
Description: {scenario['description']}
Risk Level: {scenario['risk_level']}

Dataset context:
{df_summary_text[:800]}

Write a structured analysis with these exact section headers (use the header names exactly as shown, followed by a colon and the content on the next line):

ATTACK_VECTOR:
How a fraudster would execute this step by step. Be specific. (3-4 sentences)

DETECTION_DIFFICULTY:
Why existing controls fail to catch this. Reference likely gaps. (2-3 sentences)

FINANCIAL_IMPACT:
Direct costs, indirect costs, and regulatory exposure. Include estimates. (2-3 sentences)

CONTROLS_ASSESSMENT:
Likely controls in place and their specific weaknesses. (3-4 sentences)

RECOMMENDATIONS:
1. [specific action]
2. [specific action]
3. [specific action]
4. [specific action]

QUICK_WIN:
One concrete action the company can take this week to reduce exposure. (1-2 sentences)

No markdown. No emojis. Professional tone throughout."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        messages=[{"role":"user","content":prompt}]
    )
    return resp.content[0].text.strip()

def generate_exec_summary(client, scenarios, dept, company_name, company_size, industry):
    scenario_list = "\n".join([f"- {s['title']} | {s['risk_level']} | {s['estimated_loss']}" for s in scenarios])
    prompt = f"""You are a partner-level fraud risk consultant writing an executive summary for a board-level report.

Client: {company_name}
Profile: {company_size} | {industry}
Department Assessed: {dept}

Scenarios Identified:
{scenario_list}

Write a 4-paragraph executive summary covering:
1. Overall fraud risk posture and key findings from this assessment
2. Most critical threats and their potential business impact
3. Systemic control weaknesses and root causes
4. Priority recommendations and proposed next steps

Tone: authoritative, precise, board-appropriate. No bullet points in the summary itself. No emojis. No markdown."""

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=900,
        messages=[{"role":"user","content":prompt}]
    )
    return resp.content[0].text.strip()

def parse_analysis(text):
    keys = ["ATTACK_VECTOR","DETECTION_DIFFICULTY","FINANCIAL_IMPACT","CONTROLS_ASSESSMENT","RECOMMENDATIONS","QUICK_WIN"]
    sections = {}
    for i, k in enumerate(keys):
        start = text.find(k + ":")
        if start == -1:
            sections[k] = ""
            continue
        content_start = start + len(k) + 1
        end = len(text)
        for nk in keys[i+1:]:
            p = text.find(nk + ":")
            if p != -1:
                end = p
                break
        sections[k] = text[content_start:end].strip()
    return sections

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sb-logo">
        <div class="sb-logo-text">Fraud<span>Sense</span></div>
        <div class="sb-logo-sub">AI Risk Intelligence Platform</div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="sb-section">API Access</div>', unsafe_allow_html=True)
    st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...", key="api_key",
                  help="Obtain from console.anthropic.com")

    st.markdown('<div class="sb-section">Data Mode</div>', unsafe_allow_html=True)
    data_mode = st.radio("Select Data Mode", ["Synthetic Company Data", "Upload Real Data"], label_visibility="collapsed")

    st.markdown('<div class="sb-section">Assessment Parameters</div>', unsafe_allow_html=True)

    if data_mode == "Synthetic Company Data":
        company_choice = st.selectbox("Company Profile", COMPANY_NAMES)
    else:
        company_choice = st.text_input("Company Name", placeholder="Your company name")

    selected_dept = st.selectbox("Department", DEPT_LIST)
    company_size  = st.selectbox("Company Size", COMPANY_SIZES, index=1)
    industry      = st.selectbox("Industry", INDUSTRIES)
    num_scenarios = st.slider("Scenarios to Generate", 3, 8, 5)

    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("Run Assessment", width="stretch")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div style="font-family:var(--mono);font-size:0.62rem;color:#3a3830;padding:0 0 1rem;">FraudSense v2.0 — Demo Build<br>Powered by Claude AI (Anthropic)</div>', unsafe_allow_html=True)

# ── Top bar ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
    <div class="topbar-logo">Fraud<span>Sense</span></div>
    <div class="topbar-tag">AI Fraud Risk Intelligence</div>
</div>
""", unsafe_allow_html=True)

# ── Data upload section (only in upload mode) ─────────────────────────────────
uploaded_df = None

if data_mode == "Upload Real Data":
    st.markdown('<div class="section-label">Data Upload — ' + selected_dept + '</div>', unsafe_allow_html=True)

    expected_cols = DEPT_UPLOAD_COLS.get(selected_dept, [])
    st.markdown(f"""<div class="upload-info">
        <div class="upload-title">Upload {selected_dept} Data</div>
        <div class="upload-sub">Accepted formats: CSV, XLSX &nbsp;|&nbsp; Expected columns (flexible): {', '.join(expected_cols)}</div>
    </div>""", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Upload department data file", type=["csv","xlsx"], label_visibility="collapsed")
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                uploaded_df = pd.read_csv(uploaded_file)
            else:
                uploaded_df = pd.read_excel(uploaded_file)
            st.success(f"File loaded — {len(uploaded_df)} records, {len(uploaded_df.columns)} columns.")
            with st.expander("Preview uploaded data"):
                st.dataframe(uploaded_df.head(20), width="stretch")
        except Exception as e:
            st.error(f"Could not read file: {e}")

# ── Welcome state ─────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.markdown('<div class="section-label">Platform Overview</div>', unsafe_allow_html=True)

    st.markdown("""<div class="stat-row">
        <div class="stat-cell">
            <div class="stat-num">9</div>
            <div class="stat-lbl">Departments Covered</div>
        </div>
        <div class="stat-cell">
            <div class="stat-num">2</div>
            <div class="stat-lbl">Data Modes</div>
        </div>
        <div class="stat-cell">
            <div class="stat-num">60+</div>
            <div class="stat-lbl">Fraud Pattern Types</div>
        </div>
        <div class="stat-cell stat-cell-accent">
            <div class="stat-num stat-num-accent">AI</div>
            <div class="stat-lbl stat-lbl-accent">Claude-Powered Analysis</div>
        </div>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-label">Synthetic Data Mode</div>', unsafe_allow_html=True)
        st.markdown("""<div class="sc-card">
            <div class="sc-title">Pre-loaded Company Data</div>
            <div class="sc-desc">Select any of 12 fictional companies — FraudSense generates a complete, realistic dataset across all 9 departments with embedded anomalies. Ideal for demos, sales pitches, and investor presentations. No setup required.</div>
        </div>""", unsafe_allow_html=True)
        for co in COMPANY_NAMES[:4]:
            st.markdown(f'<div style="font-family:var(--mono);font-size:0.75rem;color:var(--ink3);padding:4px 0;border-bottom:1px solid var(--border);">{co}</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-family:var(--mono);font-size:0.72rem;color:var(--accent);padding-top:6px;">+ 8 more companies</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-label">Real Data Upload Mode</div>', unsafe_allow_html=True)
        st.markdown("""<div class="sc-card">
            <div class="sc-title">Analyse Your Own Data</div>
            <div class="sc-desc">Upload CSV or Excel files from your actual systems. The AI reads your data structure, detects anomalies, and generates fraud scenarios grounded in your real numbers. Accepts flexible column formats per department.</div>
        </div>""", unsafe_allow_html=True)
        for dept, cols in list(DEPT_UPLOAD_COLS.items())[:4]:
            st.markdown(f'<div style="font-family:var(--mono);font-size:0.72rem;color:var(--ink3);padding:4px 0;border-bottom:1px solid var(--border);"><strong style="color:var(--ink);">{dept}</strong></div>', unsafe_allow_html=True)
        st.markdown('<div style="font-family:var(--mono);font-size:0.72rem;color:var(--accent);padding-top:6px;">+ 5 more department templates</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info("Configure your assessment in the sidebar and click Run Assessment to begin.")

# ── Run Analysis ──────────────────────────────────────────────────────────────
if run_btn:
    _key_check = st.session_state.get("api_key", "") or st.secrets.get("ANTHROPIC_API_KEY", "")
    if not _key_check:
        st.error("An Anthropic API key is required. Add it in the sidebar or in Streamlit Cloud Secrets.")
        st.stop()
    if not company_choice:
        st.error("Please enter a company name.")
        st.stop()
    if data_mode == "Upload Real Data" and uploaded_df is None:
        st.error("Please upload a data file before running the assessment.")
        st.stop()

    client = get_client()

    # Get dataframe
    if data_mode == "Synthetic Company Data":
        all_data = generate_company_data(company_choice)
        df = all_data[selected_dept]
    else:
        df = uploaded_df

    summary_text = df_summary(df, selected_dept)

    # Progress UI
    progress = st.progress(0)
    status   = st.empty()

    status.markdown(f"**Step 1 of 3** — Analysing {selected_dept} dataset for {company_choice}...")
    time.sleep(0.4)
    progress.progress(15)

    # Generate scenarios
    status.markdown(f"**Step 1 of 3** — Generating {num_scenarios} fraud scenarios...")
    try:
        scenarios = generate_scenarios(client, selected_dept, company_choice, company_size, industry, summary_text, num_scenarios)
        progress.progress(35)
    except Exception as e:
        st.error(f"Scenario generation failed: {type(e).__name__}: {e}")
        import traceback
        st.code(traceback.format_exc(), language="text")
        st.stop()

    # Analyze each
    analyses = []
    for i, s in enumerate(scenarios):
        pct = 35 + int((i+1)/len(scenarios)*45)
        progress.progress(pct)
        status.markdown(f"**Step 2 of 3** — Deep analysis: scenario {i+1} of {len(scenarios)} — *{s['title']}*")
        try:
            a = analyze_scenario(client, s, selected_dept, company_choice, company_size, industry, summary_text)
            analyses.append(a)
        except Exception as e:
            analyses.append(f"Analysis unavailable: {e}")
        time.sleep(0.2)

    # Executive summary
    progress.progress(88)
    status.markdown("**Step 3 of 3** — Compiling executive summary...")
    try:
        exec_sum = generate_exec_summary(client, scenarios, selected_dept, company_choice, company_size, industry)
    except Exception as e:
        exec_sum = f"Executive summary unavailable: {e}"

    progress.progress(100)
    status.markdown("Assessment complete.")
    time.sleep(0.6)
    status.empty()
    progress.empty()

    st.session_state.results = {
        "scenarios": scenarios,
        "analyses": analyses,
        "exec_summary": exec_sum,
        "company": company_choice,
        "department": selected_dept,
        "company_size": company_size,
        "industry": industry,
        "data_mode": data_mode,
        "df": df,
        "generated_at": datetime.now().strftime("%d %B %Y, %H:%M"),
    }
    st.rerun()

# ── Display Results ───────────────────────────────────────────────────────────
if st.session_state.get("results"):
    r         = st.session_state.results
    scenarios = r["scenarios"]
    analyses  = r["analyses"]
    df        = r["df"]

    critical = sum(1 for s in scenarios if s["risk_level"]=="Critical")
    high     = sum(1 for s in scenarios if s["risk_level"]=="High")
    medium   = sum(1 for s in scenarios if s["risk_level"]=="Medium")
    low      = sum(1 for s in scenarios if s["risk_level"]=="Low")

    # Header
    st.markdown(f'<div class="section-label">Assessment Report — {r["company"]} — {r["department"]}</div>', unsafe_allow_html=True)
    st.caption(f'Generated {r["generated_at"]}  |  {r["company_size"]}  |  {r["industry"]}  |  Data: {r["data_mode"]}')

    # Stats
    st.markdown(f"""<div class="stat-row">
        <div class="stat-cell">
            <div class="stat-num">{len(scenarios)}</div>
            <div class="stat-lbl">Scenarios Identified</div>
        </div>
        <div class="stat-cell">
            <div class="stat-num" style="color:#c8390a">{critical}</div>
            <div class="stat-lbl">Critical Risk</div>
        </div>
        <div class="stat-cell">
            <div class="stat-num" style="color:#c05c00">{high}</div>
            <div class="stat-lbl">High Risk</div>
        </div>
        <div class="stat-cell">
            <div class="stat-num" style="color:#1a6b3c">{medium + low}</div>
            <div class="stat-lbl">Medium / Low</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Fraud Scenarios", "Deep Analysis", "Executive Report", "Source Data"])

    # ── Tab 1: Scenarios ──────────────────────────────────────────────────────
    with tab1:
        st.markdown('<div class="section-label">Identified Fraud Scenarios</div>', unsafe_allow_html=True)
        sorted_s = sorted(scenarios, key=lambda x: ["Critical","High","Medium","Low"].index(x["risk_level"]))
        for s in sorted_s:
            flags_html = "".join([f'<div class="sc-flag">{f}</div>' for f in s["red_flags"]])
            st.markdown(f"""<div class="sc-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">
                    <div class="sc-title">{s['id']}. {s['title']}</div>
                    {pill(s['risk_level'])}
                </div>
                <div class="sc-desc">{s['description']}</div>
                <div class="sc-meta">
                    <span>Est. Loss: {s['estimated_loss']}</span>
                    <span>Likelihood: {s['likelihood']}</span>
                    <span>Type: {s['fraud_type']}</span>
                </div>
                <div class="sc-flags">
                    <div style="font-family:var(--mono);font-size:0.65rem;color:var(--ink3);letter-spacing:1px;text-transform:uppercase;margin-bottom:0.3rem;">Warning Signs</div>
                    {flags_html}
                </div>
            </div>""", unsafe_allow_html=True)

    # ── Tab 2: Deep Analysis ──────────────────────────────────────────────────
    with tab2:
        st.markdown('<div class="section-label">Scenario Deep Dives</div>', unsafe_allow_html=True)
        for i, (s, analysis) in enumerate(zip(scenarios, analyses)):
            with st.expander(f"{s['id']}. {s['title']}  —  {s['risk_level']}", expanded=(i==0)):
                parsed = parse_analysis(analysis)
                section_cfg = [
                    ("Attack Vector",         "ATTACK_VECTOR",        False),
                    ("Detection Difficulty",  "DETECTION_DIFFICULTY", False),
                    ("Financial Impact",      "FINANCIAL_IMPACT",     False),
                    ("Controls Assessment",   "CONTROLS_ASSESSMENT",  False),
                    ("Recommendations",       "RECOMMENDATIONS",      False),
                    ("Quick Win",             "QUICK_WIN",            True),
                ]
                for label, key, is_qw in section_cfg:
                    content = parsed.get(key, "")
                    if content:
                        extra_cls = "an-quickwin" if is_qw else ""
                        st.markdown(f"""<div class="an-block {extra_cls}">
                            <div class="an-label">{label}</div>
                            <div class="an-content">{content.replace(chr(10),'<br>')}</div>
                        </div>""", unsafe_allow_html=True)

    # ── Tab 3: Executive Report ───────────────────────────────────────────────
    with tab3:
        st.markdown('<div class="section-label">Executive Summary</div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="exec-block">
            <div class="exec-heading">Confidential — Board-Level Summary</div>
            <div class="exec-text">{r['exec_summary'].replace(chr(10),'<br><br>')}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-label" style="margin-top:2rem;">Risk Register</div>', unsafe_allow_html=True)
        sorted_r = sorted(scenarios, key=lambda x: ["Critical","High","Medium","Low"].index(x["risk_level"]))
        rows_html = ""
        for s in sorted_r:
            rows_html += f"""<tr>
                <td class="mono">{s['id']}</td>
                <td><strong>{s['title']}</strong></td>
                <td>{pill(s['risk_level'])}</td>
                <td class="mono">{s['fraud_type']}</td>
                <td class="mono">{s['estimated_loss']}</td>
                <td class="mono">{s['likelihood']}</td>
            </tr>"""
        st.markdown(f"""<div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;overflow:hidden;">
            <table class="risk-table">
                <thead><tr>
                    <th>#</th><th>Scenario</th><th>Risk</th><th>Fraud Type</th><th>Est. Loss</th><th>Likelihood</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>""", unsafe_allow_html=True)

        # Download
        st.markdown("<br>", unsafe_allow_html=True)
        report_lines = [
            f"FRAUDSense AI — FRAUD RISK ASSESSMENT",
            f"{'='*60}",
            f"Client:     {r['company']}",
            f"Department: {r['department']}",
            f"Profile:    {r['company_size']} | {r['industry']}",
            f"Generated:  {r['generated_at']}",
            f"Data Mode:  {r['data_mode']}",
            f"{'='*60}",
            "", "EXECUTIVE SUMMARY", "-"*40,
            r["exec_summary"], "",
            "RISK REGISTER", "-"*40,
        ]
        for s in sorted_r:
            report_lines.append(f"#{s['id']} {s['title']} | {s['risk_level']} | {s['fraud_type']} | {s['estimated_loss']} | {s['likelihood']}")
        report_lines += ["", "DETAILED SCENARIO ANALYSIS", "="*60]
        for s, a in zip(scenarios, analyses):
            report_lines += ["", f"SCENARIO {s['id']}: {s['title']}", "-"*40,
                             f"Risk: {s['risk_level']} | Loss: {s['estimated_loss']} | Likelihood: {s['likelihood']}",
                             f"Type: {s['fraud_type']}", "",
                             f"Description: {s['description']}", "",
                             "Red Flags:"] + [f"  - {f}" for f in s["red_flags"]] + ["", a, ""]
        report_text = "\n".join(report_lines)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download Report (.txt)", data=report_text,
                               file_name=f"fraudsense_{r['company'].replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                               mime="text/plain", width="stretch")
        with col2:
            csv_buf = io.StringIO()
            risk_df = pd.DataFrame([{
                "ID": s["id"], "Scenario": s["title"], "Risk Level": s["risk_level"],
                "Fraud Type": s["fraud_type"], "Est. Loss": s["estimated_loss"],
                "Likelihood": s["likelihood"], "Description": s["description"],
            } for s in scenarios])
            risk_df.to_csv(csv_buf, index=False)
            st.download_button("Download Risk Register (.csv)", data=csv_buf.getvalue(),
                               file_name=f"risk_register_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime="text/csv", width="stretch")

    # ── Tab 4: Source Data ────────────────────────────────────────────────────
    with tab4:
        st.markdown('<div class="section-label">Source Dataset — ' + r["department"] + '</div>', unsafe_allow_html=True)

        mode_label = "Synthetic (AI-generated)" if r["data_mode"]=="Synthetic Company Data" else "Uploaded by user"
        flag_cols  = [c for c in df.columns if "Flag" in c]
        flag_counts = {c: int((df[c]=="Yes").sum()) for c in flag_cols} if flag_cols else {}

        st.markdown(f"""<div class="data-info">
            <strong>Company:</strong> {r['company']} &nbsp;|&nbsp;
            <strong>Department:</strong> {r['department']} &nbsp;|&nbsp;
            <strong>Source:</strong> {mode_label} &nbsp;|&nbsp;
            <strong>Records:</strong> {len(df):,} &nbsp;|&nbsp;
            <strong>Columns:</strong> {len(df.columns)}
            {"&nbsp;|&nbsp;<strong>Flagged records:</strong> " + ", ".join([f"{v} {k}" for k,v in flag_counts.items()]) if flag_counts else ""}
        </div>""", unsafe_allow_html=True)

        # Flagged rows first if synthetic
        if flag_cols and r["data_mode"]=="Synthetic Company Data":
            st.markdown('<div style="font-family:var(--mono);font-size:0.7rem;color:var(--accent);letter-spacing:1px;text-transform:uppercase;margin-bottom:0.5rem;">Anomalous Records</div>', unsafe_allow_html=True)
            mask = df[flag_cols].eq("Yes").any(axis=1)
            st.dataframe(df[mask], width="stretch", height=240)
            st.markdown('<div style="font-family:var(--mono);font-size:0.7rem;color:var(--ink3);letter-spacing:1px;text-transform:uppercase;margin:1rem 0 0.5rem;">Full Dataset</div>', unsafe_allow_html=True)

        st.dataframe(df, width="stretch", height=360)

        # Download dataset
        csv_out = df.to_csv(index=False)
        st.download_button("Download Dataset (.csv)", data=csv_out,
                           file_name=f"{r['company'].replace(' ','_')}_{r['department'].replace(' ','_')}.csv",
                           mime="text/csv")