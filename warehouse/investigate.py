"""Per-signal investigator chat — grounded, no hallucination.

An analyst looking at a specific flagged signal can ask free-form questions
about it. We assemble an EVIDENCE PACK from the actual canonical rows related
to that signal (the identity, their payroll / bank changes / access / auth /
terminations, the vendor, who shares the account, related approvals) and pass
ONLY that to Claude with strict instructions: answer solely from the evidence,
and if the answer is not in it, say so verbatim. No outside knowledge, no
guessing.

The LLM here is a reader over real rows — the detection itself is still pure
deterministic pandas upstream.
"""

from __future__ import annotations

import pandas as pd

MODEL = "claude-sonnet-4-5"
NO_ANSWER = "I don't have the data to answer that."
_ROW_CAP = 25


def _norm(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def _rows_for(df, col, value, cap=_ROW_CAP):
    if df is None or col not in df.columns or value is None:
        return None
    sub = df[df[col].astype(str) == str(value)]
    return sub.head(cap) if len(sub) else None


def build_evidence_pack(signal_row: dict, pattern: dict, canon: dict) -> str:
    """Assemble the focused, factual evidence for one flagged signal as text."""
    parts = []
    sig = {k: _norm(v) for k, v in signal_row.items() if not str(k).startswith("_")}

    parts.append("FLAGGED SIGNAL (the record under investigation):")
    parts.append("\n".join(f"  {k} = {v}" for k, v in sig.items() if v is not None))

    ident_id = sig.get("identity_id")
    vendor_id = sig.get("vendor_id")
    accounts = [sig.get("bank_account"), sig.get("new_account"), sig.get("old_account")]
    accounts = [a for a in accounts if a]

    def add(title, df):
        if df is not None and len(df):
            parts.append(f"\n{title}:")
            parts.append(df.to_string(index=False, max_rows=_ROW_CAP))

    if ident_id:
        add("Identity record", _rows_for(canon.get("Identity"), "identity_id", ident_id))
        add("Termination record(s) for this identity",
            _rows_for(canon.get("Termination"), "identity_id", ident_id))
        add("Payroll payments to this identity",
            _rows_for(canon.get("PayrollPayment"), "identity_id", ident_id))
        add("Bank account changes by this identity",
            _rows_for(canon.get("BankAccountChange"), "identity_id", ident_id))
        add("Access grants for this identity",
            _rows_for(canon.get("AccessGrant"), "identity_id", ident_id))
        add("Recent auth events for this identity",
            _rows_for(canon.get("AuthEvent"), "identity_id", ident_id))
        add("Approvals made BY this identity (as approver)",
            _rows_for(canon.get("Approval"), "approver_id", ident_id))

    if vendor_id:
        add("Vendor record", _rows_for(canon.get("Vendor"), "vendor_id", vendor_id))
        add("Approvals referencing this vendor",
            _rows_for(canon.get("Approval"), "object_id", vendor_id))

    for acct in accounts:
        add(f"Payroll payments into account {acct}",
            _rows_for(canon.get("PayrollPayment"), "bank_account", acct))
        add(f"Vendors using account {acct}",
            _rows_for(canon.get("Vendor"), "bank_account", acct))

    return "\n".join(parts)


def answer_question(client, pattern: dict, signal_row: dict, canon: dict,
                    question: str, history: list[dict] | None = None) -> str:
    """Answer a question about one signal, grounded only in its evidence pack."""
    if client is None:
        return "An Anthropic API key is required to use the investigator."
    evidence = build_evidence_pack(signal_row, pattern, canon)
    convo = ""
    for turn in (history or [])[-4:]:
        convo += f"\nPreviously asked: {turn['q']}\nYou answered: {turn['a']}\n"

    prompt = f"""You are a fraud investigation assistant helping an analyst understand ONE
flagged signal. You must answer using ONLY the EVIDENCE below — it is the actual
data for this signal pulled from the warehouse. Hard rules:

- Use only facts present in the EVIDENCE. Do not use outside knowledge.
- Do not guess, estimate, or infer beyond what the data states.
- If the evidence does not contain what's needed to answer, reply EXACTLY:
  "{NO_ANSWER}"
- Be concise. Cite the specific values (ids, dates, amounts) you used.

PATTERN THAT FLAGGED THIS SIGNAL: {pattern['name']} ({pattern['acfe_category']})
DETECTION LOGIC: {pattern['detection_logic']}
WHY THIS ROW WAS FLAGGED: {signal_row.get('why', 'n/a')}

EVIDENCE
========
{evidence}
========
{convo}
ANALYST QUESTION: {question}

Answer:"""

    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"Investigator error: {type(e).__name__}: {e}"
