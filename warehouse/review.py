"""Human-in-the-loop review layer.

The AI proposes mappings; a human analyst stays in control. Every inferred
mapping (especially Low/Medium confidence) can be Accepted, Overridden, or
Rejected. Because all scoring is deterministic, the human's decisions feed
straight back into maturity + gaps + evaluation — the report recomputes from
the corrected mapping, not the raw AI guess.

Flagged gaps can also be triaged: marked as a genuine gap to fix, a false
positive, or an accepted risk — so noise can be dismissed with an audit note.

A `review` is a plain dict, easy to persist in st.session_state:
  {
    "mappings": { "Entity.field": {"decision": "accepted|overridden|rejected",
                                    "source": "TABLE.COL"(if overridden),
                                    "note": "..."} },
    "gaps":     { "pattern_id":   {"triage": "fix|false_positive|accepted_risk",
                                    "note": "..."} },
  }
No LLM. Pure, auditable state transforms.
"""

import copy

VALID_DECISIONS = {"accepted", "overridden", "rejected"}
VALID_TRIAGE = {"fix", "false_positive", "accepted_risk"}


def empty_review() -> dict:
    return {"mappings": {}, "gaps": {}}


def apply_review(ai_mapping: dict, review: dict) -> dict:
    """Return the EFFECTIVE mapping after applying human decisions.

    - accepted   -> kept, confidence promoted to High (a human vouched for it)
    - overridden -> source replaced with human-supplied table.column, conf High
    - rejected   -> removed entirely (treated as not present downstream)
    - untouched  -> left exactly as the AI proposed
    """
    eff = {k: copy.deepcopy(v) for k, v in ai_mapping.items() if k != "_raw"}
    decisions = (review or {}).get("mappings", {})

    for field, d in decisions.items():
        decision = d.get("decision")
        if decision == "rejected":
            eff.pop(field, None)
        elif decision == "accepted":
            if field in eff:
                eff[field]["confidence"] = "High"
                eff[field]["reviewed"] = "accepted"
        elif decision == "overridden":
            src = (d.get("source") or "").strip()
            if src:
                eff[field] = {
                    "source": src,
                    "confidence": "High",
                    "evidence": "Human override",
                    "value_hint": d.get("note", ""),
                    "reviewed": "overridden",
                }
    return eff


def review_summary(ai_mapping: dict, review: dict) -> dict:
    decisions = (review or {}).get("mappings", {})
    triage = (review or {}).get("gaps", {})
    n_low = sum(1 for k, v in ai_mapping.items()
                if k != "_raw" and v.get("confidence") == "Low")
    return {
        "n_mappings": len([k for k in ai_mapping if k != "_raw"]),
        "n_low_confidence": n_low,
        "n_accepted": sum(1 for d in decisions.values() if d.get("decision") == "accepted"),
        "n_overridden": sum(1 for d in decisions.values() if d.get("decision") == "overridden"),
        "n_rejected": sum(1 for d in decisions.values() if d.get("decision") == "rejected"),
        "n_reviewed": len(decisions),
        "n_false_positive": sum(1 for t in triage.values() if t.get("triage") == "false_positive"),
        "n_accepted_risk": sum(1 for t in triage.values() if t.get("triage") == "accepted_risk"),
    }


def open_gaps_after_triage(gaps: list[dict], review: dict) -> list[dict]:
    """Drop gaps a human dismissed as false positive / accepted risk."""
    triage = (review or {}).get("gaps", {})
    out = []
    for g in gaps:
        t = triage.get(g["pattern_id"], {}).get("triage")
        if t in ("false_positive", "accepted_risk"):
            continue
        out.append(g)
    return out
