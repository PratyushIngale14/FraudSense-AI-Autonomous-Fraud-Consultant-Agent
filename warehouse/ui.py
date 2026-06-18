"""Streamlit UI for the Warehouse Assurance module.

Reuses FraudSense's global CSS (sc-card, an-block, exec-block, stat-row,
section-label, risk-table, pill) and adds a few module-specific classes.

render_warehouse_module(get_client, pill) is the single entry point app.py
calls. It owns its own session_state keys (all prefixed 'wh_').
"""

from __future__ import annotations

import streamlit as st

from .warehouses import WAREHOUSES
from .discovery import discover_schema, mapping_without_meta
from .scoring import run_all_patterns, maturity_score
from .semantics import compile_semantic_layer, semantic_coverage, SEMANTIC_RELATIONSHIPS
from .evaluation import full_evaluation
from .analysis import rank_gaps, generate_remediation, build_report_text, _fallback_reco
from .review import apply_review, review_summary, open_gaps_after_triage
from .ontology import CANONICAL_ENTITIES, all_canonical_fields
from .rows import build_warehouse_rows, planted_summary
from .detect import run_detections, detection_summary, materialize_canonical
from .investigate import answer_question, NO_ANSWER
from .patterns import pattern_by_id

_CSS = """
<style>
.wh-banner { background: var(--ink); border-radius: 8px; padding: 1.6rem 2rem; margin-bottom: 1.6rem; }
.wh-banner h3 { color:#f4f3ef !important; font-family:var(--display); font-size:1.05rem; margin:0 0 .5rem; }
.wh-banner p { color:#c8c4bc; font-size:.85rem; line-height:1.7; margin:0; }
.wh-banner .accent { color: var(--accent2); }
.cbadge { font-family:var(--mono); font-size:.62rem; letter-spacing:.5px; padding:2px 7px; border-radius:2px; font-weight:500; text-transform:uppercase; }
.cb-high { background:#e6f4ee; color:#1a5c35; border:1px solid #a8d8bc; }
.cb-med  { background:#fef3e2; color:#854d00; border:1px solid #f5d898; }
.cb-low  { background:#fde8e3; color:#8b1a08; border:1px solid #f5c0b0; }
.statuschip { font-family:var(--mono); font-size:.65rem; letter-spacing:.5px; padding:2px 9px; border-radius:2px; font-weight:500; }
.sc-det { background:#e6f4ee; color:#1a5c35; border:1px solid #a8d8bc; }
.sc-par { background:#fef3e2; color:#854d00; border:1px solid #f5d898; }
.sc-not { background:#fde8e3; color:#8b1a08; border:1px solid #f5c0b0; }
.maptbl { width:100%; border-collapse:collapse; font-size:.8rem; }
.maptbl th { font-family:var(--mono); font-size:.6rem; letter-spacing:1px; text-transform:uppercase; color:var(--ink3); border-bottom:2px solid var(--ink); padding:.4rem .6rem; text-align:left; }
.maptbl td { padding:.45rem .6rem; border-bottom:1px solid var(--border); color:var(--ink2); vertical-align:top; }
.maptbl .src { font-family:var(--mono); font-size:.72rem; color:var(--ink); }
.maptbl .canon { font-family:var(--mono); font-size:.72rem; color:var(--accent); }
.maptbl tr:hover td { background:var(--surface2); }
.cmatrix { border-collapse:collapse; font-family:var(--mono); font-size:.72rem; margin:.4rem 0; }
.cmatrix th, .cmatrix td { border:1px solid var(--border2); padding:.4rem .7rem; text-align:center; }
.cmatrix th { background:var(--surface2); color:var(--ink3); font-size:.6rem; text-transform:uppercase; letter-spacing:.5px; }
.cmatrix .diag { background:#e6f4ee; color:#1a5c35; font-weight:700; }
.cmatrix .off  { color:#8b1a08; }
.bigscore { font-family:var(--display); font-size:3.2rem; font-weight:800; line-height:1; }
.viewsql { background:#1a1916; color:#c8c4bc; font-family:var(--mono); font-size:.72rem; padding:1rem 1.2rem; border-radius:6px; white-space:pre; overflow-x:auto; line-height:1.55; }
.viewsql .kw { color:#e84b18; }
</style>
"""


def _cbadge(conf: str) -> str:
    cls = {"High": "cb-high", "Medium": "cb-med", "Low": "cb-low"}.get(conf, "cb-low")
    return f'<span class="cbadge {cls}">{conf}</span>'


def _chip(status: str) -> str:
    cfg = {"detectable": ("sc-det", "Detectable"),
           "partial": ("sc-par", "Partial"),
           "not_detectable": ("sc-not", "Not Detectable")}
    cls, label = cfg.get(status, ("sc-not", status))
    return f'<span class="statuschip {cls}">{label}</span>'


# ── session helpers ───────────────────────────────────────────────────────────
def _ss():
    st.session_state.setdefault("wh_discovery", {})     # wid -> raw AI mapping
    st.session_state.setdefault("wh_remediation", {})   # wid -> {pattern_id: text}
    st.session_state.setdefault("wh_rows", {})          # wid -> {table: DataFrame}
    st.session_state.setdefault("wh_chat", {})          # chat key -> [{q, a}]


def _rows_for(wid: str) -> dict:
    if wid not in st.session_state.wh_rows:
        st.session_state.wh_rows[wid] = build_warehouse_rows(wid)
    return st.session_state.wh_rows[wid]


def _build_review(wid: str, ai_map: dict) -> dict:
    """Read HITL widget state into a review dict."""
    review = {"mappings": {}, "gaps": {}}
    for field in mapping_without_meta(ai_map):
        decision = st.session_state.get(f"rev_{wid}_{field}")
        if decision and decision != "AI proposal":
            entry = {"decision": {"Accept": "accepted", "Reject": "rejected",
                                  "Override": "overridden"}[decision]}
            if decision == "Override":
                entry["source"] = st.session_state.get(f"ovr_{wid}_{field}", "")
            review["mappings"][field] = entry
    return review


# ── discovery runner ──────────────────────────────────────────────────────────
def _run_discovery(get_client, wids: list[str]):
    client = get_client()
    if client is None:
        st.error("An Anthropic API key is required for AI schema discovery. "
                 "Add it in the sidebar — the mapping step is real and never faked.")
        return
    prog = st.progress(0)
    status = st.empty()
    for i, wid in enumerate(wids):
        wh = WAREHOUSES[wid]
        status.markdown(f"**Discovering** schema of *{wh['name']}* (Warehouse {wid}) — "
                        f"the AI has never seen this schema before…")
        try:
            mapping = discover_schema(client, wh)
        except Exception as e:
            st.error(f"Discovery failed for Warehouse {wid}: {type(e).__name__}: {e}")
            prog.empty(); status.empty()
            return
        st.session_state.wh_discovery[wid] = mapping
        # remediation wording (LLM) once, on the AI-mapping gaps
        results = run_all_patterns(mapping_without_meta(mapping))
        gaps = generate_remediation(client, wh, rank_gaps(results))
        st.session_state.wh_remediation[wid] = {g["pattern_id"]: g.get("recommendation", "") for g in gaps}
        prog.progress(int((i + 1) / len(wids) * 100))
    status.markdown("Discovery complete.")
    prog.empty(); status.empty()


# ── per-warehouse renderers ─────────────────────────────────────────────────────
def _render_schema(wh: dict):
    for table, spec in wh["profile"].items():
        with st.expander(f"{table}  ·  ~{spec['row_count']:,} rows  ·  {len(spec['columns'])} columns"):
            rows = ""
            for col, c in spec["columns"].items():
                samples = ", ".join(str(s) for s in c["samples"])
                rows += (f'<tr><td class="src">{col}</td><td>{c["dtype"]}</td>'
                         f'<td>{c["null_pct"]}%</td><td style="color:var(--ink3)">{samples}</td></tr>')
            st.markdown(f'<table class="maptbl"><thead><tr><th>Column</th><th>Type</th>'
                        f'<th>Null</th><th>Sample values</th></tr></thead><tbody>{rows}</tbody></table>',
                        unsafe_allow_html=True)


def _render_mapping(ai_map: dict):
    clean = mapping_without_meta(ai_map)
    rows = ""
    for entity in CANONICAL_ENTITIES:
        ent_fields = [f"{entity}.{fld}" for fld in CANONICAL_ENTITIES[entity]["fields"]]
        mapped = [f for f in ent_fields if f in clean]
        if not mapped:
            continue
        rows += (f'<tr><td colspan="4" style="background:var(--surface2);'
                 f'font-family:var(--display);font-weight:700;color:var(--ink);">{entity}</td></tr>')
        for f in mapped:
            e = clean[f]
            rev = e.get("reviewed")
            rev_tag = f' <span style="color:var(--green);font-size:.6rem;">✓ {rev}</span>' if rev else ""
            rows += (f'<tr><td class="canon">{f.split(".",1)[1]}{rev_tag}</td>'
                     f'<td class="src">{e["source"]}</td>'
                     f'<td>{_cbadge(e["confidence"])}</td>'
                     f'<td style="color:var(--ink3);font-size:.76rem;">{e.get("evidence","")}'
                     f'{(" · " + e["value_hint"]) if e.get("value_hint") else ""}</td></tr>')
    st.markdown(f'<table class="maptbl"><thead><tr><th>Canonical field</th>'
                f'<th>Mapped source (table.column)</th><th>Confidence</th>'
                f'<th>Evidence</th></tr></thead><tbody>{rows}</tbody></table>',
                unsafe_allow_html=True)


def _render_semantic_layer(eff_map: dict):
    layer = compile_semantic_layer(eff_map)
    cov = semantic_coverage(layer)
    st.markdown(f'<div class="data-info"><strong>Compiled semantic layer:</strong> '
                f'{cov["fields_resolved"]}/{cov["fields_total"]} canonical fields resolved '
                f'({cov["pct"]}%) · {cov["entities_materializable"]}/{cov["entities_total"]} '
                f'canonical entities materializable as views</div>', unsafe_allow_html=True)
    st.caption("Same canonical view names, different physical columns per warehouse — "
               "patterns query the views, never the raw tables.")
    entity = st.selectbox("Canonical view", list(layer.keys()), key=f"semv_{id(eff_map)}")
    sql = layer[entity]["sql"].replace("CREATE VIEW", '<span class="kw">CREATE VIEW</span>') \
                              .replace("SELECT", '<span class="kw">SELECT</span>') \
                              .replace("FROM", '<span class="kw">FROM</span>')
    st.markdown(f'<div class="viewsql">{sql}</div>', unsafe_allow_html=True)
    with st.expander("Semantic model — canonical join graph (invariant)"):
        rel = "".join(f'<tr><td class="src">{a}</td><td style="color:var(--ink3)">→</td>'
                      f'<td class="src">{b}</td><td style="font-size:.74rem;">{kind}</td></tr>'
                      for a, b, kind in SEMANTIC_RELATIONSHIPS)
        st.markdown(f'<table class="maptbl"><tbody>{rel}</tbody></table>', unsafe_allow_html=True)


def _render_maturity_and_gaps(wid: str, wh: dict, results: list, gaps: list):
    mat = maturity_score(results)
    c1, c2 = st.columns([1, 2])
    with c1:
        color = {"A": "#1a6b3c", "B": "#1a6b3c", "C": "#c05c00", "D": "#c05c00", "F": "#c8390a"}[mat["grade"]]
        st.markdown(f'<div class="bigscore" style="color:{color}">{mat["score_pct"]}%</div>'
                    f'<div class="stat-lbl">Maturity · grade {mat["grade"]}</div>'
                    f'<div style="font-family:var(--mono);font-size:.7rem;color:var(--ink3);margin-top:.6rem;">'
                    f'risk-weighted {mat["weighted_earned"]}/{mat["weighted_total"]}</div>',
                    unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="exec-block" style="padding:1.4rem 1.6rem;">'
                    f'<div class="exec-heading">Headline</div>'
                    f'<div class="exec-text">{mat["headline"]}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label" style="margin-top:1.2rem;">Pattern Coverage</div>',
                unsafe_allow_html=True)
    for r in results:
        miss = ""
        if r["status"] != "detectable" and r.get("blocking_concept"):
            miss = (f'<div class="sc-flag">missing canonical concept: '
                    f'<span style="font-family:var(--mono);color:var(--accent);">{r["blocking_concept"]}</span></div>')
        st.markdown(f'<div class="sc-card"><div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div class="sc-title" style="margin:0;">{r["name"]}</div>{_chip(r["status"])}</div>'
                    f'<div class="sc-meta" style="margin-top:.4rem;"><span>{r["acfe_category"]}</span>'
                    f'<span>risk weight {r["risk_weight"]}</span><span>coverage {int(r["coverage"]*100)}%</span></div>'
                    f'{miss}</div>', unsafe_allow_html=True)


def _render_evaluation(wid: str, eff_map: dict, wh: dict):
    ev = full_evaluation(eff_map, wh["ground_truth"])
    m, d = ev["mapping"], ev["detectability"]
    st.markdown('<div class="data-info">Evaluated against an authored ground-truth mapping '
                'for this warehouse. These numbers are computed, not asserted.</div>',
                unsafe_allow_html=True)
    cols = st.columns(4)
    for col, (label, val) in zip(cols, [("Precision", m["precision"]), ("Recall", m["recall"]),
                                        ("F1", m["f1"]), ("Mapping accuracy", m["accuracy"])]):
        col.markdown(f'<div class="stat-cell" style="border:1px solid var(--border);border-radius:6px;">'
                     f'<div class="stat-num" style="font-size:1.6rem;">{val}</div>'
                     f'<div class="stat-lbl">{label}</div></div>', unsafe_allow_html=True)

    c = m["counts"]
    st.markdown(f'<div style="font-family:var(--mono);font-size:.74rem;color:var(--ink2);margin:.8rem 0;">'
                f'correct {c["correct"]} · wrong-column {c["wrong_column"]} · missed {c["missed"]} · '
                f'false-positive {c["false_positive"]} · correct-absence {c["correct_absence"]} '
                f'(of {m["n_fields"]} canonical fields)</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label" style="margin-top:1rem;">Detectability Confusion Matrix '
                f'— verdict accuracy {d["accuracy"]}</div>', unsafe_allow_html=True)
    order = ["detectable", "partial", "not_detectable"]
    short = {"detectable": "Detect", "partial": "Partial", "not_detectable": "Not-Det"}
    head = "".join(f"<th>pred<br>{short[p]}</th>" for p in order)
    body = ""
    for t in order:
        cells = ""
        for p in order:
            v = d["matrix"][t][p]
            cls = "diag" if t == p else ("off" if v else "")
            cells += f'<td class="{cls}">{v}</td>'
        body += f'<tr><th>true {short[t]}</th>{cells}</tr>'
    st.markdown(f'<table class="cmatrix"><thead><tr><th></th>{head}</tr></thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)

    with st.expander("Per-field evaluation detail"):
        rows = ""
        for r in m["rows"]:
            bcolor = {"correct": "#1a5c35", "correct_absence": "#7a7870",
                      "wrong_column": "#8b1a08", "missed": "#854d00", "false_positive": "#8b1a08"}[r["bucket"]]
            rows += (f'<tr><td class="canon">{r["field"]}</td>'
                     f'<td class="src">{r["expected"] or "—"}</td>'
                     f'<td class="src">{r["predicted"] or "—"}</td>'
                     f'<td>{_cbadge(r["confidence"]) if r["confidence"] else ""}</td>'
                     f'<td style="color:{bcolor};font-family:var(--mono);font-size:.7rem;">{r["bucket"]}</td></tr>')
        st.markdown(f'<table class="maptbl"><thead><tr><th>Canonical field</th><th>Expected</th>'
                    f'<th>AI predicted</th><th>Conf</th><th>Result</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)


def _render_review(wid: str, ai_map: dict):
    clean = mapping_without_meta(ai_map)
    summ = review_summary(ai_map, _build_review(wid, ai_map))
    st.markdown(f'<div class="data-info">Human-in-the-loop · {summ["n_mappings"]} mappings · '
                f'{summ["n_low_confidence"]} low-confidence · reviewed {summ["n_reviewed"]} '
                f'(accept {summ["n_accepted"]}, override {summ["n_overridden"]}, reject {summ["n_rejected"]})'
                f'</div>', unsafe_allow_html=True)
    st.caption("Decisions feed straight back into the deterministic score below. "
               "Low/Medium-confidence mappings are surfaced first.")
    show_all = st.checkbox("Show all mappings (not just low/medium confidence)", key=f"showall_{wid}")
    fields = [f for f in clean if show_all or clean[f]["confidence"] in ("Low", "Medium")]
    if not fields:
        st.success("No low/medium-confidence mappings — nothing flagged for review.")
    for f in fields:
        e = clean[f]
        c1, c2, c3 = st.columns([3, 2, 3])
        with c1:
            st.markdown(f'<div style="font-family:var(--mono);font-size:.75rem;color:var(--accent);">{f}</div>'
                        f'<div class="src" style="font-size:.72rem;color:var(--ink2);">{e["source"]} '
                        f'{_cbadge(e["confidence"])}</div>', unsafe_allow_html=True)
        with c2:
            st.radio("decision", ["AI proposal", "Accept", "Override", "Reject"],
                     key=f"rev_{wid}_{f}", label_visibility="collapsed", horizontal=False)
        with c3:
            if st.session_state.get(f"rev_{wid}_{f}") == "Override":
                st.text_input("Correct source (TABLE.COLUMN)", key=f"ovr_{wid}_{f}",
                              placeholder="table.column", label_visibility="collapsed")
            else:
                st.caption(e.get("evidence", "")[:90])


def _render_remediation(wid: str, wh: dict, gaps: list):
    cache = st.session_state.wh_remediation.get(wid, {})
    if not gaps:
        st.success("No open gaps after review — every required canonical concept is present.")
        return
    for i, g in enumerate(gaps, 1):
        reco = cache.get(g["pattern_id"]) or _fallback_reco(g)
        st.markdown(f'<div class="an-block"><div class="an-label">#{i} · {g["name"]} · '
                    f'exposure {g["exposure"]} · {g["status"].replace("_"," ")}</div>'
                    f'<div class="an-content"><strong>Missing:</strong> '
                    f'<span style="font-family:var(--mono);color:var(--accent);">{g.get("blocking_concept") or "—"}</span>'
                    f'<br><strong>Remediation:</strong> {reco}</div></div>', unsafe_allow_html=True)


def _render_investigator(wid: str, pid: str, sample_df, canon: dict, get_client):
    pattern = pattern_by_id(pid)
    st.markdown('<div style="font-family:var(--mono);font-size:.65rem;color:var(--accent);'
                'letter-spacing:1px;text-transform:uppercase;margin:.6rem 0 .3rem;">'
                'Investigate a flagged record</div>', unsafe_allow_html=True)
    labels = []
    for i, row in sample_df.iterrows():
        key = row.get("identity_id") or row.get("vendor_id") or row.get("change_id") or i
        labels.append(f"Row {i} · {key}")
    pick = st.selectbox("Flagged record", labels, key=f"inv_pick_{wid}_{pid}",
                        label_visibility="collapsed")
    idx = labels.index(pick)
    signal_row = sample_df.iloc[idx].to_dict()

    chat_key = f"{wid}_{pid}_{idx}"
    history = st.session_state.wh_chat.setdefault(chat_key, [])

    st.caption(f"Ask about this {pattern['name']} signal. Answers are grounded only in this "
               f"record's actual related data — it will say \"{NO_ANSWER}\" rather than guess.")
    for turn in history:
        st.markdown(f'<div class="an-block"><div class="an-label">You asked</div>'
                    f'<div class="an-content">{turn["q"]}</div></div>', unsafe_allow_html=True)
        is_idk = turn["a"].strip().startswith(NO_ANSWER[:20])
        cls = "an-block" + (" " if is_idk else " an-quickwin")
        st.markdown(f'<div class="{cls}"><div class="an-label">Investigator</div>'
                    f'<div class="an-content">{turn["a"].replace(chr(10),"<br>")}</div></div>',
                    unsafe_allow_html=True)

    q = st.text_input("Question", key=f"inv_q_{chat_key}",
                      placeholder="e.g. Was this person terminated, and when? Who approved this?")
    c1, c2 = st.columns([1, 5])
    with c1:
        ask = st.button("Ask", key=f"inv_ask_{chat_key}")
    with c2:
        if history and st.button("Clear", key=f"inv_clear_{chat_key}"):
            st.session_state.wh_chat[chat_key] = []
            st.rerun()
    if ask and q.strip():
        with st.spinner("Reading this signal's evidence…"):
            ans = answer_question(get_client(), pattern, signal_row, canon, q.strip(), history)
        history.append({"q": q.strip(), "a": ans})
        st.rerun()


def _render_live_detection(wid: str, eff_map: dict, results: list, get_client):
    raw = _rows_for(wid)
    det = run_detections(raw, eff_map)
    canon = materialize_canonical(raw, eff_map)
    s = detection_summary(det)

    mat = maturity_score(results)
    st.markdown(f'<div class="exec-block" style="padding:1.4rem 1.6rem;">'
                f'<div class="exec-heading">Live Detection</div>'
                f'<div class="exec-text">Of the <strong>{mat["n_detectable"]}</strong> patterns your '
                f'data can detect, we ran the actual detection logic on synthetic rows and found '
                f'<strong>{s["total_anomalies"]}</strong> anomalies across '
                f'<strong>{s["n_with_findings"]}</strong> patterns. '
                f'{s["n_skipped_not_detectable"]} pattern(s) skipped — the data cannot support them.'
                f'</div></div>', unsafe_allow_html=True)
    st.caption("Detection is deterministic pandas run through the AI mapping — the same code runs on "
               "both warehouses. Planted counts are approximate ground truth; real rules can also catch "
               "emergent cases.")

    cols = st.columns(4)
    for col, (label, val) in zip(cols, [("Detectors run", s["n_ran"]),
                                        ("With findings", s["n_with_findings"]),
                                        ("Total anomalies", s["total_anomalies"]),
                                        ("Skipped (no data)", s["n_skipped_not_detectable"])]):
        col.markdown(f'<div class="stat-cell" style="border:1px solid var(--border);border-radius:6px;">'
                     f'<div class="stat-num" style="font-size:1.8rem;">{val}</div>'
                     f'<div class="stat-lbl">{label}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label" style="margin-top:1.2rem;">Detections</div>',
                unsafe_allow_html=True)
    for r in det:
        if not r["ran"]:
            st.markdown(f'<div class="sc-card" style="opacity:.7;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<div class="sc-title" style="margin:0;">{r["name"]}</div>{_chip(r["status"])}</div>'
                        f'<div class="sc-flag">{r["reason"]}</div></div>', unsafe_allow_html=True)
            continue
        found_color = "#c8390a" if r["count"] > 0 else "#1a6b3c"
        with st.expander(f"{r['name']}  —  {r['count']} found", expanded=False):
            st.markdown(f'<div class="sc-meta"><span>{r["acfe_category"]}</span>'
                        f'<span>risk weight {r["risk_weight"]}</span>'
                        f'<span style="color:{found_color};">anomalies: {r["count"]}</span></div>'
                        f'<div class="sc-flag" style="margin-top:.4rem;">logic: {r["detection_logic"]}</div>',
                        unsafe_allow_html=True)
            if r["count"] == 0:
                st.success("Detector ran cleanly — no anomalies of this type in the data.")
                continue
            st.dataframe(r["sample"], width="stretch", height=240)
            _render_investigator(wid, r["pattern_id"], r["sample"], canon, get_client)


def _render_warehouse_detail(wid: str, get_client):
    wh = WAREHOUSES[wid]
    ai_map = st.session_state.wh_discovery[wid]

    tabs = st.tabs(["Raw Schema", "AI Mapping", "Semantic Layer", "Human Review",
                    "Maturity & Gaps", "Live Detection", "Evaluation", "Remediation"])

    # Human review widgets must be created so their state is readable; we read it
    # in _build_review. Build effective mapping from current review state.
    with tabs[3]:
        _render_review(wid, ai_map)
    review = _build_review(wid, ai_map)
    eff_map = apply_review(ai_map, review)
    results = run_all_patterns(eff_map)
    gaps = open_gaps_after_triage(rank_gaps(results), review)

    with tabs[0]:
        _render_schema(wh)
    with tabs[1]:
        st.caption(f"AI-inferred mapping for {wh['name']} — every row cites its exact source and confidence.")
        _render_mapping(eff_map)
    with tabs[2]:
        _render_semantic_layer(eff_map)
    with tabs[4]:
        _render_maturity_and_gaps(wid, wh, results, gaps)
    with tabs[5]:
        _render_live_detection(wid, eff_map, results, get_client)
    with tabs[6]:
        _render_evaluation(wid, eff_map, wh)
    with tabs[7]:
        _render_remediation(wid, wh, gaps)
        report = build_report_text(wh, maturity_score(results), gaps, full_evaluation(eff_map, wh["ground_truth"]))
        st.download_button("Download Warehouse Assurance Report (.txt)", data=report,
                           file_name=f"warehouse_assurance_{wid}_{wh['name'].replace(' ','_')}.txt",
                           mime="text/plain", key=f"dl_{wid}")


def _render_comparison(wids: list[str]):
    """The wow shot: same engine, side by side, adapted to each schema."""
    st.markdown('<div class="section-label">Same Engine · Two Unseen Warehouses</div>',
                unsafe_allow_html=True)
    cols = st.columns(len(wids))
    for col, wid in zip(cols, wids):
        wh = WAREHOUSES[wid]
        ai_map = st.session_state.wh_discovery[wid]
        eff = mapping_without_meta(ai_map)
        results = run_all_patterns(eff)
        mat = maturity_score(results)
        ev = full_evaluation(eff, wh["ground_truth"])
        color = {"A": "#1a6b3c", "B": "#1a6b3c", "C": "#c05c00", "D": "#c05c00", "F": "#c8390a"}[mat["grade"]]
        with col:
            st.markdown(f'<div class="wh-banner"><h3>Warehouse {wid} · <span class="accent">{wh["name"]}</span></h3>'
                        f'<p>{wh["style"]}</p></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="bigscore" style="color:{color}">{mat["score_pct"]}%</div>'
                        f'<div class="stat-lbl">Maturity · grade {mat["grade"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="margin-top:.8rem;font-size:.85rem;color:var(--ink2);">'
                        f'<strong>{mat["n_detectable"]}</strong> detectable · '
                        f'<strong>{mat["n_partial"]}</strong> partial · '
                        f'<strong>{mat["n_not_detectable"]}</strong> not detectable</div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div style="margin-top:.4rem;font-family:var(--mono);font-size:.72rem;color:var(--ink3);">'
                        f'mapping accuracy {ev["mapping"]["accuracy"]} · '
                        f'verdict accuracy {ev["detectability"]["accuracy"]}</div>', unsafe_allow_html=True)


# ── entry point ─────────────────────────────────────────────────────────────────
def render_warehouse_module(get_client, pill):
    _ss()
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown('<div class="wh-banner"><h3>Warehouse Assurance</h3>'
                '<p>Fraud-risk <span class="accent">assessments</span> tell you what could go wrong. '
                'This reads a company\'s actual data warehouse and tells you which fraud scenarios their '
                'real data <span class="accent">can and cannot detect</span> — grounded in the schema, not interviews. '
                'A fixed canonical model + fixed pattern library; an AI layer maps each messy, unseen schema onto '
                'the model, then the same patterns run anywhere.</p></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([3, 1])
    with c1:
        choice = st.radio("Warehouse to analyse",
                          ["Both (side-by-side demo)", "Warehouse A — Helix Health (cryptic enterprise)",
                           "Warehouse B — Northwind Retail (clean HR)"],
                          horizontal=True, label_visibility="collapsed")
    with c2:
        run = st.button("Run Schema Discovery", key="wh_run")

    wids = {"Both (side-by-side demo)": ["A", "B"],
            "Warehouse A — Helix Health (cryptic enterprise)": ["A"],
            "Warehouse B — Northwind Retail (clean HR)": ["B"]}[choice]

    if run:
        _run_discovery(get_client, wids)

    ready = [w for w in wids if w in st.session_state.wh_discovery]
    if not ready:
        st.info("Pick a warehouse and click **Run Schema Discovery**. The AI maps a schema it has "
                "never seen onto the canonical model — that mapping step is always a real Claude call.")
        # show the canonical model so the page isn't empty
        with st.expander("The canonical model (invariant across every warehouse)"):
            st.markdown(f"**{len(all_canonical_fields())} canonical fields** across "
                        f"{len(CANONICAL_ENTITIES)} entities:")
            for ent, spec in CANONICAL_ENTITIES.items():
                st.markdown(f"- **{ent}** — {spec['description']}")
        return

    if len(ready) > 1:
        _render_comparison(ready)
        st.markdown("---")

    if len(ready) == 1:
        _render_warehouse_detail(ready[0], get_client)
    else:
        sub = st.tabs([f"Warehouse {w} · {WAREHOUSES[w]['name']}" for w in ready])
        for t, w in zip(sub, ready):
            with t:
                _render_warehouse_detail(w, get_client)
