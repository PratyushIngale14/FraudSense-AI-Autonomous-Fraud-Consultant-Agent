"""Two synthetic warehouses that look completely different but represent the
SAME reality. The whole pitch: one engine auto-maps each schema it has never
seen and produces correct, grounded gap analysis on both with zero code changes.

Each warehouse provides:
  profile       table -> {row_count, columns: {col: {dtype, null_pct, samples}}}
  ground_truth  canonical "Entity.field" -> "table.column"  (authored truth;
                fields genuinely absent from this warehouse are simply omitted)

ground_truth is NEVER shown to the discovery agent. It exists only so the
Evaluation layer can score the AI's mapping (precision / recall / accuracy).

By construction the two warehouses have DIFFERENT real gaps:
  Warehouse A (cryptic enterprise): no approval link on bank changes, and no
              privileged flag on access grants  -> those patterns not-detectable.
  Warehouse B (clean HR):           has both of those, BUT lacks vendor
              provenance (created_date / created_by) -> vendor patterns suffer.
Neither is perfect; each fails where the other succeeds. That's the point.
"""

# ─────────────────────────────────────────────────────────────────────────────
# WAREHOUSE A — cryptic enterprise (Workday / Okta / Salesforce flavored)
# ─────────────────────────────────────────────────────────────────────────────
WAREHOUSE_A = {
    "id": "A",
    "name": "Helix Health Group",
    "style": "Cryptic enterprise stack — Workday HCM, Okta, Salesforce custom objects.",
    "profile": {
        "WD_WORKER_DIM": {
            "row_count": 4820,
            "columns": {
                "WKR_ID":        {"dtype": "string", "null_pct": 0.0,  "samples": ["WKR-0001", "WKR-0002", "WKR-1184"]},
                "WKR_TYPE_C":    {"dtype": "string", "null_pct": 0.0,  "samples": ["EmplFTE", "CntngtWkr", "CspLitePortal"]},
                "WKR_STAT_C":    {"dtype": "string", "null_pct": 0.0,  "samples": ["A", "T", "LOA"]},
                "PRIM_EMAIL_C":  {"dtype": "string", "null_pct": 3.1,  "samples": ["j.reyes@helix.com", "m.osei@helix.com"]},
                "DEPT_CD":       {"dtype": "string", "null_pct": 1.2,  "samples": ["CLIN-OPS", "FIN-AP", "IT-INFRA"]},
                "SUPVR_WKR_ID":  {"dtype": "string", "null_pct": 6.0,  "samples": ["WKR-0044", "WKR-0102"]},
            },
        },
        "WD_PAY_RUN_FACT": {
            "row_count": 58110,
            "columns": {
                "PAY_RUN_LINE_ID": {"dtype": "string", "null_pct": 0.0, "samples": ["PRL-90001", "PRL-90002"]},
                "WKR_ID":          {"dtype": "string", "null_pct": 0.0, "samples": ["WKR-0001", "WKR-1184"]},
                "GROSS_AMT":       {"dtype": "number", "null_pct": 0.0, "samples": [3142.50, 5890.00, 2200.75]},
                "PAY_DT":          {"dtype": "date",   "null_pct": 0.0, "samples": ["2026-05-15", "2026-05-30"]},
                "DD_ACCT_TOKEN":   {"dtype": "string", "null_pct": 0.4, "samples": ["tok_a91f", "tok_77c2", "tok_a91f"]},
            },
        },
        "DIRECT_DEPOSIT_CONFIRMATION_C": {
            "row_count": 1290,
            "columns": {
                "DDC_ID":        {"dtype": "string", "null_pct": 0.0, "samples": ["DDC-5001", "DDC-5002"]},
                "WKR_ID":        {"dtype": "string", "null_pct": 0.0, "samples": ["WKR-0001", "WKR-0322"]},
                "OLD_ACCT_MASK": {"dtype": "string", "null_pct": 12.0, "samples": ["****1182", "****0049"]},
                "NEW_ACCT_MASK": {"dtype": "string", "null_pct": 0.0,  "samples": ["****8830", "****1182"]},
                "EFF_DT":        {"dtype": "date",   "null_pct": 0.0,  "samples": ["2026-04-02", "2026-05-19"]},
                # NOTE: there is deliberately NO approval column on this object.
            },
        },
        "OKTA_SYS_LOG": {
            "row_count": 2104550,
            "columns": {
                "EVT_UUID":     {"dtype": "string", "null_pct": 0.0, "samples": ["a1f3-9c", "b2e4-7d"]},
                "ACTOR_ID":     {"dtype": "string", "null_pct": 0.0, "samples": ["WKR-0001", "WKR-1184"]},
                "EVT_TS":       {"dtype": "timestamp", "null_pct": 0.0, "samples": ["2026-05-30T08:14:22Z", "2026-05-30T08:14:39Z"]},
                "EVT_OUTCOME":  {"dtype": "string", "null_pct": 0.0, "samples": ["SUCCESS", "FAILURE", "DENIED"]},
                "CLIENT_IP":    {"dtype": "string", "null_pct": 0.2, "samples": ["41.90.12.7", "98.14.220.3"]},
                "CLIENT_GEO":   {"dtype": "string", "null_pct": 1.5, "samples": ["NG", "US", "DE"]},
            },
        },
        "OKTA_APP_ASSIGNMENT": {
            "row_count": 31200,
            "columns": {
                "ASSGN_ID":       {"dtype": "string", "null_pct": 0.0, "samples": ["ASG-7001", "ASG-7002"]},
                "ACTOR_ID":       {"dtype": "string", "null_pct": 0.0, "samples": ["WKR-0001", "WKR-0322"]},
                "APP_LABEL":      {"dtype": "string", "null_pct": 0.0, "samples": ["Epic-EHR", "AWS-Console", "Workday"]},
                "ASSGN_TS":       {"dtype": "timestamp", "null_pct": 0.0, "samples": ["2026-01-12T10:00:00Z"]},
                "ASSIGNED_BY_ID": {"dtype": "string", "null_pct": 4.0, "samples": ["WKR-0044", "WKR-0102"]},
                # NOTE: no admin/privilege flag on assignments.
            },
        },
        "WD_TERMINATION_EVENT": {
            "row_count": 940,
            "columns": {
                "WKR_ID":     {"dtype": "string", "null_pct": 0.0, "samples": ["WKR-0322", "WKR-0815"]},
                "TERM_EFF_DT": {"dtype": "date",  "null_pct": 0.0, "samples": ["2026-03-31", "2026-05-01"]},
                "TERM_RSN_C": {"dtype": "string", "null_pct": 2.0, "samples": ["VOL", "INVOL", "RIF"]},
            },
        },
        "SF_VENDOR__C": {
            "row_count": 612,
            "columns": {
                "VND_ID":       {"dtype": "string", "null_pct": 0.0, "samples": ["a0X1", "a0X2"]},
                "VND_NAME_C":   {"dtype": "string", "null_pct": 0.0, "samples": ["Meridian Clinical Supplies", "Apex Diagnostics"]},
                "REMIT_ACCT_C": {"dtype": "string", "null_pct": 8.0, "samples": ["****8830", "****4471"]},
                "BILL_ADDR_C":  {"dtype": "string", "null_pct": 5.0, "samples": ["120 Main St, Boston MA", "PO Box 91"]},
                "CREATEDDATE":  {"dtype": "timestamp", "null_pct": 0.0, "samples": ["2025-11-02T09:13:00Z"]},
                "CREATEDBYID":  {"dtype": "string", "null_pct": 0.0, "samples": ["WKR-0044", "WKR-0210"]},
            },
        },
        "WD_BP_APPROVAL": {
            "row_count": 14880,
            "columns": {
                "BP_APPR_ID":    {"dtype": "string", "null_pct": 0.0, "samples": ["BPA-3001", "BPA-3002"]},
                "APPR_WKR_ID":   {"dtype": "string", "null_pct": 0.0, "samples": ["WKR-0044", "WKR-0102"]},
                "BP_TYPE_C":     {"dtype": "string", "null_pct": 0.0, "samples": ["EXPENSE_RPT", "REQUISITION", "OFFER"]},
                "BP_TARGET_ID":  {"dtype": "string", "null_pct": 0.0, "samples": ["EXP-221", "REQ-889"]},
                "BP_DECISION_C": {"dtype": "string", "null_pct": 0.0, "samples": ["APPROVED", "DENIED"]},
                "BP_DECISION_DT": {"dtype": "date",  "null_pct": 0.0, "samples": ["2026-02-10", "2026-04-22"]},
                # NOTE: BP_TYPE_C never includes a bank-change object type.
            },
        },
    },
    # Authored ground truth — what the schema ACTUALLY means.
    "ground_truth": {
        "Identity.identity_id":      "WD_WORKER_DIM.WKR_ID",
        "Identity.role":             "WD_WORKER_DIM.WKR_TYPE_C",
        "Identity.status":           "WD_WORKER_DIM.WKR_STAT_C",
        "Identity.email":            "WD_WORKER_DIM.PRIM_EMAIL_C",
        "Identity.department":       "WD_WORKER_DIM.DEPT_CD",
        "Identity.manager_id":       "WD_WORKER_DIM.SUPVR_WKR_ID",

        "PayrollPayment.payment_id":  "WD_PAY_RUN_FACT.PAY_RUN_LINE_ID",
        "PayrollPayment.identity_id": "WD_PAY_RUN_FACT.WKR_ID",
        "PayrollPayment.amount":      "WD_PAY_RUN_FACT.GROSS_AMT",
        "PayrollPayment.pay_date":    "WD_PAY_RUN_FACT.PAY_DT",
        "PayrollPayment.bank_account": "WD_PAY_RUN_FACT.DD_ACCT_TOKEN",

        "BankAccountChange.change_id":   "DIRECT_DEPOSIT_CONFIRMATION_C.DDC_ID",
        "BankAccountChange.identity_id": "DIRECT_DEPOSIT_CONFIRMATION_C.WKR_ID",
        "BankAccountChange.old_account": "DIRECT_DEPOSIT_CONFIRMATION_C.OLD_ACCT_MASK",
        "BankAccountChange.new_account": "DIRECT_DEPOSIT_CONFIRMATION_C.NEW_ACCT_MASK",
        "BankAccountChange.change_date": "DIRECT_DEPOSIT_CONFIRMATION_C.EFF_DT",
        # BankAccountChange.approval_id  -> ABSENT (no approval on the object)

        "AccessGrant.grant_id":    "OKTA_APP_ASSIGNMENT.ASSGN_ID",
        "AccessGrant.identity_id": "OKTA_APP_ASSIGNMENT.ACTOR_ID",
        "AccessGrant.resource":    "OKTA_APP_ASSIGNMENT.APP_LABEL",
        "AccessGrant.grant_date":  "OKTA_APP_ASSIGNMENT.ASSGN_TS",
        "AccessGrant.granted_by":  "OKTA_APP_ASSIGNMENT.ASSIGNED_BY_ID",
        # AccessGrant.privileged   -> ABSENT (no admin flag)

        "AuthEvent.event_id":    "OKTA_SYS_LOG.EVT_UUID",
        "AuthEvent.identity_id": "OKTA_SYS_LOG.ACTOR_ID",
        "AuthEvent.event_time":  "OKTA_SYS_LOG.EVT_TS",
        "AuthEvent.outcome":     "OKTA_SYS_LOG.EVT_OUTCOME",
        "AuthEvent.ip_address":  "OKTA_SYS_LOG.CLIENT_IP",
        "AuthEvent.geo":         "OKTA_SYS_LOG.CLIENT_GEO",

        "Termination.identity_id":      "WD_TERMINATION_EVENT.WKR_ID",
        "Termination.termination_date": "WD_TERMINATION_EVENT.TERM_EFF_DT",
        "Termination.reason":           "WD_TERMINATION_EVENT.TERM_RSN_C",

        "Vendor.vendor_id":    "SF_VENDOR__C.VND_ID",
        "Vendor.name":         "SF_VENDOR__C.VND_NAME_C",
        "Vendor.bank_account": "SF_VENDOR__C.REMIT_ACCT_C",
        "Vendor.address":      "SF_VENDOR__C.BILL_ADDR_C",
        "Vendor.created_date": "SF_VENDOR__C.CREATEDDATE",
        "Vendor.created_by":   "SF_VENDOR__C.CREATEDBYID",

        "Approval.approval_id":   "WD_BP_APPROVAL.BP_APPR_ID",
        "Approval.approver_id":   "WD_BP_APPROVAL.APPR_WKR_ID",
        "Approval.object_type":   "WD_BP_APPROVAL.BP_TYPE_C",
        "Approval.object_id":     "WD_BP_APPROVAL.BP_TARGET_ID",
        "Approval.decision":      "WD_BP_APPROVAL.BP_DECISION_C",
        "Approval.decision_date": "WD_BP_APPROVAL.BP_DECISION_DT",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# WAREHOUSE B — clean lowercase HR-style schema (different company, same reality)
# ─────────────────────────────────────────────────────────────────────────────
WAREHOUSE_B = {
    "id": "B",
    "name": "Northwind Retail Co",
    "style": "Clean, well-named lowercase HR/IAM warehouse (dbt-modeled).",
    "profile": {
        "employees": {
            "row_count": 2310,
            "columns": {
                "employee_id":     {"dtype": "int",    "null_pct": 0.0, "samples": [10001, 10002, 11840]},
                "employment_type": {"dtype": "string", "null_pct": 0.0, "samples": ["full_time", "contractor", "seasonal"]},
                "status":          {"dtype": "string", "null_pct": 0.0, "samples": ["active", "terminated", "on_leave"]},
                "email":           {"dtype": "string", "null_pct": 0.5, "samples": ["a.khan@northwind.co", "p.dane@northwind.co"]},
                "department":      {"dtype": "string", "null_pct": 0.0, "samples": ["Store Ops", "Finance", "IT"]},
                "manager_id":      {"dtype": "int",    "null_pct": 4.0, "samples": [10044, 10102]},
            },
        },
        "payroll_runs": {
            "row_count": 41200,
            "columns": {
                "run_id":          {"dtype": "int",    "null_pct": 0.0, "samples": [990001, 990002]},
                "employee_id":     {"dtype": "int",    "null_pct": 0.0, "samples": [10001, 11840]},
                "gross_pay":       {"dtype": "number", "null_pct": 0.0, "samples": [2900.00, 4150.50]},
                "pay_date":        {"dtype": "date",   "null_pct": 0.0, "samples": ["2026-05-15", "2026-05-31"]},
                "deposit_account": {"dtype": "string", "null_pct": 0.3, "samples": ["GB29-8830", "GB29-1182"]},
            },
        },
        "bank_account_changes": {
            "row_count": 880,
            "columns": {
                "change_id":        {"dtype": "int",    "null_pct": 0.0,  "samples": [5001, 5002]},
                "employee_id":      {"dtype": "int",    "null_pct": 0.0,  "samples": [10001, 10322]},
                "previous_account": {"dtype": "string", "null_pct": 10.0, "samples": ["GB29-1182", "GB29-0049"]},
                "new_account":      {"dtype": "string", "null_pct": 0.0,  "samples": ["GB29-8830", "GB29-1182"]},
                "changed_at":       {"dtype": "timestamp", "null_pct": 0.0, "samples": ["2026-04-02T11:00:00Z"]},
                "approved_by":      {"dtype": "int",    "null_pct": 18.0, "samples": [10044, 10102]},
                "approval_status":  {"dtype": "string", "null_pct": 0.0,  "samples": ["approved", "pending", "auto"]},
            },
        },
        "auth_events": {
            "row_count": 1560000,
            "columns": {
                "id":          {"dtype": "string", "null_pct": 0.0, "samples": ["e-9001", "e-9002"]},
                "user_id":     {"dtype": "int",    "null_pct": 0.0, "samples": [10001, 11840]},
                "event_time":  {"dtype": "timestamp", "null_pct": 0.0, "samples": ["2026-05-30T08:14:22Z"]},
                "outcome":     {"dtype": "string", "null_pct": 0.0, "samples": ["success", "failure", "mfa_denied"]},
                "ip_address":  {"dtype": "string", "null_pct": 0.1, "samples": ["41.90.12.7", "98.14.220.3"]},
                "geo_country": {"dtype": "string", "null_pct": 0.8, "samples": ["NG", "US", "GB"]},
            },
        },
        "access_grants": {
            "row_count": 18900,
            "columns": {
                "grant_id":    {"dtype": "int",    "null_pct": 0.0, "samples": [7001, 7002]},
                "user_id":     {"dtype": "int",    "null_pct": 0.0, "samples": [10001, 10322]},
                "system_name": {"dtype": "string", "null_pct": 0.0, "samples": ["POS-Core", "AWS", "SAP"]},
                "granted_at":  {"dtype": "timestamp", "null_pct": 0.0, "samples": ["2026-01-12T10:00:00Z"]},
                "granted_by":  {"dtype": "int",    "null_pct": 3.0, "samples": [10044, 10102]},
                "is_admin":    {"dtype": "bool",   "null_pct": 0.0, "samples": [True, False, False]},
            },
        },
        "terminations": {
            "row_count": 510,
            "columns": {
                "employee_id": {"dtype": "int",    "null_pct": 0.0, "samples": [10322, 10815]},
                "last_day":    {"dtype": "date",   "null_pct": 0.0, "samples": ["2026-03-31", "2026-05-01"]},
                "reason":      {"dtype": "string", "null_pct": 1.0, "samples": ["voluntary", "involuntary", "layoff"]},
            },
        },
        "vendors": {
            "row_count": 430,
            "columns": {
                "vendor_id":    {"dtype": "int",    "null_pct": 0.0, "samples": [3001, 3002]},
                "vendor_name":  {"dtype": "string", "null_pct": 0.0, "samples": ["Pacific Packaging", "Cedar Logistics"]},
                "bank_account": {"dtype": "string", "null_pct": 6.0, "samples": ["GB29-8830", "GB29-4471"]},
                "address":      {"dtype": "string", "null_pct": 3.0, "samples": ["55 Dock Rd, Leeds", "PO Box 12"]},
                # NOTE: no created_date / created_by — vendor provenance is missing in B.
            },
        },
        "approvals": {
            "row_count": 22400,
            "columns": {
                "approval_id":  {"dtype": "int",    "null_pct": 0.0, "samples": [4001, 4002]},
                "approver_id":  {"dtype": "int",    "null_pct": 0.0, "samples": [10044, 10102]},
                "request_type": {"dtype": "string", "null_pct": 0.0, "samples": ["expense", "bank_change", "access", "po"]},
                "request_id":   {"dtype": "string", "null_pct": 0.0, "samples": ["bc-5001", "exp-221"]},
                "decision":     {"dtype": "string", "null_pct": 0.0, "samples": ["approved", "rejected"]},
                "decided_at":   {"dtype": "timestamp", "null_pct": 0.0, "samples": ["2026-04-02T12:30:00Z"]},
            },
        },
    },
    "ground_truth": {
        "Identity.identity_id": "employees.employee_id",
        "Identity.role":        "employees.employment_type",
        "Identity.status":      "employees.status",
        "Identity.email":       "employees.email",
        "Identity.department":  "employees.department",
        "Identity.manager_id":  "employees.manager_id",

        "PayrollPayment.payment_id":   "payroll_runs.run_id",
        "PayrollPayment.identity_id":  "payroll_runs.employee_id",
        "PayrollPayment.amount":       "payroll_runs.gross_pay",
        "PayrollPayment.pay_date":     "payroll_runs.pay_date",
        "PayrollPayment.bank_account": "payroll_runs.deposit_account",

        "BankAccountChange.change_id":   "bank_account_changes.change_id",
        "BankAccountChange.identity_id": "bank_account_changes.employee_id",
        "BankAccountChange.old_account": "bank_account_changes.previous_account",
        "BankAccountChange.new_account": "bank_account_changes.new_account",
        "BankAccountChange.change_date": "bank_account_changes.changed_at",
        "BankAccountChange.approval_id": "bank_account_changes.approved_by",  # present in B

        "AccessGrant.grant_id":    "access_grants.grant_id",
        "AccessGrant.identity_id": "access_grants.user_id",
        "AccessGrant.resource":    "access_grants.system_name",
        "AccessGrant.grant_date":  "access_grants.granted_at",
        "AccessGrant.granted_by":  "access_grants.granted_by",
        "AccessGrant.privileged":  "access_grants.is_admin",  # present in B

        "AuthEvent.event_id":    "auth_events.id",
        "AuthEvent.identity_id": "auth_events.user_id",
        "AuthEvent.event_time":  "auth_events.event_time",
        "AuthEvent.outcome":     "auth_events.outcome",
        "AuthEvent.ip_address":  "auth_events.ip_address",
        "AuthEvent.geo":         "auth_events.geo_country",

        "Termination.identity_id":      "terminations.employee_id",
        "Termination.termination_date": "terminations.last_day",
        "Termination.reason":           "terminations.reason",

        "Vendor.vendor_id":    "vendors.vendor_id",
        "Vendor.name":         "vendors.vendor_name",
        "Vendor.bank_account": "vendors.bank_account",
        "Vendor.address":      "vendors.address",
        # Vendor.created_date -> ABSENT
        # Vendor.created_by   -> ABSENT

        "Approval.approval_id":   "approvals.approval_id",
        "Approval.approver_id":   "approvals.approver_id",
        "Approval.object_type":   "approvals.request_type",
        "Approval.object_id":     "approvals.request_id",
        "Approval.decision":      "approvals.decision",
        "Approval.decision_date": "approvals.decided_at",
    },
}

WAREHOUSES = {"A": WAREHOUSE_A, "B": WAREHOUSE_B}


def profile_for_prompt(warehouse: dict) -> str:
    """Render a warehouse schema profile as compact text for the discovery agent.

    Ground truth is intentionally NOT included.
    """
    lines = []
    for table, spec in warehouse["profile"].items():
        lines.append(f"TABLE {table}  (~{spec['row_count']:,} rows)")
        for col, c in spec["columns"].items():
            samples = ", ".join(str(s) for s in c["samples"])
            lines.append(f"    {col}  [{c['dtype']}, {c['null_pct']}% null]  e.g. {samples}")
        lines.append("")
    return "\n".join(lines)
