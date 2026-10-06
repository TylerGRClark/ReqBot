#!/usr/bin/env python3
"""WP-45.7: the resolver's gold sets on the development side, split into frozen selection and evaluation halves (offline; no LLM).

Two sets of already-labeled records, both with their quote and chunk recovered from the pinned (or WP-45.6 scratch) pipeline files:

- **audit**: the 130 WP-45.1(b) attachment-audit records. Tyler's adjudicated answer per record: complete, needs a lead-in (with the
  lead-in text and where it is) or not a requirement; and, for the 66 records production attached a stem to, a verdict on that
  stem (right, wrong_sibling, fragment_chain, not_needed, wrong_other). The production stem is the paired baseline.
- **cards**: the 90 WP-45.6 disagreement cards (records only the 8B kept, only the 14B kept, or both), labeled real requirement or
  not by two labelers. Only the cards on which the two labelers agree are gold; the rest are listed as disputed and not scored.

Each candidate falls into the **selection** or the **evaluation** half by a seeded hash of its id, frozen in the manifest before any
run. The resolver tier and model are chosen from the selection halves (and the dev pages) only; the evaluation halves are scored once,
after that choice is frozen, together with the held-out labels (plan 4.4). The split is by candidate id, so it is fixed forever.

  python3 eval/spike_results/wp_45_7/resolver_gold.py            # writes outputs/resolver_gold.json (refuses to overwrite)
  python3 eval/spike_results/wp_45_7/resolver_gold.py --check    # recompute and compare
  python3 eval/spike_results/wp_45_7/resolver_gold.py --candidates-out DIR   # selection.jsonl / evaluation.jsonl for run_resolver.py
"""

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _inputs  # noqa: E402
import score_audit as SA  # noqa: E402  (WP-45.1(b): label loading and Tyler's adjudication, reused unchanged)

SPLIT_SEED = "wp45.7/resolver-gold"
FROZEN = _HERE / "outputs" / "resolver_gold.json"
AUDIT_DIR = _ROOT / "eval/spike_results/wp_45_1/audit_results"
CARD_KEY = _ROOT / "eval/spike_results/wp_45_6/outputs/pack_answers.json"
CARD_LABELS = _ROOT / "eval/spike_results/wp_45_6/labels"
SCRATCH = Path.home() / "wp45_6_scratch"
SIDE_TAG = {"base": "8b_current_stepD", "new": "qwen2.5_14b"}
REQUIREMENT_LABELS = ("complete", "needs_lead_in")  # the two "this is a requirement" labels of the audit rubric


def half(candidate_id, seed=SPLIT_SEED):
    """'selection' or 'evaluation', by a seeded hash of the candidate id."""
    return "selection" if int(hashlib.sha256(f"{seed}/{candidate_id}".encode()).hexdigest(), 16) % 2 == 0 else "evaluation"


def _normalized(document, run_dir=None):
    path = (Path(run_dir) if run_dir else None)
    if path is None:
        path = _inputs.corpus_inputs("normalized")[document]["normalized"]
    return {r["requirement_id"]: r for r in (json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip())}


def audit_gold():
    """[gold dict] for the 130 audit records: quote, chunk, adjudicated standalone verdict, lead-in, stem verdict, production stem."""
    key = json.loads((AUDIT_DIR / "answer_key.json").read_text(encoding="utf-8"))
    args = types.SimpleNamespace(key=str(AUDIT_DIR / "answer_key.json"), labels_dir=str(AUDIT_DIR))
    _, labels = SA.load(args)
    a_pairs, b_pairs, dis_a, dis_b = SA.disagreements(key, labels)
    spot = SA.spot_check_items(a_pairs, b_pairs, dis_a, dis_b)
    answers = SA.parse_answers(AUDIT_DIR / "adjudication.txt")
    ra, rb, unresolved, _, _ = SA.resolve(a_pairs, b_pairs, dis_a, dis_b, spot, answers)
    if unresolved:
        raise SystemExit(f"unresolved audit disagreements: {unresolved}")
    docs = {d: _normalized(d) for d in sorted({v["document"] for v in key["items"].values()})}
    out = []
    for rid in sorted(key["items"]):
        item = key["items"][rid]
        rec = docs[item["document"]][item["requirement_id"]]
        standalone, location, text = ra[rid]
        out.append({
            "candidate_id": f"audit:{rid}", "set": "audit", "document": item["document"], "chunk_id": int(item["chunk_id"]),
            "requirement_id": item["requirement_id"], "quote": rec["source_quote"], "stratum": item["stratum"],
            "standalone": standalone, "lead_in_location": location, "lead_in_text": text,
            "production_stem": item.get("stem") or None, "stem_verdict": rb.get(rid),
        })
    return out


def card_gold():
    """([gold dict], [disputed ids]) for the WP-45.6 cards on which both labelers agree about real requirement or not."""
    key = json.loads(CARD_KEY.read_text(encoding="utf-8"))
    labels = {
        who: {r["id"]: r for r in (json.loads(x) for x in (CARD_LABELS / f"labels_{who}_a.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
        for who in ("claude", "codex")
    }
    cache, out, disputed = {}, [], []
    for rid in sorted(key["items"]):
        item = key["items"][rid]
        real = {who: labels[who][rid]["standalone"] in REQUIREMENT_LABELS for who in labels}
        if real["claude"] != real["codex"]:
            disputed.append(f"card:{rid}")
            continue
        run_dir = SCRATCH / SIDE_TAG[item["side"]] / item["document"]
        if (run_dir, "n") not in cache:
            cache[(run_dir, "n")] = _normalized(item["document"], run_dir / f"{item['document']}_requirements_normalized.jsonl")
        rec = cache[(run_dir, "n")][item["requirement_id"]]
        out.append({
            "candidate_id": f"card:{rid}", "set": "cards", "document": item["document"], "chunk_id": int(rec["chunk_id"]),
            "requirement_id": item["requirement_id"], "quote": rec["source_quote"], "origin": item["set"],
            "real_requirement": real["claude"],
        })
    return out, disputed


def build():
    audit = audit_gold()
    cards, disputed = card_gold()
    gold = audit + cards
    for g in gold:
        g["half"] = half(g["candidate_id"])
    return {
        "split_seed": SPLIT_SEED,
        "counts": {
            "audit": len(audit), "cards": len(cards), "cards_disputed": len(disputed),
            **{f"{s}_{h}": sum(1 for g in gold if g["set"] == s and g["half"] == h) for s in ("audit", "cards") for h in ("selection", "evaluation")},
        },
        "disputed_cards": disputed,
        "gold": gold,
    }


def candidates(data, which):
    """run_resolver.py candidate rows for one half."""
    return [
        {"candidate_id": g["candidate_id"], "document": g["document"], "chunk_id": g["chunk_id"], "quote": g["quote"]}
        for g in data["gold"] if g["half"] == which
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--candidates-out", metavar="DIR")
    args = ap.parse_args()
    if args.candidates_out:
        data = json.loads(FROZEN.read_text(encoding="utf-8"))
        out = Path(args.candidates_out)
        out.mkdir(parents=True, exist_ok=True)
        for which in ("selection", "evaluation"):
            rows = candidates(data, which)
            (out / f"{which}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            print(f"{which}: {len(rows)} candidates")
        return
    text = json.dumps(build(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if args.check:
        if FROZEN.read_text(encoding="utf-8") != text:
            sys.exit("the recomputed gold differs from the frozen file")
        print("resolver gold verified")
        return
    if FROZEN.exists():
        sys.exit(f"{FROZEN} already exists; the split is frozen. Use --check.")
    FROZEN.write_text(text, encoding="utf-8")
    print(json.dumps(json.loads(text)["counts"], indent=1))


if __name__ == "__main__":
    main()
