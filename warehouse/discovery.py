"""AI Schema Discovery agent — the magic, and it is always real.

Input:  a warehouse schema profile (table/column names, sample values, null
        rates, row counts) + the canonical ontology.
Output: a mapping of raw columns -> canonical concepts, each with a confidence
        (High/Med/Low), the exact source table.column cited, and the evidence
        the model used.

The model infers meaning from cryptic names + sample values
(e.g. WKR_TYPE_C='CspLitePortal' -> Identity.role='external portal user').
Where it is not sure, it must label Low confidence; where there is no
evidence at all, it must OMIT the field rather than guess. Never fabricate.

Follows the existing FraudSense agent convention: build prompt -> messages.create
-> strip code fences -> json.loads.
"""

import json
import re

from .ontology import ontology_for_prompt, all_canonical_fields
from .warehouses import profile_for_prompt
from .scoring import normalize_confidence

MODEL = "claude-sonnet-4-5"


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def build_discovery_prompt(warehouse: dict) -> str:
    return f"""You are a data-warehouse schema discovery agent for a fraud-analytics platform.

You are given the schema profile of a warehouse you have NEVER seen before. Column
and table names may be cryptic, abbreviated, vendor-specific, or misleading. You must
map the RAW columns onto a fixed CANONICAL ontology used by fraud-detection patterns.

# CANONICAL ONTOLOGY (the only target names allowed)
{ontology_for_prompt()}

# WAREHOUSE SCHEMA PROFILE (raw — infer meaning from names, dtypes, sample values)
{profile_for_prompt(warehouse)}

# YOUR TASK
For each canonical field you can support, emit ONE mapping object. Rules:
- Cite the EXACT source as "TABLE.COLUMN" using names exactly as they appear above.
- confidence: "High" (name + samples clearly match), "Medium" (plausible but inferred),
  "Low" (a guess worth flagging for human review).
- If there is NO column that could represent a canonical field, OMIT it entirely.
  Do NOT invent a source. Omitting is correct and expected — many warehouses lack
  concepts (e.g. an approval link on a bank change, or a privileged-access flag).
- Use sample values as evidence. E.g. a column whose values are SUCCESS/FAILURE is an
  auth outcome; values like 'A'/'T'/'LOA' are an employment status.
- "evidence": the specific sample values or naming clue that justified the mapping.
- "value_hint": for enumerated fields (role/status/outcome), briefly note what the raw
  codes appear to mean (e.g. "CspLitePortal => external portal user"). Else "".

Return ONLY a JSON object of this exact shape, no markdown, no preamble:
{{
  "mappings": [
    {{
      "canonical": "Entity.field",
      "source": "TABLE.COLUMN",
      "confidence": "High|Medium|Low",
      "evidence": "...",
      "value_hint": "..."
    }}
  ]
}}
Only use canonical names from the ontology above. Cite real columns only."""


def discover_schema(client, warehouse: dict) -> dict:
    """Run the discovery agent. Returns a mapping dict keyed by 'Entity.field':
        { "Entity.field": {source, confidence, evidence, value_hint}, ... }
    Plus a parallel list under key '_raw' for display/debugging.
    """
    prompt = build_discovery_prompt(warehouse)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = _strip_fences(resp.content[0].text)
    data = json.loads(raw)
    return normalize_discovery(data.get("mappings", []))


def normalize_discovery(mappings: list[dict]) -> dict:
    """Validate + fold the agent's list into the canonical mapping dict.

    Drops any mapping that targets a canonical field outside the ontology.
    Keeps the highest-confidence entry if a field is mapped more than once.
    """
    valid_fields = set(all_canonical_fields())
    rank = {"High": 3, "Medium": 2, "Low": 1}
    out: dict[str, dict] = {}
    raw_kept = []
    for m in mappings:
        canon = (m.get("canonical") or "").strip()
        src = (m.get("source") or "").strip()
        if canon not in valid_fields or not src:
            continue
        entry = {
            "source": src,
            "confidence": normalize_confidence(m.get("confidence")),
            "evidence": (m.get("evidence") or "").strip(),
            "value_hint": (m.get("value_hint") or "").strip(),
        }
        raw_kept.append({"canonical": canon, **entry})
        prev = out.get(canon)
        if prev is None or rank[entry["confidence"]] > rank[prev["confidence"]]:
            out[canon] = entry
    out["_raw"] = raw_kept
    return out


def mapping_without_meta(mapping: dict) -> dict:
    """Strip the '_raw' helper key for clean iteration."""
    return {k: v for k, v in mapping.items() if k != "_raw"}
