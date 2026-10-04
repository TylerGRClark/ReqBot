"""WP-45.1(b): build the blind labeling pack for the parent-stem attachment audit (read-only; no LLM, no Qdrant).

Draws a stratified, seeded sample of the normalized-tier records and writes two sets of cards:
  pack_a.md  source text only (the quote, its chunk, the previous chunk), no pipeline output
  pack_b.md  the stem the pipeline attached, for the sampled records that have one
plus RUBRIC.md-compatible ids (R001...) that carry no stratum information. The answer key (id -> record, stratum,
attachment method) is written ONLY to --key-out and is never part of the pack.

Why two passes: asking "is this stem right?" anchors the labeler on the pipeline's answer. Pass A makes each
labeler say whether the quote needs a lead-in and where it is before seeing the pipeline's stem.

The sample is the first n of a seeded shuffle of each stratum, so it can be extended later without a redraw.
The 16 same-chunk records hand-labeled earlier (audit F04, seed 45) are excluded from the same-chunk frame so
the new labels do not depend on those earlier ones; they were a random draw, so the rest of the stratum
stands in for it.

Run from the repo root:
  python3 eval/spike_results/wp_45_1/audit_pack.py --out-dir eval/spike_results/wp_45_1/outputs/audit_pack \\
      --key-out PATH_OUTSIDE_THE_PACK/key.json --manifest-out eval/spike_results/wp_45_1/outputs/audit_pack_manifest.json
"""

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import census as C  # noqa: E402
from _inputs import corpus_inputs  # noqa: E402
from core.profiles import default_profile  # noqa: E402

SEED = "wp45.1b"
PRIOR_SAMPLE_SEED = 45  # audit F04: random.seed(45); random.sample(same-chunk attachments, 16)
PRIOR_SAMPLE_SIZE = 16

# Population per stratum on the pinned corpus (census tables) and how many of each to label.
# A change in the data or the census rules shows up here as a hard stop rather than a quietly different sample.
POPULATION = {
    "same-chunk": 142,
    "cross-chunk": 59,
    "heading": 2,
    "none+signal": 90,
    "none+nosignal": 546,
    "not-a-candidate+signal": 54,
    "not-a-candidate+nosignal": 954,
}
SAMPLE = {
    "same-chunk": 36,
    "cross-chunk": 28,
    "heading": 2,
    "none+signal": 28,
    "none+nosignal": 20,
    "not-a-candidate+signal": 8,
    "not-a-candidate+nosignal": 8,
}
MARK_OPEN, MARK_CLOSE = "⟦", "⟧"  # ⟦ ⟧ around the quote inside its chunk
SHOW_LIMIT = (
    4000  # characters of a chunk shown in full; longer chunks are windowed around the quote
)
UNMARKED_LIMIT = (
    8000  # a quote not found in its chunk cannot anchor a window, so those chunks get more room
)
WINDOW_BEFORE, WINDOW_AFTER = 3000, 500


def stratum_of(method, signalled):
    if method in ("same-chunk", "cross-chunk", "heading"):
        return method
    return f"{method}+{'signal' if signalled else 'nosignal'}"


def load_rows(inputs, verb_re):
    """Census rows plus the quote and chunk texts, in the census's own order."""
    rows = C.collect(inputs, verb_re)
    out, i = [], 0
    for doc, files in inputs.items():
        chunks = {c["chunk_id"]: c for c in C._read_jsonl(files["chunks"])}
        for rec in C._read_jsonl(files["normalized"]):
            row = rows[i]
            i += 1
            if row["document"] != doc or row["requirement_id"] != rec.get("requirement_id"):
                sys.exit(f"census row {i} does not line up with the normalized file for {doc}")
            row = dict(row)
            row["quote"] = (rec.get("source_quote") or "").strip()
            row["chunk"] = chunks.get(row["chunk_id"])
            row["prev_chunk"] = (
                chunks.get(row["chunk_id"] - 1) if row["chunk_id"] is not None else None
            )
            row["index"] = i - 1
            row["signalled"] = any(row["signals"][s] for s in C.FRAGMENT_SIGNALS)
            row["stratum"] = stratum_of(row["method"], row["signalled"])
            out.append(row)
    if i != len(rows):
        sys.exit("census produced rows that no normalized record accounts for")
    return out


def prior_sample_indexes(rows):
    """Row indexes of the 16 same-chunk attachments hand-labeled in audit F04 (same seed, same candidate order)."""
    same = [r for r in rows if r["method"] == "same-chunk"]
    picks = random.Random(PRIOR_SAMPLE_SEED).sample(range(len(same)), PRIOR_SAMPLE_SIZE)
    return {same[p]["index"] for p in picks}


def check_prior_sample(rows, excluded):
    """The reproduced draw must be the 16 records printed in the audit's own output, or the exclusion is wrong."""
    printed = (_ROOT / "eval/spike_results/wp_45_audit/outputs/f04_sample.txt").read_text(
        encoding="utf-8"
    )
    missing = [
        r for r in rows if r["index"] in excluded and f"ITEM : {r['quote'][:150]}" not in printed
    ]
    if missing:
        sys.exit(
            f"the reproduced F04 draw does not match outputs/f04_sample.txt ({len(missing)} of "
            f"{PRIOR_SAMPLE_SIZE} differ); not excluding the wrong records"
        )


def draw(rows, excluded):
    frames = {s: [] for s in POPULATION}
    for r in rows:
        frames[r["stratum"]].append(r)
    counts = {s: len(v) for s, v in frames.items()}
    if counts != POPULATION:
        sys.exit(f"stratum populations changed: expected {POPULATION}, found {counts}")
    chosen = []
    for stratum, frame in frames.items():
        frame = [r for r in frame if r["index"] not in excluded]
        frame.sort(key=lambda r: r["index"])
        random.Random(f"{SEED}/{stratum}").shuffle(frame)
        take = frame[: SAMPLE[stratum]]
        if len(take) != SAMPLE[stratum]:
            sys.exit(
                f"stratum {stratum} has only {len(take)} eligible records for a sample of {SAMPLE[stratum]}"
            )
        chosen.extend(take)
    random.Random(f"{SEED}/order").shuffle(chosen)
    for n, r in enumerate(chosen, 1):
        r["id"] = f"R{n:03d}"
    return chosen


def require_chunks(chosen):
    """Every sampled record needs its own chunk to build a card; a gap means the inputs and the census disagree."""
    for r in chosen:
        if r["chunk"] is None:
            sys.exit(
                f"chunk {r['chunk_id']} of {r['document']} is missing for {r['requirement_id']}; "
                "no card can be built for it"
            )


def _flexible(quote):
    return r"\s+".join(re.escape(tok) for tok in quote.split())


def show_chunk(text, quote=None, tail=False):
    """The chunk as the labeler sees it: the quote marked where it appears (whitespace-insensitive), long chunks windowed."""
    if (
        MARK_OPEN in text or MARK_CLOSE in text
    ):  # never alter source text silently; the pinned corpus has none
        sys.exit(
            f"chunk text already contains {MARK_OPEN} or {MARK_CLOSE}; pick other quote markers"
        )
    span = None
    if quote:
        m = re.search(_flexible(quote), text)
        span = m.span() if m else None
    note = ""
    if span:
        text = text[: span[0]] + MARK_OPEN + text[span[0] : span[1]] + MARK_CLOSE + text[span[1] :]
        span = (span[0], span[1] + 2)
    elif quote:
        note = "(the quote does not appear verbatim in this chunk, so it is not marked; judge it as written)\n"
    limit = UNMARKED_LIMIT if quote and not span else SHOW_LIMIT
    if len(text) > limit:
        if span:
            start, end = max(0, span[0] - WINDOW_BEFORE), min(len(text), span[1] + WINDOW_AFTER)
        elif tail:
            start, end = len(text) - WINDOW_BEFORE, len(text)
        else:
            start, end = 0, limit - 500
        head = f"[... {start} characters omitted ...]\n" if start else ""
        foot = f"\n[... {len(text) - end} characters omitted ...]" if end < len(text) else ""
        text = head + text[start:end] + foot
    return note, text


def card_a(r):
    chunk = r["chunk"]
    note, body = show_chunk(chunk["text"], r["quote"])
    lines = [
        f"## {r['id']}",
        f"Document: {r['document']}  |  chunk {r['chunk_id']}  |  page {chunk.get('page_start')}",
        "",
        "Quote (the requirement text to judge):",
        "> " + r["quote"].replace("\n", "\n> "),
        "",
        f"Chunk {r['chunk_id']} (the quote is marked {MARK_OPEN} {MARK_CLOSE} where it appears):",
    ]
    if note:
        lines.append(note.rstrip())
    lines += ["~~~~text", body, "~~~~", ""]
    prev = r["prev_chunk"]
    if prev:
        _, pbody = show_chunk(prev["text"], tail=True)
        lines += [f"Previous chunk {prev['chunk_id']}:", "~~~~text", pbody, "~~~~", ""]
    else:
        lines += ["Previous chunk: none (this is the document's first chunk).", ""]
    return "\n".join(lines)


def card_b(r):
    return "\n".join(
        [
            f"## {r['id']}",
            "Quote:",
            "> " + r["quote"].replace("\n", "\n> "),
            "",
            "Stem the pipeline attached:",
            "> " + r["stem"].replace("\n", "\n> "),
            "",
        ]
    )


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", required=True, help="where pack_a.md and pack_b.md go")
    ap.add_argument(
        "--key-out", required=True, help="answer key; keep it OUT of the labelers' reach"
    )
    ap.add_argument("--manifest-out", help="inputs, versions, seed, sample table and file hashes")
    args = ap.parse_args()
    if Path(args.key_out).resolve().is_relative_to(Path(args.out_dir).resolve()):
        sys.exit("--key-out must be outside --out-dir so the pack stays blind")

    inputs = corpus_inputs("chunks", "extracted", "normalized")
    verbs = default_profile()["obligation_verbs"]
    verb_re = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in verbs) + r")\b", re.IGNORECASE)
    rows = load_rows(inputs, verb_re)
    excluded = prior_sample_indexes(rows)
    check_prior_sample(rows, excluded)
    chosen = draw(rows, excluded)
    require_chunks(chosen)

    pack_a = (
        "# Attachment audit, pass A: source text only\n\n"
        "Read RUBRIC.md first. Cards are in random order. Do not open pack_b.md until every card here is labeled.\n\n"
        + "\n".join(card_a(r) for r in sorted(chosen, key=lambda r: r["id"]))
    )
    attached = [r for r in sorted(chosen, key=lambda r: r["id"]) if r["stem"]]
    pack_b = (
        "# Attachment audit, pass B: the stem the pipeline attached\n\n"
        "Only records that received a stem appear here. Judge each stem against its quote (RUBRIC.md, pass B). "
        "pack_a.md has the surrounding text.\n\n" + "\n".join(card_b(r) for r in attached)
    )
    out_dir = Path(args.out_dir)
    hashes = {
        "pack_a.md": write(out_dir / "pack_a.md", pack_a),
        "pack_b.md": write(out_dir / "pack_b.md", pack_b),
    }
    for name in (
        "RUBRIC.md",
        "check_labels.py",
    ):  # the labelers' instructions, written by hand next to the pack
        hashes[name] = C._sha256(out_dir / name) if (out_dir / name).exists() else None

    key = {
        "seed": SEED,
        "prior_sample_excluded": sorted(excluded),
        "items": {
            r["id"]: {
                "document": r["document"],
                "requirement_id": r["requirement_id"],
                "chunk_id": r["chunk_id"],
                "index": r["index"],
                "stratum": r["stratum"],
                "method": r["method"],
                "stem": r["stem"],
            }
            for r in sorted(chosen, key=lambda r: r["id"])
        },
        "population": POPULATION,
        "sample": SAMPLE,
        "frame_excluding_prior": {
            s: sum(1 for r in rows if r["stratum"] == s and r["index"] not in excluded)
            for s in POPULATION
        },
    }
    key_hash = write(args.key_out, json.dumps(key, indent=2, ensure_ascii=False) + "\n")

    n_stem = len(attached)
    print(f"records labeled: {len(chosen)}  (pass B cards, i.e. with an attached stem: {n_stem})")
    print(f"{'stratum':26s} {'population':>10s} {'frame':>6s} {'sample':>6s}")
    for s in POPULATION:
        print(f"{s:26s} {POPULATION[s]:10d} {key['frame_excluding_prior'][s]:6d} {SAMPLE[s]:6d}")
    unmarked = [r["id"] for r in chosen if not re.search(_flexible(r["quote"]), r["chunk"]["text"])]
    big = [
        r["id"]
        for r in chosen
        if len(r["chunk"]["text"]) > (UNMARKED_LIMIT if r["id"] in unmarked else SHOW_LIMIT)
    ]
    print(
        f"chunks windowed (more than {SHOW_LIMIT} characters, {UNMARKED_LIMIT} if the quote is not in it): {len(big)} {big}"
    )
    print(f"quotes not found verbatim in their chunk (card says so): {len(unmarked)} {unmarked}")
    for name, digest in hashes.items():
        print(f"sha256 {name}: {digest}")
    print(f"sha256 key: {key_hash}")

    if args.manifest_out:
        manifest = C.build_manifest(inputs)
        manifest["script"] = "eval/spike_results/wp_45_1/audit_pack.py"
        manifest["code_sha256"]["eval/spike_results/wp_45_1/audit_pack.py"] = C._sha256(
            Path(__file__)
        )
        manifest["audit_pack"] = {
            "seed": SEED,
            "population": POPULATION,
            "frame_excluding_prior_sample": key["frame_excluding_prior"],
            "sample": SAMPLE,
            "pass_b_cards": n_stem,
            "file_sha256": hashes,
            "answers_sha256": key_hash,
            "answers_note": "the answer key is not in the repository; rerunning this script with the same inputs reproduces it byte for byte",
        }
        write(args.manifest_out, json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
