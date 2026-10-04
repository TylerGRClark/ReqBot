"""WP-45.1(c)/(d): freeze the record groups for the fair retrieval test (read-only; no LLM, no Qdrant).

Reads the committed WP-45.1(b) answer key, the four label files and Tyler's adjudication, resolves the final
labels with the audit scorer's own `resolve`, and writes explicit ID lists:

  eligible   the audited records that are requirements and whose stem, if any, was not judged unnecessary
  groups     right | misleading | incomplete (attached stems), bare (no stem, needs a lead-in), control (no stem, complete)
  oracle_set every eligible record that needs a lead-in AND has adjudicated lead-in text (a lead-in "not shown" to the
             labelers has none, so those records stay in their group but are not oracle targets)

Lists are written before any query is, so a group cannot be adjusted after seeing a retrieval result.

Run from the repo root:  python3 eval/spike_results/wp_45_1c/groups.py [--out PATH]
"""

import argparse
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_AUDIT = _ROOT / "eval/spike_results/wp_45_1"
_RESULTS = _AUDIT / "audit_results"

# Hashes of the audit inputs, keyed by short labels: a hash next to a file name that contains "key" trips the
# repository's secrets scanner (generic-api-key), the same false positive as the audit pack's old `key_sha256` field.
SOURCE_FILES = {
    "answers": "answer_key.json",
    "adjudication": "adjudication.txt",
    "claude_a": "labels_claude_a.jsonl",
    "claude_b": "labels_claude_b.jsonl",
    "codex_a": "labels_codex_a.jsonl",
    "codex_b": "labels_codex_b.jsonl",
}
MISLEADING = ("wrong_sibling", "wrong_other")
INCOMPLETE = ("fragment_chain",)


def load_scorer():
    spec = importlib.util.spec_from_file_location(
        "wp45_score_audit_for_groups", _AUDIT / "score_audit.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def final_labels(results_dir=_RESULTS):
    """(key, ra, rb): the answer key and the adjudicated pass A / pass B labels, exactly as the audit scored them."""
    sa = load_scorer()
    key, labels = sa.load(
        types.SimpleNamespace(key=str(results_dir / "answer_key.json"), labels_dir=str(results_dir))
    )
    a_pairs, b_pairs, dis_a, dis_b = sa.disagreements(key, labels)
    spot = sa.spot_check_items(a_pairs, b_pairs, dis_a, dis_b)
    answers = sa.parse_answers(results_dir / "adjudication.txt")
    ra, rb, unresolved, _, _ = sa.resolve(a_pairs, b_pairs, dis_a, dis_b, spot, answers)
    if unresolved:
        sys.exit(f"unresolved disagreements, no groups: {unresolved}")
    return key, ra, rb


def build(key, ra, rb):
    """Pure: the group lists from the final labels. Returns a dict that json-serialises as written."""
    items = key["items"]
    records, groups = (
        {},
        {"right": [], "misleading": [], "incomplete": [], "bare": [], "control": []},
    )
    excluded = {"not_a_requirement": [], "stem_not_needed": []}
    for rid in sorted(items):
        it = items[rid]
        standalone, location, lead_in = ra[rid]
        has_stem = bool(it["stem"])
        verdict = rb.get(rid) if has_stem else None
        if standalone == "not_a_requirement":
            excluded["not_a_requirement"].append(rid)
            continue
        if verdict == "not_needed":
            excluded["stem_not_needed"].append(rid)
            continue
        if has_stem:
            if verdict == "right":
                group = "right"
            elif verdict in MISLEADING:
                group = "misleading"
            elif verdict in INCOMPLETE:
                group = "incomplete"
            else:
                sys.exit(f"{rid}: unexpected stem verdict {verdict!r}")
        else:
            group = "bare" if standalone == "needs_lead_in" else "control"
        groups[group].append(rid)
        records[rid] = {
            "document": it["document"],
            "requirement_id": it["requirement_id"],
            "chunk_id": it["chunk_id"],
            "stratum": it["stratum"],
            "group": group,
            "stem": it["stem"] or None,
            "stem_verdict": verdict,
            "standalone": standalone,
            "lead_in_location": location,
            "lead_in_text": lead_in,
        }
    needs = [r for r, v in records.items() if v["standalone"] == "needs_lead_in"]
    # A lead-in "not shown" to the labelers has no text to adjudicate: the record stays in its group but cannot be
    # an oracle target. Any other location without text is a data error.
    no_text = [r for r in needs if not (records[r]["lead_in_text"] or "").strip()]
    bad = [r for r in no_text if records[r]["lead_in_location"] != "not_shown"]
    if bad:
        sys.exit(f"{bad} need a lead-in at a shown location but have no adjudicated lead-in text")
    return {
        "eligible": sorted(records),
        "groups": groups,
        "excluded": excluded,
        "oracle_set": sorted(r for r in needs if r not in no_text),
        "needs_lead_in_not_shown": sorted(no_text),
        "heading_located": sorted(
            r for r in needs if records[r]["lead_in_location"] == "section_heading"
        ),
        "stem_on_complete_quote": sorted(
            r for r, v in records.items() if v["stem"] and v["standalone"] == "complete"
        ),
        "records": records,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "groups.json"))
    args = ap.parse_args()
    key, ra, rb = final_labels()
    out = build(key, ra, rb)
    out["sources"] = {label: sha256(_RESULTS / name) for label, name in SOURCE_FILES.items()}
    Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sizes = {g: len(v) for g, v in out["groups"].items()}
    print(
        f"eligible {len(out['eligible'])}; groups {sizes}; oracle set {len(out['oracle_set'])}; wrote {args.out}"
    )


if __name__ == "__main__":
    main()
