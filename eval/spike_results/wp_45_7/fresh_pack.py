#!/usr/bin/env python3
"""WP-45.7e: draw the fresh candidates and write the blind labeling pack (read-only; no LLM, no Qdrant).

The fresh set is the NEXT records of the WP-45.1(b) attachment audit's own seeded per-stratum shuffles (`audit_pack.py`: the audit took the
first n of each shuffle "so it can be extended later without a redraw"), so none of them was in the audit. Records whose document and quote
text equal those of a record of the spent gold (the 220 audit and card candidates of `resolver_gold.json`) are skipped and the next record of
the stratum takes their place: the corpus holds duplicated sentences. Cards use the audit's own format (`audit_pack.card_a`, `card_b`); ids are
R201 upward so they cannot be confused with the audit's R001-R130 and the audit's label checker applies unchanged.

  python3 eval/spike_results/wp_45_7/fresh_pack.py --check     # recompute the draw and compare it with outputs/fresh_draw_map.json
  python3 eval/spike_results/wp_45_7/fresh_pack.py             # writes fresh_pack/pack_a.md, pack_b.md, outputs/fresh_draw_map.json (refuses to overwrite)

Pass A of the labeling uses pack_a.md only; the key (strata, production stems) is in outputs/ and is not opened until pass A is saved.
"""

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import audit_pack as AP  # noqa: E402
import bundle as B  # noqa: E402
from _inputs import corpus_inputs  # noqa: E402
from core.profiles import default_profile  # noqa: E402

PACK_DIR = _HERE / "fresh_pack"
KEY = _HERE / "outputs" / "fresh_draw_map.json"
MANIFEST = _HERE / "outputs" / "fresh_pack_manifest.json"
GOLD = _HERE / "outputs" / "resolver_gold.json"
AUDIT_PACK_DIR = _ROOT / "eval/spike_results/wp_45_1/audit_pack"
ORDER_SEED = "wp45.7e/order"
# How many fresh records per stratum (docs/PHASE45_WP457E_PLAN.md section 2); the `heading` stratum has two records and both were used.
EXTRA = {"same-chunk": 30, "cross-chunk": 28, "heading": 0, "none+signal": 28, "none+nosignal": 12,
         "not-a-candidate+signal": 8, "not-a-candidate+nosignal": 8}
FIRST_ID = 201


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spent_quotes():
    """{(document, normalized quote)} of every spent gold candidate (the audit's and the cards')."""
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["gold"]
    return {(g["document"], B.normalize(g["quote"]).lower()) for g in gold}


def draw(rows, excluded, spent):
    """The fresh records, in id order. Per stratum: the audit's own frame and shuffle, skip the audit's first n, then take EXTRA records that are
    not duplicates of a spent record. Raises SystemExit if a stratum cannot supply them."""
    frames = {s: [] for s in AP.POPULATION}
    for r in rows:
        if r["stratum"] not in frames:
            sys.exit(f"unexpected stratum {r['stratum']!r}")
        frames[r["stratum"]].append(r)
    if {s: len(v) for s, v in frames.items()} != AP.POPULATION:
        sys.exit("stratum populations changed: the audit's frame is no longer the one this extension continues")
    chosen, skipped = [], {}
    for stratum, frame in frames.items():
        frame = sorted((r for r in frame if r["index"] not in excluded), key=lambda r: r["index"])
        random.Random(f"{AP.SEED}/{stratum}").shuffle(frame)
        later, skipped[stratum] = frame[AP.SAMPLE[stratum]:], 0
        take = []
        for r in later:
            if len(take) == EXTRA[stratum]:
                break
            if (r["document"], B.normalize(r["quote"]).lower()) in spent:
                skipped[stratum] += 1
                continue
            take.append(r)
        if len(take) != EXTRA[stratum]:
            sys.exit(f"stratum {stratum} has only {len(take)} fresh eligible records for {EXTRA[stratum]}")
        chosen.extend(take)
    random.Random(ORDER_SEED).shuffle(chosen)
    for n, r in enumerate(chosen, FIRST_ID):
        r["id"] = f"R{n:03d}"
    return sorted(chosen, key=lambda r: r["id"]), skipped


def build():
    inputs = corpus_inputs("chunks", "extracted", "normalized")
    verbs = default_profile()["obligation_verbs"]
    verb_re = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in verbs) + r")\b", re.IGNORECASE)
    rows = AP.load_rows(inputs, verb_re)
    excluded = AP.prior_sample_indexes(rows)
    AP.check_prior_sample(rows, excluded)
    chosen, skipped = draw(rows, excluded, spent_quotes())
    AP.require_chunks(chosen)
    # no fresh record may be one of the audit's own first-n records (the same shuffle, an earlier slice)
    audit_taken = set()
    for stratum in AP.POPULATION:
        frame = sorted((r for r in rows if r["stratum"] == stratum and r["index"] not in excluded), key=lambda r: r["index"])
        random.Random(f"{AP.SEED}/{stratum}").shuffle(frame)
        audit_taken |= {r["index"] for r in frame[: AP.SAMPLE[stratum]]}
    if audit_taken & {r["index"] for r in chosen}:
        sys.exit("a fresh record is one of the audit's own: the extension logic is wrong")
    return chosen, skipped, audit_taken


def texts(chosen):
    pack_a = ("# Fresh candidates, pass A: source text only\n\nRead RUBRIC.md first. Cards are in random order. "
              "Do not open pack_b.md until every card here is labeled.\n\n" + "\n".join(AP.card_a(r) for r in chosen))
    attached = [r for r in chosen if r["stem"]]
    pack_b = ("# Fresh candidates, pass B: the stem the pipeline attached\n\nOnly records that received a stem appear here. Judge each stem against "
              "its quote (RUBRIC.md, pass B). pack_a.md has the surrounding text.\n\n" + "\n".join(AP.card_b(r) for r in attached))
    key = {
        "seed": f"{AP.SEED} (extension), order {ORDER_SEED}", "extra": EXTRA, "first_id": FIRST_ID,
        "items": {r["id"]: {"document": r["document"], "requirement_id": r["requirement_id"], "chunk_id": r["chunk_id"], "index": r["index"],
                            "stratum": r["stratum"], "method": r["method"], "stem": r["stem"]} for r in chosen},
    }
    return pack_a, pack_b, json.dumps(key, indent=2, ensure_ascii=False) + "\n", len(attached)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="recompute the draw and compare it with the committed pack and key")
    args = ap.parse_args()
    chosen, skipped, audit_taken = build()
    pack_a, pack_b, key, n_stem = texts(chosen)
    if args.check:
        same = (_sha(PACK_DIR / "pack_a.md") == hashlib.sha256(pack_a.encode()).hexdigest()
                and _sha(PACK_DIR / "pack_b.md") == hashlib.sha256(pack_b.encode()).hexdigest()
                and _sha(KEY) == hashlib.sha256(key.encode()).hexdigest())
        print("draw reproduces the committed pack and key" if same else "DIFFERENT from the committed pack or key")
        sys.exit(0 if same else 1)
    if KEY.exists() or (PACK_DIR / "pack_a.md").exists():
        sys.exit("the fresh draw already exists; it is frozen (use --check)")
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("RUBRIC.md", "check_labels.py"):
        shutil.copyfile(AUDIT_PACK_DIR / name, PACK_DIR / name)
    (PACK_DIR / "pack_a.md").write_text(pack_a, encoding="utf-8")
    (PACK_DIR / "pack_b.md").write_text(pack_b, encoding="utf-8")
    KEY.write_text(key, encoding="utf-8")
    by = {}
    for r in chosen:
        by[r["stratum"]] = by.get(r["stratum"], 0) + 1
    manifest = {
        "script": "eval/spike_results/wp_45_7/fresh_pack.py", "plan": "docs/PHASE45_WP457E_PLAN.md",
        "drawn": len(chosen), "pass_b_cards": n_stem, "by_stratum": by, "skipped_as_duplicates_of_spent_gold": skipped,
        "audit_records_excluded_as_the_audit_took_them": len(audit_taken),
        "file_sha256": {"pack_a.md": _sha(PACK_DIR / "pack_a.md"), "pack_b.md": _sha(PACK_DIR / "pack_b.md"), "RUBRIC.md": _sha(PACK_DIR / "RUBRIC.md"),
                        "check_labels.py": _sha(PACK_DIR / "check_labels.py"), "fresh_draw_map.json": _sha(KEY)},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
