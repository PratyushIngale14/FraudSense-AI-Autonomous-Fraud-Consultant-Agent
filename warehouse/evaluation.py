"""Evaluation layer — measures how accurate the AI's mapping actually is.

Because the synthetic warehouses ship with an authored ground-truth mapping,
we can score the discovery agent objectively and show the numbers in the UI.
Two evaluations:

  1. MAPPING accuracy  — per canonical field, did the AI map it to the right
     source column? Buckets: correct, wrong_column, missed, false_positive,
     correct_absence. Yields precision / recall / F1 / accuracy.

  2. DETECTABILITY accuracy — does the engine's pattern verdict (run on the AI
     mapping) match the verdict run on the ground-truth mapping? Yields a
     3x3 confusion matrix over detectable / partial / not_detectable.

All deterministic. No LLM.
"""

from __future__ import annotations

from .ontology import all_canonical_fields
from .scoring import run_all_patterns, normalize_confidence

STATUSES = ["detectable", "partial", "not_detectable"]


def _source_of(entry) -> str | None:
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry
    return entry.get("source")


def evaluate_mapping(ai_mapping: dict, ground_truth: dict) -> dict:
    """Compare AI mapping against ground truth, field by field."""
    fields = all_canonical_fields()
    rows = []
    counts = {"correct": 0, "wrong_column": 0, "missed": 0,
              "false_positive": 0, "correct_absence": 0}
    # confidence calibration: how confident was the AI on right vs wrong calls
    calib = {"High": {"right": 0, "wrong": 0},
             "Medium": {"right": 0, "wrong": 0},
             "Low": {"right": 0, "wrong": 0}}

    for f in fields:
        gt_src = _source_of(ground_truth.get(f))
        ai_entry = ai_mapping.get(f)
        ai_src = _source_of(ai_entry)
        conf = normalize_confidence(ai_entry.get("confidence")) if isinstance(ai_entry, dict) else None

        if gt_src and ai_src:
            if gt_src.lower() == ai_src.lower():
                bucket = "correct"
            else:
                bucket = "wrong_column"
        elif gt_src and not ai_src:
            bucket = "missed"
        elif not gt_src and ai_src:
            bucket = "false_positive"
        else:
            bucket = "correct_absence"

        counts[bucket] += 1
        if conf and bucket in ("correct", "wrong_column", "false_positive"):
            calib[conf]["right" if bucket == "correct" else "wrong"] += 1

        rows.append({
            "field": f, "expected": gt_src, "predicted": ai_src,
            "confidence": conf, "bucket": bucket,
        })

    correct = counts["correct"]
    tp_denom_p = correct + counts["wrong_column"] + counts["false_positive"]
    tp_denom_r = correct + counts["wrong_column"] + counts["missed"]
    precision = round(correct / tp_denom_p, 3) if tp_denom_p else 1.0
    recall = round(correct / tp_denom_r, 3) if tp_denom_r else 1.0
    f1 = round(2 * precision * recall / (precision + recall), 3) if (precision + recall) else 0.0
    accuracy = round((correct + counts["correct_absence"]) / len(fields), 3)

    return {
        "rows": rows,
        "counts": counts,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "calibration": calib,
        "n_fields": len(fields),
    }


def evaluate_detectability(ai_mapping: dict, ground_truth: dict) -> dict:
    """Compare pattern verdicts on AI mapping vs ground-truth mapping."""
    # ground truth mapping is "source string" form; lift to the scoring shape
    gt_lifted = {k: {"source": _source_of(v), "confidence": "High"}
                 for k, v in ground_truth.items()}

    ai_results = {r["pattern_id"]: r for r in run_all_patterns(ai_mapping)}
    gt_results = {r["pattern_id"]: r for r in run_all_patterns(gt_lifted)}

    matrix = {t: {p: 0 for p in STATUSES} for t in STATUSES}  # matrix[true][pred]
    rows, agree = [], 0
    for pid, gt in gt_results.items():
        true_s = gt["status"]
        pred_s = ai_results[pid]["status"]
        matrix[true_s][pred_s] += 1
        if true_s == pred_s:
            agree += 1
        rows.append({"pattern_id": pid, "name": gt["name"],
                     "true": true_s, "predicted": pred_s, "match": true_s == pred_s})

    n = len(gt_results)
    return {
        "matrix": matrix,
        "rows": rows,
        "accuracy": round(agree / n, 3) if n else 1.0,
        "n_patterns": n,
    }


def full_evaluation(ai_mapping: dict, ground_truth: dict) -> dict:
    return {
        "mapping": evaluate_mapping(ai_mapping, ground_truth),
        "detectability": evaluate_detectability(ai_mapping, ground_truth),
    }
