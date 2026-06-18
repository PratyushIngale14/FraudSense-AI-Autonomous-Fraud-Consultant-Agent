"""Synthetic ROW generation for the Warehouse Assurance module.

This is the warehouse module's OWN data world — it has nothing to do with
synthetic_data.py (the department-based assessment data). Do not mix them.

Strategy: generate ONE shared canonical reality (a coherent set of identities,
payroll, bank changes, access, auth, vendors, approvals, terminations) with
real fraud anomalies planted at low rates, then PROJECT it into each
warehouse's exact raw schema using that warehouse's ground_truth mapping.

Because the projection only renames columns (and drops canonical fields a
warehouse doesn't store), both warehouses represent the SAME underlying fraud
— but each is automatically blind to the subset of patterns its schema can't
support (A: no bank-change approval, no privileged flag; B: no vendor
provenance). Deterministic (seeded) so the demo is reproducible.

Public API:
    build_warehouse_rows(wid) -> { raw_table_name: DataFrame }   # for detection
    canonical_reality()       -> (canonical_dfs, planted_counts) # the source of truth
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import pandas as pd

from .warehouses import WAREHOUSES

SEED = 42
_BASE = datetime(2026, 6, 1)

# Canonical value vocabularies (projected into per-warehouse encodings below).
_ROLES = ["employee", "contractor", "external"]
_DEPTS = ["Finance", "Clinical Ops", "IT", "Store Ops", "HR", "Procurement"]
_RESOURCES = ["Epic-EHR", "AWS-Console", "Workday", "SAP", "POS-Core", "GitHub"]
_GEOS_NORMAL = ["US", "US", "US", "GB", "DE"]
_GEOS_FAR = ["NG", "RU", "BR", "SG"]

# Per-warehouse value encodings for enumerated fields (detection normalizes these).
_ENCODINGS = {
    "A": {
        "status": {"active": "A", "terminated": "T", "on_leave": "LOA"},
        "outcome": {"success": "SUCCESS", "failure": "FAILURE", "denied": "DENIED"},
        "role": {"employee": "EmplFTE", "contractor": "CntngtWkr", "external": "CspLitePortal"},
    },
    "B": {
        "status": {"active": "active", "terminated": "terminated", "on_leave": "on_leave"},
        "outcome": {"success": "success", "failure": "failure", "denied": "mfa_denied"},
        "role": {"employee": "full_time", "contractor": "contractor", "external": "seasonal"},
    },
}


def _d(days_ago: int) -> str:
    return (_BASE - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _ts(days_ago: int, hour: int = 9, minute: int = 0) -> str:
    return (_BASE - timedelta(days=days_ago)).strftime(f"%Y-%m-%dT{hour:02d}:{minute:02d}:00Z")


# ─────────────────────────────────────────────────────────────────────────────
# Canonical reality
# ─────────────────────────────────────────────────────────────────────────────
def _generate(rng: random.Random):
    planted = {}

    # ---- Identities --------------------------------------------------------
    n_ids = 260
    ids = list(range(1001, 1001 + n_ids))
    term_ids = set(rng.sample(ids, int(n_ids * 0.12)))      # ~12% terminated
    leave_ids = set(rng.sample([i for i in ids if i not in term_ids], int(n_ids * 0.05)))
    accounts = {i: 40000 + i for i in ids}                  # each identity -> primary acct int

    identity_rows = []
    for i in ids:
        status = "terminated" if i in term_ids else ("on_leave" if i in leave_ids else "active")
        identity_rows.append({
            "identity_id": i,
            "role": rng.choice(_ROLES),
            "status": status,
            "email": f"user{i}@corp.example",
            "department": rng.choice(_DEPTS),
            "manager_id": rng.choice(ids),
        })
    identity = pd.DataFrame(identity_rows)

    # ---- Terminations ------------------------------------------------------
    term_rows = []
    term_date = {}
    for i in sorted(term_ids):
        da = rng.randint(20, 150)
        term_date[i] = da
        term_rows.append({"identity_id": i, "termination_date": _d(da),
                          "reason": rng.choice(["voluntary", "involuntary", "layoff"])})
    termination = pd.DataFrame(term_rows)

    active_ids = [i for i in ids if i not in term_ids]

    # ---- Payroll -----------------------------------------------------------
    pay_rows = []
    pid = 90000
    n_pay = 680
    planted["ghost_employee"] = 0
    planted["terminated_still_paid"] = 0
    # a shared account used by several distinct identities (shared_payroll_account)
    shared_acct = 49999
    shared_payees = rng.sample(active_ids, 4)
    for _ in range(n_pay):
        pid += 1
        roll = rng.random()
        if roll < 0.06:  # GHOST: payee id not in the identity table at all
            ghost_id = rng.randint(80001, 80999)
            pay_rows.append({"payment_id": f"PAY-{pid}", "identity_id": ghost_id,
                             "amount": round(rng.uniform(2000, 6000), 2),
                             "pay_date": _d(rng.randint(1, 45)), "bank_account": 70000 + ghost_id % 500})
            planted["ghost_employee"] += 1
        elif roll < 0.12 and term_ids:  # TERMINATED STILL PAID: pay after term_date
            i = rng.choice(sorted(term_ids))
            pay_rows.append({"payment_id": f"PAY-{pid}", "identity_id": i,
                             "amount": round(rng.uniform(2000, 6000), 2),
                             "pay_date": _d(max(0, term_date[i] - rng.randint(5, 18))),
                             "bank_account": accounts[i]})
            planted["terminated_still_paid"] += 1
        else:
            i = rng.choice(active_ids)
            acct = shared_acct if i in shared_payees else accounts[i]
            pay_rows.append({"payment_id": f"PAY-{pid}", "identity_id": i,
                             "amount": round(rng.uniform(2000, 6000), 2),
                             "pay_date": _d(rng.randint(1, 45)), "bank_account": acct})
    payroll = pd.DataFrame(pay_rows)
    planted["shared_payroll_account"] = len(shared_payees)

    # ---- Approvals (built alongside the events they approve) ---------------
    appr_rows = []
    aid = 3000

    def add_approval(obj_type, obj_id, approver, days_ago, decision="approved"):
        nonlocal aid
        aid += 1
        ap = f"APR-{aid}"
        appr_rows.append({"approval_id": ap, "approver_id": approver,
                          "object_type": obj_type, "object_id": obj_id,
                          "decision": decision, "decision_date": _d(days_ago)})
        return ap

    # ---- Bank account changes ---------------------------------------------
    bac_rows = []
    cid = 5000
    n_bac = 150
    planted["unapproved_bank_change"] = 0
    planted["self_approval_bank_change"] = 0
    planted["duplicate_bank_account"] = 0
    dup_acct = 60606  # one new_account reused across identities
    dup_payees = rng.sample(active_ids, 3)
    for k in range(n_bac):
        cid += 1
        change_id = f"BAC-{cid}"
        days = rng.randint(2, 60)
        # DUPLICATE BANK ACCOUNT: first len(dup_payees) changes route distinct
        # identities to ONE shared new_account.
        if k < len(dup_payees):
            i = dup_payees[k]
            new_acct = dup_acct
            planted["duplicate_bank_account"] += 1
        else:
            i = rng.choice(active_ids)
            new_acct = accounts[i] + 5000
        roll = rng.random()
        approval_id = None
        if roll < 0.08:           # UNAPPROVED: no approval link
            approval_id = None
            planted["unapproved_bank_change"] += 1
        elif roll < 0.13:         # SELF-APPROVED: approver == the owner of the change
            approval_id = add_approval("bank_change", change_id, i, days)
            planted["self_approval_bank_change"] += 1
        else:                     # normal: approved by a manager (not the owner)
            mgr = rng.choice([x for x in active_ids if x != i])
            approval_id = add_approval("bank_change", change_id, mgr, days)
        bac_rows.append({"change_id": change_id, "identity_id": i,
                         "old_account": accounts[i], "new_account": new_acct,
                         "change_date": _d(days), "approval_id": approval_id})
    bank_change = pd.DataFrame(bac_rows)

    # ---- Access grants -----------------------------------------------------
    ag_rows = []
    gid = 7000
    n_ag = 220
    planted["access_after_termination"] = 0
    planted["priv_escalation_no_approval"] = 0
    planted["orphaned_privileged_access"] = 0
    for _ in range(n_ag):
        gid += 1
        grant_id = f"AG-{gid}"
        roll = rng.random()
        privileged = rng.random() < 0.25
        if roll < 0.06 and term_ids:  # ACCESS AFTER TERMINATION
            i = rng.choice(sorted(term_ids))
            days = max(0, term_date[i] - rng.randint(3, 15))
            ag_rows.append({"grant_id": grant_id, "identity_id": i, "resource": rng.choice(_RESOURCES),
                            "grant_date": _d(days), "granted_by": rng.choice(active_ids),
                            "privileged": privileged})
            if privileged:
                planted["orphaned_privileged_access"] += 1
            planted["access_after_termination"] += 1
            # usually no approval for these
            continue
        i = rng.choice(active_ids)
        days = rng.randint(5, 200)
        ag_rows.append({"grant_id": grant_id, "identity_id": i, "resource": rng.choice(_RESOURCES),
                        "grant_date": _d(days), "granted_by": rng.choice(active_ids),
                        "privileged": privileged})
        if privileged:
            if rng.random() < 0.30:   # PRIV ESCALATION: privileged but NO approval
                planted["priv_escalation_no_approval"] += 1
            else:                     # privileged WITH an access approval
                mgr = rng.choice(active_ids)
                add_approval("access", grant_id, mgr, days)
    access = pd.DataFrame(ag_rows)

    # ---- Auth events -------------------------------------------------------
    ae_rows = []
    eid = 100000
    n_ae = 900
    planted["login_after_termination"] = 0
    planted["impossible_travel"] = 0
    planted["dormant_reactivation"] = 0
    for _ in range(n_ae):
        eid += 1
        roll = rng.random()
        if roll < 0.05 and term_ids:   # LOGIN AFTER TERMINATION
            i = rng.choice(sorted(term_ids))
            ae_rows.append({"event_id": f"EVT-{eid}", "identity_id": i,
                            "event_time": _ts(max(0, term_date[i] - rng.randint(1, 10)), rng.randint(0, 23)),
                            "outcome": "success", "ip_address": f"41.90.{rng.randint(1,255)}.{rng.randint(1,255)}",
                            "geo": rng.choice(_GEOS_FAR)})
            planted["login_after_termination"] += 1
        else:
            i = rng.choice(active_ids)
            ae_rows.append({"event_id": f"EVT-{eid}", "identity_id": i,
                            "event_time": _ts(rng.randint(0, 40), rng.randint(0, 23), rng.randint(0, 59)),
                            "outcome": rng.choices(["success", "failure", "denied"], [0.85, 0.1, 0.05])[0],
                            "ip_address": f"98.14.{rng.randint(1,255)}.{rng.randint(1,255)}",
                            "geo": rng.choice(_GEOS_NORMAL)})
    # IMPOSSIBLE TRAVEL: a few identities with two events, distant geos, < 2h apart
    for i in rng.sample(active_ids, 5):
        d = rng.randint(1, 30)
        eid += 1
        ae_rows.append({"event_id": f"EVT-{eid}", "identity_id": i, "event_time": _ts(d, 8, 0),
                        "outcome": "success", "ip_address": "98.14.10.10", "geo": "US"})
        eid += 1
        ae_rows.append({"event_id": f"EVT-{eid}", "identity_id": i, "event_time": _ts(d, 9, 30),
                        "outcome": "success", "ip_address": "41.90.10.10", "geo": rng.choice(_GEOS_FAR)})
        planted["impossible_travel"] += 1
    # DORMANT REACTIVATION: a few identities with one very old event then a recent success
    for i in rng.sample(active_ids, 4):
        eid += 1
        ae_rows.append({"event_id": f"EVT-{eid}", "identity_id": i, "event_time": _ts(330, 10),
                        "outcome": "success", "ip_address": "98.14.5.5", "geo": "US"})
        eid += 1
        ae_rows.append({"event_id": f"EVT-{eid}", "identity_id": i, "event_time": _ts(2, 3),
                        "outcome": "success", "ip_address": "41.90.5.5", "geo": rng.choice(_GEOS_FAR)})
        planted["dormant_reactivation"] += 1
    auth = pd.DataFrame(ae_rows)

    # ---- Vendors -----------------------------------------------------------
    v_rows = []
    vid = 200
    n_v = 70
    emp_accounts = list(accounts.values())
    planted["vendor_bank_eq_employee_bank"] = 0
    planted["sod_vendor_create_and_approve"] = 0
    planted["vendor_created_paid_same_day"] = 0
    for _ in range(n_v):
        vid += 1
        vendor_id = f"VND-{vid}"
        created_days = rng.randint(10, 300)
        creator = rng.choice(active_ids)
        roll = rng.random()
        if roll < 0.06:   # VENDOR BANK == EMPLOYEE PAYROLL ACCOUNT
            bank = rng.choice(emp_accounts)
            planted["vendor_bank_eq_employee_bank"] += 1
        else:
            bank = 88000 + vid
        v_rows.append({"vendor_id": vendor_id, "name": f"Vendor {vid} Ltd",
                       "bank_account": bank, "address": f"{rng.randint(1,999)} Trade St",
                       "created_date": _d(created_days), "created_by": creator})
        # vendor/payment approvals
        r2 = rng.random()
        if r2 < 0.10:     # SoD: the vendor's payment is approved by its own creator
            add_approval("payment", vendor_id, creator, created_days - rng.randint(1, 5))
            planted["sod_vendor_create_and_approve"] += 1
        elif r2 < 0.20:   # created and paid SAME DAY
            add_approval("payment", vendor_id, rng.choice(active_ids), created_days)
            planted["vendor_created_paid_same_day"] += 1
        else:
            add_approval("payment", vendor_id, rng.choice(active_ids), max(0, created_days - rng.randint(10, 60)))
    vendor = pd.DataFrame(v_rows)

    approval = pd.DataFrame(appr_rows)

    canonical = {
        "Identity": identity, "PayrollPayment": payroll, "BankAccountChange": bank_change,
        "AccessGrant": access, "AuthEvent": auth, "Termination": termination,
        "Vendor": vendor, "Approval": approval,
    }
    return canonical, planted


_CANON_CACHE = None


def canonical_reality():
    global _CANON_CACHE
    if _CANON_CACHE is None:
        _CANON_CACHE = _generate(random.Random(SEED))
    return _CANON_CACHE


# ─────────────────────────────────────────────────────────────────────────────
# Projection into a warehouse's raw schema
# ─────────────────────────────────────────────────────────────────────────────
# Canonical columns that hold identity references / account references — styled
# per-warehouse so values look native (joins still hold because the same raw
# integer is formatted identically everywhere it appears).
_IDENTITY_COLS = {
    "Identity": ["identity_id", "manager_id"],
    "PayrollPayment": ["identity_id"], "BankAccountChange": ["identity_id"],
    "AccessGrant": ["identity_id", "granted_by"], "AuthEvent": ["identity_id"],
    "Termination": ["identity_id"], "Vendor": ["created_by"], "Approval": ["approver_id"],
}
_ACCOUNT_COLS = {
    "PayrollPayment": ["bank_account"],
    "BankAccountChange": ["old_account", "new_account"],
    "Vendor": ["bank_account"],
}
_ENUM_COLS = {  # entity -> {field: encoding_key}
    "Identity": {"status": "status", "role": "role"},
    "AuthEvent": {"outcome": "outcome"},
}


def _fmt_identity(wid, v):
    if pd.isna(v):
        return v
    return f"WKR-{int(v):05d}" if wid == "A" else int(v)


def _fmt_account(wid, v):
    if pd.isna(v):
        return v
    return f"tok_{int(v):04x}" if wid == "A" else f"GB29-{int(v):04d}"


def build_warehouse_rows(wid: str) -> dict:
    """Project the shared canonical reality into warehouse `wid`'s raw tables.

    Returns { raw_table_name: DataFrame } using the EXACT table/column names
    from wh's profile (via its ground_truth). Canonical fields the warehouse
    does not store are simply absent — reproducing its real data gaps.
    """
    wh = WAREHOUSES[wid]
    gt = wh["ground_truth"]
    canonical, _ = canonical_reality()
    enc = _ENCODINGS[wid]

    # 1. style a working copy of the canonical frames for this warehouse
    styled = {ent: df.copy() for ent, df in canonical.items()}
    for ent, cols in _IDENTITY_COLS.items():
        for c in cols:
            if c in styled[ent].columns:
                styled[ent][c] = styled[ent][c].map(lambda v: _fmt_identity(wid, v))
    for ent, cols in _ACCOUNT_COLS.items():
        for c in cols:
            if c in styled[ent].columns:
                styled[ent][c] = styled[ent][c].map(lambda v: _fmt_account(wid, v))
    for ent, fields in _ENUM_COLS.items():
        for field, ekey in fields.items():
            if field in styled[ent].columns:
                styled[ent][field] = styled[ent][field].map(lambda v: enc[ekey].get(v, v))

    # 2. project: group ground_truth targets by raw table, rename columns
    tables: dict[str, dict] = {}
    for dotted, source in gt.items():
        entity, field = dotted.split(".", 1)
        table, col = source.split(".", 1)
        if entity not in styled or field not in styled[entity].columns:
            continue
        tables.setdefault(table, {})[col] = styled[entity][field].reset_index(drop=True)

    return {t: pd.DataFrame(cols) for t, cols in tables.items()}


def planted_summary() -> dict:
    _, planted = canonical_reality()
    return dict(planted)
