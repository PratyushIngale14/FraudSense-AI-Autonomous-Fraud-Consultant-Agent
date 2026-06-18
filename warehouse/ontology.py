"""Canonical fraud-detection ontology — INVARIANT across every warehouse.

Every company's warehouse schema is different and undocumented, but the
underlying concepts fraud detection needs are universal. This file is that
universal layer: ~8 canonical entities with the exact fields the pattern
library relies on. The AI Schema Discovery agent maps each raw, cryptic
schema onto THESE names; everything downstream is defined against them.

Plain data only — no logic, no LLM. This is the contract.
"""

CANONICAL_ENTITIES = {
    "Identity": {
        "description": "A person or service account the company knows about — "
                       "employee, contractor, external portal user, or system account.",
        "key": "identity_id",
        "fields": {
            "identity_id":  "Unique id for the person/account.",
            "role":         "Worker type or role (e.g. full-time employee, contractor, external clinician).",
            "status":       "Active / terminated / leave / disabled.",
            "email":        "Primary email or login.",
            "department":   "Org unit / cost centre.",
            "manager_id":   "identity_id of this person's manager (for SoD checks).",
        },
    },
    "PayrollPayment": {
        "description": "A disbursement of pay/compensation to an identity.",
        "key": "payment_id",
        "fields": {
            "payment_id":   "Unique id for the pay line / disbursement.",
            "identity_id":  "Who was paid (links to Identity).",
            "amount":       "Gross or net amount paid.",
            "pay_date":     "Date the payment was made.",
            "bank_account": "Destination bank account (number, token, or mask).",
        },
    },
    "BankAccountChange": {
        "description": "An event in which a payee's destination bank account was changed.",
        "key": "change_id",
        "fields": {
            "change_id":    "Unique id for the change event.",
            "identity_id":  "Whose account was changed.",
            "old_account":  "Previous bank account.",
            "new_account":  "New bank account.",
            "change_date":  "When the change took effect.",
            "approval_id":  "Link/reference to an approval of this change (null => unapproved).",
        },
    },
    "AccessGrant": {
        "description": "A grant of access to a system, application, or privilege.",
        "key": "grant_id",
        "fields": {
            "grant_id":     "Unique id for the access grant.",
            "identity_id":  "Who received access.",
            "resource":     "App / system / entitlement granted.",
            "grant_date":   "When access was granted.",
            "granted_by":   "identity_id of who granted it.",
            "privileged":   "Whether this is an admin / high-privilege grant.",
        },
    },
    "AuthEvent": {
        "description": "An authentication / login event.",
        "key": "event_id",
        "fields": {
            "event_id":    "Unique id for the auth event.",
            "identity_id": "Who authenticated.",
            "event_time":  "Timestamp of the event.",
            "outcome":     "Success / failure / denied.",
            "ip_address":  "Source IP.",
            "geo":         "Geographic location / country of the event.",
        },
    },
    "Termination": {
        "description": "A record that an identity was terminated / offboarded.",
        "key": "identity_id",
        "fields": {
            "identity_id":      "Who was terminated.",
            "termination_date": "Effective last day.",
            "reason":           "Reason / termination code.",
        },
    },
    "Vendor": {
        "description": "A supplier / payee organisation the company pays.",
        "key": "vendor_id",
        "fields": {
            "vendor_id":    "Unique id for the vendor.",
            "name":         "Vendor name.",
            "bank_account": "Vendor remittance bank account.",
            "address":      "Vendor address.",
            "created_date": "When the vendor record was created.",
            "created_by":   "identity_id of who created the vendor record.",
        },
    },
    "Approval": {
        "description": "A discrete approval decision on some business object "
                       "(payment, requisition, bank change, access request, etc.).",
        "key": "approval_id",
        "fields": {
            "approval_id":   "Unique id for the approval.",
            "approver_id":   "identity_id of the approver.",
            "object_type":   "What kind of object was approved.",
            "object_id":     "Id of the approved object.",
            "decision":      "Approved / rejected.",
            "decision_date": "When the decision was made.",
        },
    },
}


def all_canonical_fields() -> list[str]:
    """Flat list of every 'Entity.field' the ontology defines."""
    out = []
    for entity, spec in CANONICAL_ENTITIES.items():
        for field in spec["fields"]:
            out.append(f"{entity}.{field}")
    return out


def field_description(dotted: str) -> str:
    entity, field = dotted.split(".", 1)
    return CANONICAL_ENTITIES.get(entity, {}).get("fields", {}).get(field, "")


def ontology_for_prompt() -> str:
    """Render the ontology as compact text for the discovery agent's prompt."""
    lines = []
    for entity, spec in CANONICAL_ENTITIES.items():
        lines.append(f"{entity} — {spec['description']}")
        for field, desc in spec["fields"].items():
            lines.append(f"    {entity}.{field}: {desc}")
    return "\n".join(lines)
