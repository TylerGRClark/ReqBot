#!/usr/bin/env python3
"""WP-45.10 H1: score re-chunked outputs against the labeled lead-ins and the baseline's text (offline; no LLM).

  python3 analyze_chunks.py --runs d2.94.0:256 d2.94.0:512 d2.94.0:1024 d2.94.0:2048 d2.94.0:4096 --out chunks_report.json
  python3 analyze_chunks.py --runs d2.94.0:default d2.135.0:default --out upgrade_chunks_report.json      # the upgrade comparison

A run is RELEASE_TAG:LABEL (a token limit, or `default` for that release's own HybridChunker()); the first run is the baseline every other is compared with,
so a comparison can span two Docling releases (files under ~/wp45_10_cache/<tag>/chunks/<label>/).

Measures per token limit (all through the production chunk function, so its filters apply):
  * chunk count and size distribution (characters and the repository's own token estimate), and how many chunks leave less than the answer allowance of
    Step C's 8,192-token window once the fixed prompt is counted;
  * lead-in co-location: of the labeled quotes that need a lead-in and have its text (the audit gold and the fresh gold, both already in the repository),
    the share whose lead-in text sits wholly inside the `text` (breadcrumb plus body) of the chunk that contains the quote. The 256-token result is checked
    against the labelers' own `lead_in_location` (the metric must call a previous_chunk label not co-located);
  * list continuations: chunks whose body opens with a list marker that is not a list's first (a list cut across chunks);
  * text preservation against the 256-token emitted text: word 6-gram multiset loss and duplication over each document's chunks concatenated in order.
"""

import argparse
import collections
import json
import re
import statistics

import common

GOLDS = ("eval/spike_results/wp_45_7/outputs/resolver_gold.json", "eval/spike_results/wp_45_7/outputs/fresh_gold.json")
ANSWER_ALLOWANCE = 1000  # tokens kept free for Step C's answer; the largest answer seen in the 13 documents is about 570 (llm_extract_requirements.py)
WINDOW = 8192
_MARKER = re.compile(r"^\(?([a-zA-Z0-9]{1,3})[.)]\s")
_FIRST = {"1", "a", "A", "i", "I"}


def norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def load_chunks(run, name):
    tag, _, label = run.partition(":")
    path = common.cache_dir("chunks", label, tag, create=False) / f"{name}_chunks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def est_tokens(chars):
    return -(-int(chars) * 2 // 5)  # the repository's estimate (bundle.estimate_tokens): ceil(chars / 2.5)


def fixed_prompt_tokens():
    from pipeline import llm_extract_requirements as llm
    from core.profiles import default_profile
    template = llm.PASS1_PROMPT_TEMPLATE.replace("{obligation_verbs}", ", ".join(default_profile()["obligation_verbs"]))
    return est_tokens(len(llm._render_prompt(template, "")))


def gold_items():
    items = []
    for rel in GOLDS:
        for g in json.loads((common.ROOT / rel).read_text(encoding="utf-8"))["gold"]:
            if g.get("set") == "audit" and g.get("standalone") == "needs_lead_in" and g.get("lead_in_text"):
                items.append({"id": g["candidate_id"], "document": g["document"], "quote": g["quote"], "lead_in": g["lead_in_text"],
                              "location": g["lead_in_location"], "gold": "fresh" if "fresh" in rel else "audit"})
    return items


def pieces(lead_in):
    return [norm(p) for part in re.split(r"\s*\|\s*", lead_in) for p in re.split(r"\s*\.\.\.\s*", part) if norm(p)]


def colocation(run, items, cache):
    """{candidate id: 'colocated' | 'apart' | 'quote_not_found'} for this run."""
    out = {}
    for it in items:
        chunks = cache.setdefault((run, it["document"]), load_chunks(run, it["document"]))
        q = norm(it["quote"])
        hit = next((c for c in chunks if q in norm(c["raw_text"])), None) or next((c for c in chunks if q[:60] in norm(c["raw_text"])), None)
        if hit is None:
            out[it["id"]] = "quote_not_found"
            continue
        text = norm(hit["text"])
        out[it["id"]] = "colocated" if all(p in text for p in pieces(it["lead_in"])) else "apart"
    return out


def list_continuations(chunks):
    n = 0
    for c in chunks:
        m = _MARKER.match(c["raw_text"].strip())
        if m and m.group(1) not in _FIRST:
            n += 1
    return n


def shingles(chunks, n=6):
    words = " ".join(norm(c["raw_text"]) for c in chunks).split()
    return collections.Counter(tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1)))


def preservation(base, other):
    lost = dup = total = 0
    for name in base:
        b, o = shingles(base[name]), shingles(other[name])
        total += sum(b.values())
        lost += sum(max(0, v - o.get(k, 0)) for k, v in b.items())
        dup += sum(max(0, v - b.get(k, 0)) for k, v in o.items())
    return {"baseline_shingles": total, "lost": lost, "extra": dup, "lost_share": round(lost / total, 5), "extra_share": round(dup / total, 5)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", nargs="+", required=True, help="RELEASE_TAG:LABEL, the first is the baseline")
    ap.add_argument("--out")
    args = ap.parse_args()
    names = sorted(common.pinned_documents())
    items = gold_items()
    fixed = fixed_prompt_tokens()
    cache, report = {}, {"versions": common.versions(), "gold_items": len(items), "fixed_prompt_tokens": fixed, "limits": {}}
    for run in args.runs:
        if ":" not in run:
            raise SystemExit(f"{run!r}: a run is RELEASE_TAG:LABEL, for example d2.94.0:256")
    base = {n: load_chunks(args.runs[0], n) for n in names}
    for limit in args.runs:
        per_doc = {n: load_chunks(limit, n) for n in names}
        allc = [c for chunks in per_doc.values() for c in chunks]
        sizes = sorted(len(c["raw_text"]) for c in allc)
        co = colocation(limit, items, cache)
        by = collections.Counter(co.values())
        by_loc = collections.defaultdict(collections.Counter)
        for it in items:
            by_loc[it["location"]][co[it["id"]]] += 1
        report["limits"][limit] = {
            "chunks": len(allc), "median_chars": statistics.median(sizes), "p90_chars": sizes[int(len(sizes) * 0.9)], "max_chars": sizes[-1],
            "over_window_after_prompt": sum(1 for c in allc if fixed + est_tokens(len(c["text"])) + ANSWER_ALLOWANCE > WINDOW),
            "list_continuation_chunks": sum(list_continuations(v) for v in per_doc.values()),
            "colocation": dict(by), "colocation_by_labeled_location": {k: dict(v) for k, v in sorted(by_loc.items())},
            "preservation_vs_baseline": preservation(base, per_doc),
        }
        r = report["limits"][limit]
        print(f"{limit:16s}: {r['chunks']:5d} chunks, median {r['median_chars']:.0f} chars, max {r['max_chars']}, over-window {r['over_window_after_prompt']}, "
              f"list-continuations {r['list_continuation_chunks']}, colocated {by.get('colocated', 0)}/{len(items)} (not found {by.get('quote_not_found', 0)}), "
              f"lost {r['preservation_vs_baseline']['lost']} extra {r['preservation_vs_baseline']['extra']}", flush=True)
    if args.out:
        (common.HERE / args.out).write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
