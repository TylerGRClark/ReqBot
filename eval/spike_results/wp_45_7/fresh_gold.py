#!/usr/bin/env python3
"""WP-45.7e: freeze the fresh candidates' labels into a gold file in the resolver gold's own shape (offline; no LLM, no corpus needed).

Inputs, all committed: `fresh_pack/pack_a.md` (the quotes as the labeler saw them), `outputs/fresh_draw_map.json` (document, chunk, requirement id, stratum and
the production stem per card), and the labeler's two files `fresh_labels/labels_claude_a.jsonl` (pass A: complete / needs a lead-in and its text / not a
requirement) and `labels_claude_b.jsonl` (pass B: the verdict on the production stem). One labeler. The output is `outputs/fresh_gold.json`, every
candidate in the `evaluation` half of a gold that `score_resolver.py --gold` can read, plus the sufficiency check the plan requires before any run.

  python3 eval/spike_results/wp_45_7/fresh_gold.py            # writes outputs/fresh_gold.json (refuses to overwrite)
  python3 eval/spike_results/wp_45_7/fresh_gold.py --check    # the committed gold must be the sealed file (sha256 fixed in the plan), and equal the recomputed one
"""

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
PACK = _HERE / "fresh_pack"
LABELS = _HERE / "fresh_labels"
KEY = _HERE / "outputs" / "fresh_draw_map.json"
PLAN = _HERE.parents[2] / "docs" / "PHASE45_WP457E_PLAN.md"
SPENT = _HERE / "outputs" / "resolver_gold.json"
FROZEN = _HERE / "outputs" / "fresh_gold.json"
MIN_REAL, MIN_NON_REQUIREMENTS, MIN_ATTACHMENT_SCORED = 80, 8, 60  # docs/PHASE45_WP457E_PLAN.md section 2
STANDALONE = {"complete", "needs_lead_in", "not_a_requirement"}


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _jsonl(path):
    out = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            rec = json.loads(line)
            if rec["id"] in out:
                raise SystemExit(f"{path} line {n}: {rec['id']} appears twice")
            out[rec["id"]] = rec
    return out


def parse_pack_a(text):
    """{card id: {"quote": the quote text, "card": the whole card normalized}} from pack_a.md."""
    cards = {}
    for m in re.finditer(r"^## (R\d{3})\n(.*?)(?=^## R\d{3}\n|\Z)", text, flags=re.M | re.S):
        body = m.group(2)
        q = re.search(r"Quote \(the requirement text to judge\):\n((?:> ?.*\n?)+)", body)
        quote = "\n".join(line[2:] if line.startswith("> ") else line[1:] for line in q.group(1).rstrip("\n").split("\n"))
        cards[m.group(1)] = {"quote": quote, "card": norm(body)}
    return cards


def rubric_problems(pack, labels):
    """The audit's own label checker (copied byte for byte into the pack folder) run on both passes: every card labeled once, only allowed values, a lead-in
    text exactly when the rubric asks for one, a verdict only for cards with a stem. A list of problems, empty when the labels follow the rubric."""
    spec = importlib.util.spec_from_file_location("fresh_pack_check_labels", Path(pack) / "check_labels.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check(pack, Path(labels) / "labels_claude_a.jsonl", Path(labels) / "labels_claude_b.jsonl")


def build(pack=PACK, labels=LABELS, key_path=KEY, spent_path=SPENT):
    for path in (labels / "labels_claude_a.jsonl", labels / "labels_claude_b.jsonl"):
        if not path.exists():
            raise SystemExit(f"{path} does not exist: the fresh labels are sealed outside the repository until stage C2 of docs/PHASE45_WP457E_PLAN.md commits them")
    problems = rubric_problems(pack, labels)
    if problems:
        raise SystemExit("the labels do not follow the rubric: " + "; ".join(problems[:8]))
    key = json.loads(key_path.read_text(encoding="utf-8"))["items"]
    cards = parse_pack_a((pack / "pack_a.md").read_text(encoding="utf-8"))
    a, b = _jsonl(labels / "labels_claude_a.jsonl"), _jsonl(labels / "labels_claude_b.jsonl")
    if set(cards) != set(key) or set(a) != set(key):
        raise SystemExit("the pack, the key and the pass A labels do not list the same cards")
    spent = json.loads(spent_path.read_text(encoding="utf-8"))["gold"]
    spent_quotes = {(g["document"], norm(g["quote"]).lower()) for g in spent}
    gold = []
    for rid in sorted(key):
        item, la = key[rid], a[rid]
        if la["standalone"] not in STANDALONE:
            raise SystemExit(f"{rid}: bad standalone {la['standalone']!r}")
        stem = item.get("stem") or None
        if bool(stem) != (rid in b):
            raise SystemExit(f"{rid}: a pass B verdict must exist exactly for the cards that have a production stem")
        text = la.get("lead_in_text")
        if la["standalone"] == "needs_lead_in" and text:  # every passage of a lead-in must be in the card, as shown (whitespace aside)
            for piece in re.split(r"\s*\|\s*", text):
                for part in re.split(r"\s*\.\.\.\s*", piece):
                    if part.strip() and norm(part) not in cards[rid]["card"]:
                        raise SystemExit(f"{rid}: lead-in passage {part[:60]!r} is not in the card")
        if (item["document"], norm(cards[rid]["quote"]).lower()) in spent_quotes:
            raise SystemExit(f"{rid}: the quote duplicates a spent gold record")
        gold.append({
            "candidate_id": f"fresh:{rid}", "set": "audit", "half": "evaluation", "document": item["document"], "chunk_id": int(item["chunk_id"]),
            "requirement_id": item["requirement_id"], "quote": cards[rid]["quote"], "stratum": item["stratum"],
            "standalone": la["standalone"], "lead_in_location": la.get("lead_in_location"), "lead_in_text": la.get("lead_in_text"),
            "production_stem": stem, "stem_verdict": b[rid]["stem_verdict"] if rid in b else None,
        })
    real = sum(g["standalone"] in ("complete", "needs_lead_in") for g in gold)
    non = sum(g["standalone"] == "not_a_requirement" for g in gold)
    scored = sum(not (g["standalone"] == "not_a_requirement" or (g["standalone"] == "needs_lead_in" and not g["lead_in_text"])) for g in gold)
    counts = {"candidates": len(gold), "real": real, "non_requirements": non, "attachment_scored": scored,
              **{k: sum(g["standalone"] == k for g in gold) for k in sorted(STANDALONE)},
              "needs_lead_in_not_shown": sum(g["standalone"] == "needs_lead_in" and not g["lead_in_text"] for g in gold),
              "with_production_stem": sum(1 for g in gold if g["production_stem"]),
              "stem_verdicts": {v: sum(g["stem_verdict"] == v for g in gold) for v in sorted({g["stem_verdict"] for g in gold if g["stem_verdict"]})}}
    sufficient = real >= MIN_REAL and non >= MIN_NON_REQUIREMENTS and scored >= MIN_ATTACHMENT_SCORED
    return {
        "plan": "docs/PHASE45_WP457E_PLAN.md", "labeler": "claude (one labeler; the audit's two labelers and adjudication are not available here)",
        "sufficiency": {"required": {"real": MIN_REAL, "non_requirements": MIN_NON_REQUIREMENTS, "attachment_scored": MIN_ATTACHMENT_SCORED}, "met": sufficient},
        "counts": counts,
        "inputs_sha256": {p.name if p.parent.name != "outputs" else f"outputs/{p.name}": _sha(p) for p in (
            pack / "pack_a.md", pack / "pack_b.md", key_path, labels / "labels_claude_a.jsonl", labels / "labels_claude_b.jsonl")},
        "gold": gold,
    }


def expected_hashes(plan=PLAN):
    """{file name: sha256} fixed in the plan for the two label files and the frozen gold (section 2, "Sealing and order")."""
    text = Path(plan).read_text(encoding="utf-8")
    out = {}
    for name in ("labels_claude_a.jsonl", "labels_claude_b.jsonl", "fresh_gold.json"):
        m = re.search(rf"`{re.escape(name)}`\s+`([0-9a-f]{{64}})`", text)
        if not m:
            raise SystemExit(f"the plan does not fix a hash for {name}")
        out[name] = m.group(1)
    return out


def verify_sealed(labels, gold_text, plan=PLAN):
    """Stop unless the label files and the frozen gold are exactly the sealed ones whose hashes the plan fixed. Raises SystemExit naming every mismatch."""
    want = expected_hashes(plan)
    have = {"labels_claude_a.jsonl": _sha(Path(labels) / "labels_claude_a.jsonl"), "labels_claude_b.jsonl": _sha(Path(labels) / "labels_claude_b.jsonl"),
            "fresh_gold.json": hashlib.sha256(gold_text.encode("utf-8")).hexdigest()}
    bad = [f"{n}: plan {want[n][:12]}..., got {have[n][:12]}..." for n in want if have[n] != want[n]]
    if bad:
        raise SystemExit("the labels or the gold are not the sealed ones the plan fixed, so the one-shot protocol stops here: " + "; ".join(bad))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    data = build()
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        if not FROZEN.exists():
            sys.exit("there is no committed fresh gold to check")
        frozen_text = FROZEN.read_text(encoding="utf-8")
        verify_sealed(LABELS, frozen_text)  # the committed bytes and the label files are the sealed ones the plan fixed
        same = frozen_text == text
        print("the committed fresh gold is the sealed file and equals the recomputed one" if same else "DIFFERENT from the recomputed gold")
        sys.exit(0 if same else 1)
    verify_sealed(LABELS, text)  # before anything is written
    if not data["sufficiency"]["met"]:
        sys.exit(f"the fresh set is not sufficient ({data['counts']}); the plan stops here, nothing is frozen")
    if FROZEN.exists():
        sys.exit("the fresh gold is frozen; use --check")
    FROZEN.write_text(text, encoding="utf-8")
    print(json.dumps({k: data[k] for k in ("sufficiency", "counts")}, indent=1))


if __name__ == "__main__":
    main()
