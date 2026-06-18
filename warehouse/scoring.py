"""Deterministic gap analysis + maturity scoring.

NO LLM here. Given a mapping (canonical field -> source column + confidence),
this computes — by exact arithmetic — whether each pattern is detectable,
and an overall maturity score weighted by each pattern's risk exposure.

This is the trust layer: the verdict is a function of the AI's mapping, not
a second opaque judgement. Same code runs identically on any warehouse.

A `mapping` is a dict:
    { "Entity.field": {"source": "table.column", "confidence": "High|Medium|Low",
                        "evidence": "...", "reasoning": "..."}, ... }
Fields the warehouse cannot supply are simply absent from the dict.
"""

from .patterns import PATTERN_LIBRARY

_STRONG = {"High", "Medium"}
STATUS_VALUE = {"detectable": 1.0, "partial": 0.5, "not_detectable": 0.0}


def normalize_confidence(c: str) -> str:
    c = (c or "").strip().lower()
    if c in ("high", "h"):
        return "High"
    if c in ("medium", "med", "m"):
        return "Medium"
    if c in ("low", "l"):
        return "Low"
    return "Low"


def evaluate_pattern(pattern: dict, mapping: dict) -> dict:
    """Deterministic detectability verdict for one pattern given a mapping."""
    required = pattern["required_fields"]
    critical = pattern.get("critical_fields", [])

    present, missing, weak = [], [], []
    for f in required:
        if f not in mapping:
            missing.append(f)
            continue
        conf = normalize_confidence(mapping[f].get("confidence"))
        if conf in _STRONG:
            present.append(f)
        else:
            weak.append(f)  # mapped, but Low confidence => not trustworthy enough

    crit_missing = [f for f in critical if f not in mapping]
    crit_weak = [f for f in critical if f in weak]

    if crit_missing:
        status = "not_detectable"
    elif missing or weak:
        status = "partial"
    else:
        status = "detectable"

    # The single most useful "missing concept" to surface for remediation.
    if crit_missing:
        blocking = crit_missing[0]
    elif crit_weak:
        blocking = crit_weak[0]
    elif missing:
        blocking = missing[0]
    elif weak:
        blocking = weak[0]
    else:
        blocking = None

    return {
        "pattern_id": pattern["id"],
        "name": pattern["name"],
        "acfe_category": pattern["acfe_category"],
        "risk_weight": pattern["risk_weight"],
        "status": status,
        "present": present,
        "weak": weak,
        "missing": missing,
        "critical_missing": crit_missing,
        "blocking_concept": blocking,
        "coverage": round(len(present) / len(required), 2) if required else 0.0,
    }


def run_all_patterns(mapping: dict) -> list[dict]:
    return [evaluate_pattern(p, mapping) for p in PATTERN_LIBRARY]


def maturity_score(results: list[dict]) -> dict:
    """Risk-weighted maturity: sum(weight * status_value) / sum(weight)."""
    total_w = sum(r["risk_weight"] for r in results) or 1
    earned = sum(r["risk_weight"] * STATUS_VALUE[r["status"]] for r in results)
    pct = round(100 * earned / total_w, 1)

    n_det = sum(1 for r in results if r["status"] == "detectable")
    n_par = sum(1 for r in results if r["status"] == "partial")
    n_not = sum(1 for r in results if r["status"] == "not_detectable")

    if pct >= 85:
        grade = "A"
    elif pct >= 70:
        grade = "B"
    elif pct >= 55:
        grade = "C"
    elif pct >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "score_pct": pct,
        "grade": grade,
        "weighted_earned": round(earned, 1),
        "weighted_total": total_w,
        "n_total": len(results),
        "n_detectable": n_det,
        "n_partial": n_par,
        "n_not_detectable": n_not,
        "headline": f"Your warehouse data supports detection of {n_det} of {len(results)} "
                    f"fraud scenarios ({n_par} partial, {n_not} not detectable).",
    }
