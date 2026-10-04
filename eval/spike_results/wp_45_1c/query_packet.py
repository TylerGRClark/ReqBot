"""WP-45.1(c)/(d): build the packet the query writer works from (read-only; no LLM, no Qdrant, no retrieval).

One card per eligible record, in a seeded shuffle, under opaque ids P001..., with:
  the document, the heading path, the verbatim quote, and, only where Tyler's rulings say the quote needs one,
  the adjudicated lead-in text (so the writer sees the record's full intended meaning).
The card never shows the attached stem, the stem verdict or the group, and the packet carries no retrieval output.
The id mapping is written to a separate file (`--map-out`) that the writer does not open until the queries are frozen.

Run from the repo root:  python3 eval/spike_results/wp_45_1c/query_packet.py
"""

import argparse
import ast
import hashlib
import json
import random
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SEED = "wp45.1c/queries"


def shuffled_ids(rids, seed=SEED):
    """Opaque packet ids in a seeded shuffle: P001 is not the first record, and nothing in an id reveals a group."""
    order = sorted(rids)
    random.Random(seed).shuffle(order)
    return {f"P{i:03d}": rid for i, rid in enumerate(order, 1)}


def heading_path(rec):
    path = rec.get("section_title_path") or []
    if isinstance(path, str):
        path = ast.literal_eval(path)
    return [str(p).strip() for p in path if str(p).strip()]


def card(pid, rec, group_rec):
    lines = [f"## {pid}", "", f"Document: {group_rec['document']}"]
    path = heading_path(rec)
    lines.append("Heading path: " + (" > ".join(path) if path else "(none)"))
    lines.append("")
    lines.append("Quote (verbatim):")
    lines.append("> " + " ".join(rec["source_quote"].split()))
    if group_rec["standalone"] == "needs_lead_in" and (group_rec["lead_in_text"] or "").strip():
        lines += [
            "",
            "Lead-in this quote needs to be complete (from the adjudication):",
            "> " + group_rec["lead_in_text"],
        ]
    elif group_rec["standalone"] == "needs_lead_in":
        lines += [
            "",
            "This quote needs a lead-in that was not visible in the source shown; no text is available.",
        ]
    return "\n".join(lines)


def load_normalized(documents):
    from _inputs import corpus_inputs

    inputs = corpus_inputs("normalized")
    by_id = {}
    for doc, files in inputs.items():
        if doc not in documents:
            continue
        with open(files["normalized"], encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    by_id[r["requirement_id"]] = r
    return by_id


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--groups", default=str(_HERE / "groups.json"))
    ap.add_argument("--out", default=str(_HERE / "query_packet.md"))
    ap.add_argument("--map-out", default=str(_HERE / "query_ids.json"))
    args = ap.parse_args()
    groups = json.loads(Path(args.groups).read_text(encoding="utf-8"))
    recs = groups["records"]
    by_id = load_normalized({v["document"] for v in recs.values()})
    mapping = shuffled_ids(groups["eligible"])
    cards = []
    for pid, rid in mapping.items():
        rq = recs[rid]["requirement_id"]
        if rq not in by_id:
            sys.exit(f"{rid} ({rq}) is not in the pinned normalized files")
        cards.append(card(pid, by_id[rq], recs[rid]))
    Path(args.out).write_text(
        "# Query-writing packet\n\n" + "\n\n".join(cards) + "\n", encoding="utf-8"
    )
    Path(args.map_out).write_text(
        json.dumps({"seed": SEED, "ids": mapping}, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(Path(args.out).read_bytes()).hexdigest()
    print(f"{len(cards)} cards -> {args.out} (sha256 {digest[:12]}...); id map -> {args.map_out}")


if __name__ == "__main__":
    main()
