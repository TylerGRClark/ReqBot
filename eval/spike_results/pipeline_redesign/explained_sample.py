#!/usr/bin/env python3
"""A seeded sample of rows where the explained text differs from the root, for the owner to rate (docs/PIPELINE_REDESIGN_PLAN.md, step 5: better or same at least 80%). Reads the newest runs
of the 13 reference documents; writes outputs/explained_rating_sheet.md. No model.

  PYTHONPATH=. python3 eval/spike_results/pipeline_redesign/explained_sample.py
"""
import collections
import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

DOCS = ["CJCSI 6510.02G", "DODI 5200.01", "DODI 5200.44", "DODI 5200.48", "DODI 8410.03", "DODI 8551.01", "NIST.SP.800-125", "afi10-2402", "afi13-550", "afi17-203", "afman17-2101", "afpd_17-1", "dafman17-1305"]
PROCESSED = Path.home() / "documents" / "processed"
SEED, N, N_FORMATTING = 4701, 30, 8  # most differences are only a list number, a dash or spacing; the sample keeps a few of those and fills the rest with rows whose words change


def formatting_only(root, explained):
    """The explained text is the root with a leading list number or dash, an inline marker and spacing tidied, nothing else."""
    from pipeline.sentence_expand import _LEADING_NUMBER, tidy
    body = root.strip()
    m = _LEADING_NUMBER.match(body)
    body = body[m.end():] if m else body
    return tidy(body).lower() == tidy(explained).lower()


def main():
    pool = []
    totals = collections.Counter()
    for doc in DOCS:
        run = Path(sorted(glob.glob(str(PROCESSED / f"{doc}_2026*")))[-1])
        for line in (run / f"{doc}_requirements_normalized.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            totals["records"] += 1
            if r.get("explained_text") and r["explained_text"].strip() != r["source_quote"].strip():
                totals["explained_differs"] += 1
                pool.append((doc, r))
    ordered = sorted(pool, key=lambda t: (t[0], t[1]["requirement_id"]))
    trivial = [t for t in ordered if formatting_only(t[1]["source_quote"], t[1]["explained_text"])]
    content = [t for t in ordered if not formatting_only(t[1]["source_quote"], t[1]["explained_text"])]
    rng = random.Random(SEED)
    picked = rng.sample(trivial, min(N_FORMATTING, len(trivial))) + rng.sample(content, min(N - N_FORMATTING, len(content)))
    picked = sorted(picked, key=lambda t: (t[0], t[1]["requirement_id"]))
    totals["formatting_only"], totals["words_differ"] = len(trivial), len(content)
    lines = [f"# Explained text against the root — {len(picked)} rows (seeded sample: {min(N_FORMATTING, len(trivial))} of {len(trivial)} where only a list number, dash or spacing differs, and {len(picked) - min(N_FORMATTING, len(trivial))} of {len(content)} where the words differ; {totals['records']} records in all)", "",
             "The **root** is exactly what requirement finding returned. The **explained text** is what a reader sees: the whole sentence, with a lead-in the source backs.",
             "Rate each: **better** (the explained text is the more useful and still says the same thing) / **same** / **worse** (it lost, added or changed meaning, or is more confusing).",
             "Pass rule (plan step 5): at least 80% better or same.", ""]
    for n, (doc, r) in enumerate(picked, 1):
        lines += [f"## {n}. {doc} — {r.get('source_ref') or '(no ref)'}", "", f"**Root:** {r['source_quote']}", "", f"**Explained:** {r['explained_text']}", "",
                  f"**What was done:** {'; '.join(r.get('explain_notes', []))}", "", "**Rating:** ", "", "---", ""]
    out = Path(__file__).resolve().parent / "outputs" / "explained_rating_sheet.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"records": totals["records"], "explained_differs": totals["explained_differs"], "formatting_only": totals["formatting_only"], "words_differ": totals["words_differ"], "sampled": len(picked)}))


if __name__ == "__main__":
    main()
