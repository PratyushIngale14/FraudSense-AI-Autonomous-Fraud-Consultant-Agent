"""Deterministic self-test — runs the whole pipeline with NO API key.

    python -m warehouse._selftest

Uses each warehouse's authored ground truth as a stand-in "perfect" mapping to
exercise scoring/semantics/report, and a deliberately perturbed mapping to
exercise the evaluation + review layers.
"""

from .warehouses import WAREHOUSES
from .scoring import run_all_patterns, maturity_score
from .semantics import compile_semantic_layer, semantic_coverage
from .evaluation import full_evaluation
from .analysis import rank_gaps, generate_remediation, build_report_text
from .review import empty_review, apply_review, open_gaps_after_triage, review_summary


def lift(gt: dict) -> dict:
    """Ground-truth source strings -> scoring-shaped mapping (all High conf)."""
    return {k: {"source": v, "confidence": "High", "evidence": "ground truth", "value_hint": ""}
            for k, v in gt.items()}


def perturb(gt: dict) -> dict:
    """Simulate an imperfect AI mapping: drop 2 fields, demote some, mis-map 1."""
    m = lift(gt)
    keys = list(m.keys())
    # miss two fields entirely
    for k in keys[:2]:
        m.pop(k)
    # demote a few to Low
    for k in keys[5:8]:
        if k in m:
            m[k]["confidence"] = "Low"
    # mis-map one to a wrong column
    if "Identity.email" in m:
        m["Identity.email"]["source"] = "SOME_TABLE.WRONG_COL"
    return m


def main():
    for wid, wh in WAREHOUSES.items():
        print("=" * 70)
        print(f"WAREHOUSE {wid}: {wh['name']}  —  {wh['style']}")
        print("=" * 70)

        gt_map = lift(wh["ground_truth"])

        # 1. deterministic scoring on the (perfect) ground-truth mapping
        results = run_all_patterns(gt_map)
        mat = maturity_score(results)
        print(f"\n[scoring] {mat['headline']}")
        print(f"[scoring] maturity {mat['score_pct']}% grade {mat['grade']} "
              f"(weighted {mat['weighted_earned']}/{mat['weighted_total']})")
        for r in results:
            mark = {"detectable": "OK ", "partial": "~~ ", "not_detectable": "XX "}[r["status"]]
            extra = f"  (missing: {r['blocking_concept']})" if r["status"] != "detectable" else ""
            print(f"    {mark}{r['name']:<38}{r['status']}{extra}")

        # 2. semantic layer compile
        layer = compile_semantic_layer(gt_map)
        cov = semantic_coverage(layer)
        print(f"\n[semantics] {cov['fields_resolved']}/{cov['fields_total']} fields resolved "
              f"({cov['pct']}%), {cov['entities_materializable']}/{cov['entities_total']} entities materializable")
        print("    sample view ->")
        print("    " + layer["BankAccountChange"]["sql"].replace("\n", "\n    "))

        # 3. evaluation with a perturbed "AI" mapping vs ground truth
        ai_map = perturb(wh["ground_truth"])
        ev = full_evaluation(ai_map, wh["ground_truth"])
        m = ev["mapping"]
        print(f"\n[eval] mapping precision={m['precision']} recall={m['recall']} "
              f"f1={m['f1']} accuracy={m['accuracy']}  counts={m['counts']}")
        print(f"[eval] detectability verdict accuracy={ev['detectability']['accuracy']}")

        # 4. ranked gaps + remediation (fallback, no client) + report
        gaps = rank_gaps(results)
        gaps = generate_remediation(None, wh, gaps)
        print(f"\n[gaps] {len(gaps)} ranked gaps; top exposure:")
        for g in gaps[:3]:
            print(f"    exposure={g['exposure']:<5} {g['name']}  -> {g['recommendation'][:80]}")

        # 5. human-in-the-loop: reject a mapping, dismiss a gap, recompute
        rv = empty_review()
        # reject the first mapped field => should change downstream scoring
        first_field = next(k for k in ai_map if k != "_raw")
        rv["mappings"][first_field] = {"decision": "rejected", "note": "test reject"}
        if gaps:
            rv["gaps"][gaps[0]["pattern_id"]] = {"triage": "false_positive", "note": "noise"}
        eff = apply_review(ai_map, rv)
        eff_results = run_all_patterns(eff)
        eff_mat = maturity_score(eff_results)
        open_gaps = open_gaps_after_triage(rank_gaps(eff_results), rv)
        rs = review_summary(ai_map, rv)
        print(f"\n[hitl] after review: rejected {first_field}; maturity now {eff_mat['score_pct']}%; "
              f"open gaps {len(open_gaps)} (1 dismissed); summary={rs}")

        # 6. report text renders
        report = build_report_text(wh, mat, gaps, ev)
        assert "WAREHOUSE ASSURANCE REPORT" in report
        print(f"\n[report] {len(report)} chars OK\n")

    print("ALL DETERMINISTIC CHECKS PASSED.")


if __name__ == "__main__":
    main()
