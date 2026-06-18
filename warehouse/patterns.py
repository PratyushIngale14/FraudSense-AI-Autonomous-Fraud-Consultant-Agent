"""Canonical fraud pattern library — INVARIANT across every warehouse.

Each pattern is defined against canonical concepts (Entity.field), never
against raw tables. The same library runs on any warehouse once the AI has
mapped that warehouse onto the ontology.

Per pattern:
  id              stable slug
  name            human name
  acfe_category   ACFE fraud-tree category
  description     how the fraud works
  risk_weight     1-10 exposure weight (drives deterministic maturity scoring)
  required_fields canonical fields needed to run the detection at all
  critical_fields subset of required whose ABSENCE makes the pattern
                  fundamentally not-detectable (no proxy possible)
  detection_logic plain-language detection rule, in canonical terms
"""

PATTERN_LIBRARY = [
    {
        "id": "ghost_employee",
        "name": "Ghost Employee",
        "acfe_category": "Asset Misappropriation — Payroll",
        "description": "Payments flow to an identity that does not correspond to a real, active worker.",
        "risk_weight": 9,
        "required_fields": ["PayrollPayment.payment_id", "PayrollPayment.identity_id",
                            "Identity.identity_id", "Identity.status"],
        "critical_fields": ["PayrollPayment.identity_id", "Identity.status"],
        "detection_logic": "PayrollPayment.identity_id that has no matching active Identity "
                           "(no Identity row, or Identity.status != active).",
    },
    {
        "id": "unapproved_bank_change",
        "name": "Unapproved Bank Account Change",
        "acfe_category": "Asset Misappropriation — Payroll Diversion",
        "description": "A payee's destination bank account is changed with no approval, redirecting funds.",
        "risk_weight": 9,
        "required_fields": ["BankAccountChange.change_id", "BankAccountChange.identity_id",
                            "BankAccountChange.approval_id"],
        "critical_fields": ["BankAccountChange.approval_id"],
        "detection_logic": "BankAccountChange where approval_id is null / has no linked Approval.",
    },
    {
        "id": "terminated_still_paid",
        "name": "Terminated Employee Still Paid",
        "acfe_category": "Asset Misappropriation — Payroll",
        "description": "Payroll continues to an identity after their termination date.",
        "risk_weight": 8,
        "required_fields": ["PayrollPayment.identity_id", "PayrollPayment.pay_date",
                            "Termination.identity_id", "Termination.termination_date"],
        "critical_fields": ["PayrollPayment.pay_date", "Termination.termination_date"],
        "detection_logic": "PayrollPayment.pay_date later than the matching Termination.termination_date.",
    },
    {
        "id": "access_after_termination",
        "name": "Access Active After Termination",
        "acfe_category": "Corruption / Unauthorized Access",
        "description": "Access grants remain active for an identity after they were terminated.",
        "risk_weight": 7,
        "required_fields": ["AccessGrant.identity_id", "AccessGrant.grant_date",
                            "Termination.identity_id", "Termination.termination_date"],
        "critical_fields": ["AccessGrant.identity_id", "Termination.termination_date"],
        "detection_logic": "AccessGrant for an identity whose Termination.termination_date has passed.",
    },
    {
        "id": "login_after_termination",
        "name": "Login After Termination",
        "acfe_category": "Cyber Fraud / Unauthorized Access",
        "description": "Successful authentications occur for an identity after termination.",
        "risk_weight": 7,
        "required_fields": ["AuthEvent.identity_id", "AuthEvent.event_time", "AuthEvent.outcome",
                            "Termination.identity_id", "Termination.termination_date"],
        "critical_fields": ["AuthEvent.event_time", "Termination.termination_date"],
        "detection_logic": "Successful AuthEvent.event_time after the identity's Termination.termination_date.",
    },
    {
        "id": "vendor_bank_eq_employee_bank",
        "name": "Vendor Bank Account Matches Employee",
        "acfe_category": "Corruption — Conflict of Interest",
        "description": "A vendor's remittance account matches an employee payroll account (self-dealing / shell vendor).",
        "risk_weight": 8,
        "required_fields": ["Vendor.bank_account", "PayrollPayment.bank_account"],
        "critical_fields": ["Vendor.bank_account", "PayrollPayment.bank_account"],
        "detection_logic": "Vendor.bank_account equal to any PayrollPayment.bank_account.",
    },
    {
        "id": "self_approval_bank_change",
        "name": "Self-Approved Bank Change",
        "acfe_category": "Corruption — Override of Controls",
        "description": "The same identity who owns a bank change also approves it (broken segregation of duties).",
        "risk_weight": 7,
        "required_fields": ["BankAccountChange.identity_id", "BankAccountChange.approval_id",
                            "Approval.approver_id", "Approval.object_id"],
        "critical_fields": ["BankAccountChange.approval_id", "Approval.approver_id"],
        "detection_logic": "Approval whose approver_id equals the BankAccountChange.identity_id it covers.",
    },
    {
        "id": "impossible_travel",
        "name": "Impossible Travel / Geo Anomaly",
        "acfe_category": "Cyber Fraud — Account Takeover",
        "description": "An identity authenticates from geographically impossible locations in a short window.",
        "risk_weight": 5,
        "required_fields": ["AuthEvent.identity_id", "AuthEvent.event_time", "AuthEvent.geo"],
        "critical_fields": ["AuthEvent.geo", "AuthEvent.event_time"],
        "detection_logic": "Two AuthEvents for one identity from distant geos within an infeasible time gap.",
    },
    {
        "id": "dormant_reactivation",
        "name": "Dormant Account Reactivation",
        "acfe_category": "Cyber Fraud — Account Takeover",
        "description": "A long-dormant account suddenly authenticates successfully.",
        "risk_weight": 4,
        "required_fields": ["AuthEvent.identity_id", "AuthEvent.event_time", "AuthEvent.outcome"],
        "critical_fields": ["AuthEvent.event_time", "AuthEvent.outcome"],
        "detection_logic": "Successful AuthEvent after a long gap with no prior activity for that identity.",
    },
    {
        "id": "priv_escalation_no_approval",
        "name": "Privilege Escalation Without Approval",
        "acfe_category": "Corruption — Override of Controls",
        "description": "An admin / privileged access grant exists with no corresponding approval.",
        "risk_weight": 7,
        "required_fields": ["AccessGrant.identity_id", "AccessGrant.privileged",
                            "Approval.object_id", "Approval.object_type"],
        "critical_fields": ["AccessGrant.privileged"],
        "detection_logic": "AccessGrant.privileged = true with no matching Approval on that grant.",
    },
    {
        "id": "orphaned_privileged_access",
        "name": "Orphaned Privileged Access",
        "acfe_category": "Corruption / Unauthorized Access",
        "description": "Privileged access held by an identity that is not active.",
        "risk_weight": 6,
        "required_fields": ["AccessGrant.identity_id", "AccessGrant.privileged", "Identity.status"],
        "critical_fields": ["AccessGrant.privileged", "Identity.status"],
        "detection_logic": "AccessGrant.privileged = true for an Identity whose status is not active.",
    },
    {
        "id": "duplicate_bank_account",
        "name": "Bank Account Shared Across Identities",
        "acfe_category": "Asset Misappropriation — Payroll",
        "description": "One bank account is used as the destination for multiple distinct identities.",
        "risk_weight": 6,
        "required_fields": ["BankAccountChange.new_account", "BankAccountChange.identity_id"],
        "critical_fields": ["BankAccountChange.new_account", "BankAccountChange.identity_id"],
        "detection_logic": "Same BankAccountChange.new_account appearing for two or more identity_ids.",
    },
    {
        "id": "shared_payroll_account",
        "name": "Shared Payroll Destination Account",
        "acfe_category": "Asset Misappropriation — Payroll",
        "description": "Multiple employees are paid into the same destination account.",
        "risk_weight": 7,
        "required_fields": ["PayrollPayment.bank_account", "PayrollPayment.identity_id"],
        "critical_fields": ["PayrollPayment.bank_account", "PayrollPayment.identity_id"],
        "detection_logic": "Same PayrollPayment.bank_account for two or more distinct identities.",
    },
    {
        "id": "sod_vendor_create_and_approve",
        "name": "SoD: Vendor Creator Also Approver",
        "acfe_category": "Corruption — Segregation of Duties",
        "description": "The identity that created a vendor also approves payments/objects (no segregation).",
        "risk_weight": 6,
        "required_fields": ["Vendor.created_by", "Approval.approver_id", "Approval.object_type"],
        "critical_fields": ["Vendor.created_by", "Approval.approver_id"],
        "detection_logic": "Vendor.created_by equal to Approval.approver_id for that vendor's payments.",
    },
    {
        "id": "vendor_created_paid_same_day",
        "name": "Vendor Created and Paid Same Day",
        "acfe_category": "Asset Misappropriation — Billing",
        "description": "A vendor is created and immediately approved/paid, bypassing onboarding controls.",
        "risk_weight": 5,
        "required_fields": ["Vendor.vendor_id", "Vendor.created_date", "Approval.decision_date"],
        "critical_fields": ["Vendor.created_date"],
        "detection_logic": "Vendor.created_date equal to the decision/payment date for that vendor.",
    },
]


def pattern_by_id(pid: str) -> dict:
    for p in PATTERN_LIBRARY:
        if p["id"] == pid:
            return p
    raise KeyError(pid)


TOTAL_RISK_WEIGHT = sum(p["risk_weight"] for p in PATTERN_LIBRARY)
