"""WP-45.6: build the blind labeling pack for the extraction-model comparison (read-only; no LLM, no Qdrant).

Draws, once and with a seeded shuffle, a sample of the records that only the new model found, only the 8B found, and both found,
pooled across the documents, and writes ONE pass A pack in the WP-45.1(b) card format (the quote, its chunk with the quote marked,
the previous chunk). Cards carry no model name and no stem, and ids are assigned after a shuffle so nothing reveals the set.
The WP-45.1(b) rubric and checker are reused unchanged. The answer key (id -> set, document, model, requirement id) is written ONLY
to --key-out, outside the pack.

Each set is the first n of its own seeded shuffle, so the sample can be extended later without a redraw.

Run from the repo root (after compare.py has produced the overlap files):
  python3 eval/spike_results/wp_45_6/pack.py --new qwen2.5_14b --out-dir PACK_DIR --key-out PATH_OUTSIDE_PACK/key.json
"""

import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import audit_pack as AP  # noqa: E402  (card format and quote marking, reused unchanged)

SEED = "wp45.6"
SAMPLE = {"new_only": 40, "base_only": 40, "both": 20}
DEFAULT_SCRATCH = Path.home() / "wp45_6_scratch"
BASELINE_TAG = "8b_current_stepD"
RUBRIC_DIR = _ROOT / "eval/spike_results/wp_45_1/audit_pack"
DOCS = ("DODI 8410.03", "afman17-2101", "NIST.SP.800-125")


def read_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def frames(new_tag, scratch, docs=DOCS):
    """{set: [(document, side, requirement_id)]} from each document's comparison file."""
    out = {"new_only": [], "base_only": [], "both": []}
    for doc in docs:
        cmp_path = _HERE / "outputs" / f"comparison_{doc}_{new_tag}.json"
        ids = json.loads(cmp_path.read_text(encoding="utf-8"))["overlap_ids"]
        out["new_only"] += [(doc, "new", r) for r in ids["new_only"]]
        out["base_only"] += [(doc, "base", r) for r in ids["base_only"]]
        out["both"] += [
            (doc, "new", r) for r in ids["new_matched"]
        ]  # the matched records of the new model's side
    return out


def draw(frame, sample=SAMPLE, seed=SEED):
    """First n of a seeded shuffle of each set (sets smaller than n are taken whole)."""
    chosen = {}
    for name, items in frame.items():
        order = sorted(items)
        random.Random(f"{seed}/{name}").shuffle(order)
        chosen[name] = order[: sample[name]]
    return chosen


def assign_ids(chosen, seed=SEED):
    """R001... over the pooled sample after a shuffle, so an id says nothing about its set or document."""
    pooled = [(name, item) for name, items in chosen.items() for item in items]
    pooled.sort(key=lambda x: (x[0], x[1]))
    random.Random(f"{seed}/ids").shuffle(pooled)
    return {
        f"R{i:03d}": {"set": name, "document": it[0], "side": it[1], "requirement_id": it[2]}
        for i, (name, it) in enumerate(pooled, 1)
    }


def card_rows(assigned, new_tag, scratch):
    cache, rows = {}, []
    for rid, a in assigned.items():
        tag = new_tag if a["side"] == "new" else BASELINE_TAG
        d = Path(scratch) / tag / a["document"]
        if (tag, a["document"]) not in cache:
            norm = {
                r["requirement_id"]: r
                for r in read_jsonl(d / f"{a['document']}_requirements_normalized.jsonl")
            }
            chunks = {c["chunk_id"]: c for c in read_jsonl(d / f"{a['document']}_chunks.jsonl")}
            cache[(tag, a["document"])] = (norm, chunks)
        norm, chunks = cache[(tag, a["document"])]
        rec = norm[a["requirement_id"]]
        cid = rec["chunk_id"]
        rows.append(
            {
                "id": rid,
                "document": a["document"],
                "chunk_id": cid,
                "chunk": chunks[cid],
                "prev_chunk": chunks.get(cid - 1) if cid is not None else None,
                "quote": (rec.get("source_quote") or "").strip(),
            }
        )
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--new", required=True, help="scratch tag of the new model, e.g. qwen2.5_14b")
    ap.add_argument("--scratch", default=str(DEFAULT_SCRATCH))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--key-out", required=True)
    ap.add_argument("--manifest-out")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    if Path(args.key_out).resolve().is_relative_to(out_dir.resolve()):
        sys.exit("--key-out must be outside --out-dir so the pack stays blind")

    frame = frames(args.new, args.scratch)
    chosen = draw(frame)
    assigned = assign_ids(chosen)
    rows = card_rows(assigned, args.new, args.scratch)
    pack = (
        "# Extraction-model comparison, pass A only: source text only\n\n"
        "Read RUBRIC.md first (it is the WP-45.1(b) rubric, unchanged). Label pass A only; there is no pass B and no stem "
        "in this pack. Cards are in random order and carry no model name.\n\n"
        + "\n".join(AP.card_a(r) for r in sorted(rows, key=lambda r: r["id"]))
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ("RUBRIC.md", "check_labels.py"):
        shutil.copy2(RUBRIC_DIR / name, out_dir / name)
    (out_dir / "pack_a.md").write_text(pack, encoding="utf-8")
    key = {
        "seed": SEED,
        "sample": SAMPLE,
        "frame": {k: len(v) for k, v in frame.items()},
        "drawn": {k: len(v) for k, v in chosen.items()},
        "items": assigned,
    }
    Path(args.key_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.key_out).write_text(
        json.dumps(key, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    hashes = {
        n: hashlib.sha256((out_dir / n).read_bytes()).hexdigest()
        for n in ("pack_a.md", "RUBRIC.md", "check_labels.py")
    }
    hashes["answers"] = hashlib.sha256(Path(args.key_out).read_bytes()).hexdigest()
    print(json.dumps({"frame": key["frame"], "drawn": key["drawn"], "sha256": hashes}, indent=1))
    if args.manifest_out:
        Path(args.manifest_out).write_text(
            json.dumps(
                {
                    "seed": SEED,
                    "sample": SAMPLE,
                    "frame": key["frame"],
                    "drawn": key["drawn"],
                    "sha256": hashes,
                },
                indent=1,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
