"""Remediation roadmap + board-ready report.

Ranking is DETERMINISTIC (by risk exposure that is currently un-/partially
covered). The LLM is used only to phrase the recommendation for each gap; if
no client is supplied, a deterministic fallback sentence is used so the module
runs end-to-end without an API key.
"""

from __future__ import annotations

import json
import re

from .ontology import field_description

MODEL = "claude-sonnet-4-5"

# How much risk weight a status leaves on the table.
_EXPOSURE = {"not_detectable": 1.0, "partial": 0.5, "detectable": 0.0}


def rank_gaps(pattern_results: list[dict]) -> list[dict]:
    """Deterministic ranking of gaps by un-covered risk exposure."""
    gaps = []
    for r in pattern_results:
        exposure = r["risk_weight"] * _EXPOSURE[r["status"]]
        if exposure <= 0:
            continue
        gaps.append({
            "pattern_id": r["pattern_id"],
            "name": r["name"],
            "acfe_category": r["acfe_category"],
            "status": r["status"],
            "risk_weight": r["risk_weight"],
            "exposure": round(exposure, 1),
            "blocking_concept": r.get("blocking_concept"),
            "blocking_desc": field_description(r["blocking_concept"]) if r.get("blocking_concept") else "",
            "missing": r.get("missing", []),
        })
    gaps.sort(key=lambda g: g["exposure"], reverse=True)
    return gaps


def _fallback_reco(gap: dict) -> str:
    concept = gap.get("blocking_concept") or "the required concept"
    return (f"Capture and pipeline {concept} into the warehouse. "
            f"Without it, '{gap['name']}' ({gap['acfe_category']}) cannot be "
            f"reliably detected from current data.")


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def generate_remediation(client, warehouse: dict, gaps: list[dict]) -> list[dict]:
    """Attach a specific recommendation to each (already-ranked) gap.

    LLM phrases the 'how'; ranking/exposure stay deterministic. Falls back to a
    template sentence if no client or on any error.
    """
    if not gaps:
        return gaps
    if client is None:
        for g in gaps:
            g["recommendation"] = _fallback_reco(g)
        return gaps

    gap_lines = "\n".join(
        f"{i+1}. {g['name']} | status={g['status']} | missing canonical concept: "
        f"{g.get('blocking_concept') or 'n/a'} ({g.get('blocking_desc','')})"
        for i, g in enumerate(gaps)
    )
    prompt = f"""You are a fraud-data engineering advisor. A company's warehouse
("{warehouse['name']}") was mapped onto a canonical fraud-detection model. The
following detection gaps were found, already ranked by risk exposure:

{gap_lines}

For EACH gap, write one concrete, specific remediation: the exact field, table,
or pipeline they should add to close it (e.g. "Add an approval_id foreign key on
the bank-change table sourced from the approvals workflow"). Be specific and
technical, 1-2 sentences. Do not re-rank. Do not add commentary.

Return ONLY JSON: {{"remediations": ["text for gap 1", "text for gap 2", ...]}}
in the same order as listed above."""

    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(_strip_fences(resp.content[0].text))
        recos = data.get("remediations", [])
        for i, g in enumerate(gaps):
            g["recommendation"] = recos[i] if i < len(recos) else _fallback_reco(g)
    except Exception:
        for g in gaps:
            g["recommendation"] = _fallback_reco(g)
    return gaps


def build_report_text(warehouse: dict, maturity: dict, gaps: list[dict],
                      evaluation: dict | None = None) -> str:
    """Board-ready plain-text report in FraudSense's existing output style."""
    lines = [
        "FRAUDSense AI — WAREHOUSE ASSURANCE REPORT",
        "=" * 60,
        f"Warehouse:  {warehouse['name']}",
        f"Stack:      {warehouse['style']}",
        "=" * 60, "",
        "HEADLINE",
        "-" * 40,
        maturity["headline"],
        f"Maturity score: {maturity['score_pct']}%  (grade {maturity['grade']}) — "
        f"risk-weighted {maturity['weighted_earned']}/{maturity['weighted_total']}.",
        "",
        "DETECTION GAPS — RANKED BY RISK EXPOSURE",
        "-" * 40,
    ]
    if not gaps:
        lines.append("No gaps — every canonical concept required by the pattern library is present.")
    for i, g in enumerate(gaps, 1):
        lines += [
            f"#{i}  {g['name']}  [{g['status'].replace('_',' ')}]  exposure={g['exposure']}",
            f"    ACFE: {g['acfe_category']}",
            f"    Missing concept: {g.get('blocking_concept') or 'n/a'}",
            f"    Remediation: {g.get('recommendation', _fallback_reco(g))}",
            "",
        ]
    if evaluation:
        m = evaluation["mapping"]
        d = evaluation["detectability"]
        lines += [
            "EVALUATION (vs authored ground truth)",
            "-" * 40,
            f"Mapping precision {m['precision']} | recall {m['recall']} | "
            f"F1 {m['f1']} | accuracy {m['accuracy']}",
            f"Detectability verdict accuracy: {d['accuracy']} over {d['n_patterns']} patterns.",
            "",
        ]
    return "\n".join(lines)
