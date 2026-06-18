"""Semantic layer.

The canonical ontology is the SEMANTIC MODEL (universal business concepts,
decoupled from any physical schema). This module makes that explicit and
turns it into something concrete and demoable:

  1. SEMANTIC_RELATIONSHIPS — the join graph between canonical entities
     (Identity 1:N PayrollPayment, etc.). This is the invariant semantic model.

  2. compile_semantic_layer(mapping) — binds the discovered mapping to the
     model and emits per-warehouse CANONICAL VIEWS: deterministic
     `SELECT raw_col AS canonical_field FROM raw_table` definitions. This is
     the "compiled" semantic layer — the same canonical view names resolve to
     totally different physical columns in Warehouse A vs B, yet every fraud
     pattern queries the canonical names only.

So: ontology = semantic model (fixed), mapping = the binding the AI infers,
compiled views = the materialized semantic layer for THIS warehouse. Patterns
run against the views, never the raw tables. Pure data/string work, no LLM.
"""

from .ontology import CANONICAL_ENTITIES
from .scoring import normalize_confidence

# Invariant join graph over canonical entities (semantic model relationships).
SEMANTIC_RELATIONSHIPS = [
    ("PayrollPayment.identity_id", "Identity.identity_id",      "many-to-one"),
    ("BankAccountChange.identity_id", "Identity.identity_id",   "many-to-one"),
    ("AccessGrant.identity_id", "Identity.identity_id",         "many-to-one"),
    ("AuthEvent.identity_id", "Identity.identity_id",           "many-to-one"),
    ("Termination.identity_id", "Identity.identity_id",         "one-to-one"),
    ("Approval.object_id", "BankAccountChange.change_id",       "one-to-one (when object_type=bank_change)"),
    ("Approval.approver_id", "Identity.identity_id",            "many-to-one"),
    ("Vendor.created_by", "Identity.identity_id",               "many-to-one"),
    ("AccessGrant.granted_by", "Identity.identity_id",          "many-to-one"),
    ("Identity.manager_id", "Identity.identity_id",             "many-to-one (self)"),
]


def _split(source: str):
    if source and "." in source:
        t, c = source.split(".", 1)
        return t, c
    return None, None


def compile_semantic_layer(mapping: dict) -> dict:
    """Produce, per canonical entity, a resolved view definition from the mapping.

    Returns:
      { "Identity": {
            "table": "WD_WORKER_DIM" | None,
            "columns": [ {canonical_field, source_table, source_column, confidence}, ... ],
            "sql": "CREATE VIEW canonical_identity AS SELECT ... FROM ...",
            "complete": bool,        # all entity fields resolved
            "n_fields": int, "n_resolved": int,
        }, ... }
    """
    layer = {}
    for entity, spec in CANONICAL_ENTITIES.items():
        cols, tables = [], {}
        for field in spec["fields"]:
            dotted = f"{entity}.{field}"
            entry = mapping.get(dotted)
            if not entry or not entry.get("source"):
                continue
            t, c = _split(entry["source"])
            if not t:
                continue
            cols.append({
                "canonical_field": field,
                "source_table": t,
                "source_column": c,
                "confidence": normalize_confidence(entry.get("confidence")),
            })
            tables[t] = tables.get(t, 0) + 1

        base_table = max(tables, key=tables.get) if tables else None
        n_fields = len(spec["fields"])

        if cols and base_table:
            select_lines = ",\n    ".join(
                f"{c['source_column']} AS {c['canonical_field']}"
                + (f"   -- from {c['source_table']}" if c["source_table"] != base_table else "")
                for c in cols
            )
            sql = (f"CREATE VIEW canonical_{entity.lower()} AS\n"
                   f"SELECT\n    {select_lines}\nFROM {base_table};")
        else:
            sql = f"-- canonical_{entity.lower()}: NOT MATERIALIZABLE (no source columns mapped)"

        layer[entity] = {
            "table": base_table,
            "columns": cols,
            "sql": sql,
            "complete": len(cols) == n_fields,
            "n_fields": n_fields,
            "n_resolved": len(cols),
        }
    return layer


def semantic_coverage(layer: dict) -> dict:
    total = sum(v["n_fields"] for v in layer.values())
    resolved = sum(v["n_resolved"] for v in layer.values())
    materializable = sum(1 for v in layer.values() if v["table"])
    return {
        "fields_total": total,
        "fields_resolved": resolved,
        "pct": round(100 * resolved / total, 1) if total else 0.0,
        "entities_materializable": materializable,
        "entities_total": len(layer),
    }
