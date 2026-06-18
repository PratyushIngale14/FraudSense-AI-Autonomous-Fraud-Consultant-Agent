"""Detection Execution engine.

Turns each pattern's detection_logic from a description into pandas code that
actually RUNS against the synthetic rows — and crucially runs through the
CANONICAL MAPPING, never hardcoded column names. The same detector works on
Warehouse A and B because it queries canonical concepts; the mapping resolves
those to whatever raw column each warehouse uses.

Architecture rule: detection is DETERMINISTIC pandas only. The LLM's job
(schema mapping) is upstream and separate — that's the transparency story.

Flow:
  raw_tables (per warehouse) + mapping (canonical -> table.column)
     -> materialize_canonical() builds canonical-named DataFrames
     -> each detector queries canonical fields
     -> returns count + the actual flagged rows (canonical fields shown)

If a pattern is not detectable (a critical canonical field is unmapped), it is
skipped with the reason — never faked.
"""

from __future__ import annotations

import pandas as pd

from .patterns import PATTERN_LIBRARY, pattern_by_id
from .scoring import run_all_patterns


# ─────────────────────────────────────────────────────────────────────────────
# Mapping -> canonical DataFrames
# ─────────────────────────────────────────────────────────────────────────────
def _source_of(entry):
    if entry is None:
        return None
    return entry if isinstance(entry, str) else entry.get("source")


def materialize_canonical(raw_tables: dict, mapping: dict) -> dict:
    """Build { Entity: DataFrame(canonical columns) } from raw tables + mapping."""
    cols_by_entity: dict[str, dict] = {}
    for dotted, entry in mapping.items():
        if dotted == "_raw":
            continue
        src = _source_of(entry)
        if not src or "." not in src:
            continue
        table, col = src.split(".", 1)
        df = raw_tables.get(table)
        if df is None or col not in df.columns:
            continue
        entity, field = dotted.split(".", 1)
        cols_by_entity.setdefault(entity, {})[field] = df[col].reset_index(drop=True)
    return {ent: pd.DataFrame(cols) for ent, cols in cols_by_entity.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic value normalizers (handle per-warehouse encodings)
# ─────────────────────────────────────────────────────────────────────────────
_ACTIVE = {"active", "a", "employed", "enabled", "1", "true"}
_SUCCESS = {"success", "succeeded", "ok", "allow", "allowed", "pass", "passed"}
_TRUTHY = {"true", "1", "admin", "yes", "privileged", "y", "t"}


def _is_active(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(_ACTIVE)


def _is_success(s: pd.Series) -> pd.Series:
    low = s.astype(str).str.strip().str.lower()
    return low.str.startswith("success") | low.isin(_SUCCESS)


def _is_privileged(s: pd.Series) -> pd.Series:
    return s.map(lambda v: v is True or str(v).strip().lower() in _TRUTHY)


def _dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=True)


def _has(canon: dict, entity: str, *fields) -> bool:
    df = canon.get(entity)
    return df is not None and all(f in df.columns for f in fields)


# ─────────────────────────────────────────────────────────────────────────────
# Detectors — each queries CANONICAL fields only. Returns flagged DataFrame.
# Return None means "no executable detector ran" (caller reports it).
# ─────────────────────────────────────────────────────────────────────────────
def _ghost_employee(c):
    if not (_has(c, "PayrollPayment", "identity_id") and _has(c, "Identity", "identity_id")):
        return None
    pay, ident = c["PayrollPayment"], c["Identity"]
    known = set(ident["identity_id"].astype(str))
    flagged = pay[~pay["identity_id"].astype(str).isin(known)].copy()
    flagged["why"] = "payee has no matching Identity record"
    return flagged


def _terminated_still_paid(c):
    if not (_has(c, "PayrollPayment", "identity_id", "pay_date")
            and _has(c, "Termination", "identity_id", "termination_date")):
        return None
    pay = c["PayrollPayment"].copy()
    term = c["Termination"][["identity_id", "termination_date"]].copy()
    pay["identity_id"] = pay["identity_id"].astype(str)
    term["identity_id"] = term["identity_id"].astype(str)
    m = pay.merge(term, on="identity_id", how="inner")
    flagged = m[_dt(m["pay_date"]) > _dt(m["termination_date"])].copy()
    flagged["why"] = "pay_date is after termination_date"
    return flagged


def _unapproved_bank_change(c):
    if not _has(c, "BankAccountChange", "approval_id"):
        return None
    bac = c["BankAccountChange"]
    ap = bac["approval_id"]
    flagged = bac[ap.isna() | (ap.astype(str).str.strip().isin(["", "None", "nan"]))].copy()
    flagged["why"] = "bank change has no linked approval"
    return flagged


def _access_after_termination(c):
    if not (_has(c, "AccessGrant", "identity_id", "grant_date")
            and _has(c, "Termination", "identity_id", "termination_date")):
        return None
    ag = c["AccessGrant"].copy(); ag["identity_id"] = ag["identity_id"].astype(str)
    term = c["Termination"][["identity_id", "termination_date"]].copy()
    term["identity_id"] = term["identity_id"].astype(str)
    m = ag.merge(term, on="identity_id", how="inner")
    flagged = m[_dt(m["grant_date"]) > _dt(m["termination_date"])].copy()
    flagged["why"] = "access granted after termination_date"
    return flagged


def _login_after_termination(c):
    if not (_has(c, "AuthEvent", "identity_id", "event_time")
            and _has(c, "Termination", "identity_id", "termination_date")):
        return None
    ae = c["AuthEvent"].copy(); ae["identity_id"] = ae["identity_id"].astype(str)
    if "outcome" in ae.columns:
        ae = ae[_is_success(ae["outcome"])]
    term = c["Termination"][["identity_id", "termination_date"]].copy()
    term["identity_id"] = term["identity_id"].astype(str)
    m = ae.merge(term, on="identity_id", how="inner")
    flagged = m[_dt(m["event_time"]) > _dt(m["termination_date"])].copy()
    flagged["why"] = "successful login after termination_date"
    return flagged


def _vendor_bank_eq_employee_bank(c):
    if not (_has(c, "Vendor", "bank_account") and _has(c, "PayrollPayment", "bank_account")):
        return None
    emp = set(c["PayrollPayment"]["bank_account"].astype(str))
    v = c["Vendor"]
    flagged = v[v["bank_account"].astype(str).isin(emp)].copy()
    flagged["why"] = "vendor remittance account matches an employee payroll account"
    return flagged


def _self_approval_bank_change(c):
    if not (_has(c, "BankAccountChange", "identity_id", "approval_id")
            and _has(c, "Approval", "approval_id", "approver_id")):
        return None
    bac = c["BankAccountChange"].copy()
    ap = c["Approval"][["approval_id", "approver_id"]].copy()
    m = bac.merge(ap, on="approval_id", how="inner")
    flagged = m[m["identity_id"].astype(str) == m["approver_id"].astype(str)].copy()
    flagged["why"] = "approver of the bank change is its own owner"
    return flagged


def _impossible_travel(c):
    if not _has(c, "AuthEvent", "identity_id", "event_time", "geo"):
        return None
    ae = c["AuthEvent"].copy()
    ae["_t"] = _dt(ae["event_time"])
    ae = ae.sort_values(["identity_id", "_t"])
    ae["_pg"] = ae.groupby("identity_id")["geo"].shift()
    ae["_pt"] = ae.groupby("identity_id")["_t"].shift()
    gap_h = (ae["_t"] - ae["_pt"]).dt.total_seconds() / 3600.0
    flagged = ae[(ae["_pg"].notna()) & (ae["geo"].astype(str) != ae["_pg"].astype(str))
                 & (gap_h < 3)].copy()
    flagged["why"] = "two logins from different geos within 3 hours"
    return flagged.drop(columns=["_t", "_pg", "_pt"], errors="ignore")


def _dormant_reactivation(c):
    if not _has(c, "AuthEvent", "identity_id", "event_time", "outcome"):
        return None
    ae = c["AuthEvent"].copy()
    ae["_t"] = _dt(ae["event_time"])
    ae = ae.sort_values(["identity_id", "_t"])
    ae["_pt"] = ae.groupby("identity_id")["_t"].shift()
    gap_d = (ae["_t"] - ae["_pt"]).dt.total_seconds() / 86400.0
    flagged = ae[(gap_d > 180) & _is_success(ae["outcome"])].copy()
    flagged["why"] = "successful login after >180 days dormant"
    return flagged.drop(columns=["_t", "_pt"], errors="ignore")


def _priv_escalation_no_approval(c):
    if not _has(c, "AccessGrant", "grant_id", "privileged"):
        return None
    ag = c["AccessGrant"].copy()
    priv = ag[_is_privileged(ag["privileged"])]
    approved = set()
    if _has(c, "Approval", "object_id", "object_type"):
        ap = c["Approval"]
        approved = set(ap[ap["object_type"].astype(str).str.contains("access", case=False, na=False)]
                       ["object_id"].astype(str))
    flagged = priv[~priv["grant_id"].astype(str).isin(approved)].copy()
    flagged["why"] = "privileged access grant with no approval"
    return flagged


def _orphaned_privileged_access(c):
    if not (_has(c, "AccessGrant", "identity_id", "privileged") and _has(c, "Identity", "identity_id", "status")):
        return None
    ag = c["AccessGrant"].copy(); ag["identity_id"] = ag["identity_id"].astype(str)
    priv = ag[_is_privileged(ag["privileged"])]
    ident = c["Identity"][["identity_id", "status"]].copy()
    ident["identity_id"] = ident["identity_id"].astype(str)
    m = priv.merge(ident, on="identity_id", how="left")
    flagged = m[~_is_active(m["status"].fillna("missing"))].copy()
    flagged["why"] = "privileged access held by a non-active identity"
    return flagged


def _duplicate_bank_account(c):
    if not _has(c, "BankAccountChange", "new_account", "identity_id"):
        return None
    bac = c["BankAccountChange"]
    grp = bac.groupby(bac["new_account"].astype(str))["identity_id"].nunique()
    shared = set(grp[grp > 1].index)
    flagged = bac[bac["new_account"].astype(str).isin(shared)].copy()
    flagged["why"] = "destination account shared by multiple identities"
    return flagged


def _shared_payroll_account(c):
    if not _has(c, "PayrollPayment", "bank_account", "identity_id"):
        return None
    pay = c["PayrollPayment"]
    grp = pay.groupby(pay["bank_account"].astype(str))["identity_id"].nunique()
    shared = set(grp[grp > 1].index)
    flagged = pay[pay["bank_account"].astype(str).isin(shared)].copy()
    flagged["why"] = "payroll destination account shared by multiple identities"
    return flagged


def _sod_vendor_create_and_approve(c):
    if not (_has(c, "Vendor", "vendor_id", "created_by") and _has(c, "Approval", "object_id", "approver_id")):
        return None
    v = c["Vendor"].copy()
    ap = c["Approval"]
    pay_ap = ap[ap["object_type"].astype(str).str.contains("payment|vendor", case=False, na=False)] \
        if "object_type" in ap.columns else ap
    m = v.merge(pay_ap[["object_id", "approver_id"]], left_on="vendor_id", right_on="object_id", how="inner")
    flagged = m[m["created_by"].astype(str) == m["approver_id"].astype(str)].copy()
    flagged["why"] = "vendor creator also approved its payment"
    return flagged


def _vendor_created_paid_same_day(c):
    if not (_has(c, "Vendor", "vendor_id", "created_date") and _has(c, "Approval", "object_id", "decision_date")):
        return None
    v = c["Vendor"].copy()
    ap = c["Approval"]
    pay_ap = ap[ap["object_type"].astype(str).str.contains("payment|vendor", case=False, na=False)] \
        if "object_type" in ap.columns else ap
    m = v.merge(pay_ap[["object_id", "decision_date"]], left_on="vendor_id", right_on="object_id", how="inner")
    flagged = m[_dt(m["created_date"]).dt.date == _dt(m["decision_date"]).dt.date].copy()
    flagged["why"] = "vendor created and paid on the same day"
    return flagged


DETECTORS = {
    "ghost_employee": _ghost_employee,
    "terminated_still_paid": _terminated_still_paid,
    "unapproved_bank_change": _unapproved_bank_change,
    "access_after_termination": _access_after_termination,
    "login_after_termination": _login_after_termination,
    "vendor_bank_eq_employee_bank": _vendor_bank_eq_employee_bank,
    "self_approval_bank_change": _self_approval_bank_change,
    "impossible_travel": _impossible_travel,
    "dormant_reactivation": _dormant_reactivation,
    "priv_escalation_no_approval": _priv_escalation_no_approval,
    "orphaned_privileged_access": _orphaned_privileged_access,
    "duplicate_bank_account": _duplicate_bank_account,
    "shared_payroll_account": _shared_payroll_account,
    "sod_vendor_create_and_approve": _sod_vendor_create_and_approve,
    "vendor_created_paid_same_day": _vendor_created_paid_same_day,
}


def run_detections(raw_tables: dict, mapping: dict, sample_n: int = 25) -> list[dict]:
    """Run every pattern's detector that the gap analysis marked detectable.

    Returns one result per pattern, in pattern-library order:
      { pattern_id, name, acfe_category, risk_weight, status,
        ran (bool), count, sample (DataFrame), reason }
    """
    canon = materialize_canonical(raw_tables, mapping)
    gap = {r["pattern_id"]: r for r in run_all_patterns(mapping)}

    results = []
    for p in PATTERN_LIBRARY:
        pid = p["id"]
        g = gap[pid]
        base = {"pattern_id": pid, "name": p["name"], "acfe_category": p["acfe_category"],
                "risk_weight": p["risk_weight"], "status": g["status"],
                "detection_logic": p["detection_logic"]}
        if g["status"] == "not_detectable":
            results.append({**base, "ran": False, "count": 0, "sample": None,
                            "reason": f"Not detectable — missing canonical concept "
                                      f"{g.get('blocking_concept') or 'required field'}."})
            continue
        detector = DETECTORS.get(pid)
        if detector is None:
            results.append({**base, "ran": False, "count": 0, "sample": None,
                            "reason": "Detectable, but no executable detector implemented yet."})
            continue
        try:
            flagged = detector(canon)
        except Exception as e:
            results.append({**base, "ran": False, "count": 0, "sample": None,
                            "reason": f"Detector error: {type(e).__name__}: {e}"})
            continue
        if flagged is None:
            results.append({**base, "ran": False, "count": 0, "sample": None,
                            "reason": "Required canonical fields not resolvable from the mapping."})
            continue
        results.append({**base, "ran": True, "count": int(len(flagged)),
                        "sample": flagged.head(sample_n).reset_index(drop=True), "reason": ""})
    return results


def detection_summary(results: list[dict]) -> dict:
    ran = [r for r in results if r["ran"]]
    return {
        "n_patterns": len(results),
        "n_ran": len(ran),
        "n_with_findings": sum(1 for r in ran if r["count"] > 0),
        "total_anomalies": sum(r["count"] for r in ran),
        "n_skipped_not_detectable": sum(1 for r in results if r["status"] == "not_detectable"),
    }
