#!/usr/bin/env python3
"""WP-45.7: score discovery runs on the labeled development pages (offline; no LLM).

Recall, the way WP-45.1(e) measured it: of the adjudicated obligations on the sampled pages, how many does a run's extracted
records cover (a piece is covered when the records of its chunk(s) reproduce at least 90% of its tokens; partly covered from 50%),
with the 45.1(e) page-level bootstrap interval and a paired difference between runs. Precision, by an overlap rule fixed here:
a record touches a labeled piece when it holds at least half of the piece's tokens or the piece holds at least half of the
record's; a record that touches an adjudicated obligation is a true positive; one that touches only non-obligation pieces is a
false positive (split by the pieces' label); one that touches no labeled piece is `unscored` (it lies in text nobody labeled) and
is reported by count, never counted as a false positive or a miss. When a false-positive record touches pieces of different labels, the
`false_positive_<label>` breakdown uses the first touched piece in page order; the false-positive total is unaffected. Needs numpy,
as WP-45.1(e)'s `score.py` (which this reuses) already does; numpy is not a project dependency, and this script is an eval tool. A chunk whose call was an overrun, a truncation, a failure or
untreatable exports no records, so its obligations stay misses.

The labels are the 45.1(e) ones, made under rubric version 1: permission-only pieces ("may", "can") were not obligations there, and
a `should` recommendation was. The dev set therefore under-credits an arm that correctly returns permissions; the kind pass
(`pack_devkind.md`) will say how many such pieces there are.

  python3 eval/spike_results/wp_45_7/score_discovery.py --runs d0=~/wp45_7_scratch/d0_8b_dev_r1 d1=~/wp45_7_scratch/d1_8b_dev_r1 \\
      --baseline d0 [--out results.json]
"""

import argparse
import collections
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_DEV = _ROOT / "eval/spike_results/wp_45_1e"
for _p in (_HERE, _ROOT, _DEV, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import chunk_sets as CS  # noqa: E402
import loss_trace as T  # noqa: E402  (WP-45.1(e): tokens and the coverage rule)
import ollama_run as OR  # noqa: E402
import run_discovery as RD  # noqa: E402
import score as DEV  # noqa: E402  (WP-45.1(e): labels, trace_all, page bootstrap, paired difference)

TOUCH = 0.5


def load_dev_labels():
    """(final labels, piece index, obligation ids with sound segmentation, every sampled page) of the WP-45.1(e) sample."""
    labels = DEV.load_labels(_DEV / "labels")
    answers = DEV.parse_answers((_DEV / "labels" / "adjudication.txt").read_text(encoding="utf-8"))
    final = DEV.resolve(labels, answers)
    frozen = json.loads(CS.DEV_FROZEN.read_text(encoding="utf-8"))
    index = DEV.piece_index(frozen)
    obligations = [i for i, r in final.items() if r["label"] == "obligation" and not r["flagged"]]
    pages = sorted({(index[i]["document"], index[i]["page"]) for i in index})
    return final, index, obligations, pages


def touches(piece_tokens, quote_tokens):
    """A record touches a piece when it holds at least half the piece's tokens or the piece holds at least half the record's."""
    if not piece_tokens or not quote_tokens:
        return False
    in_piece = len(T.matched_indices(piece_tokens, quote_tokens)) / len(piece_tokens)
    in_quote = len(T.matched_indices(quote_tokens, piece_tokens)) / len(quote_tokens)
    return in_piece >= TOUCH or in_quote >= TOUCH


def precision_tally(records, final, index):
    """Classify every extracted record (as (document, record)) against the labeled pieces of its document."""
    by_doc = collections.defaultdict(list)
    for pid, info in index.items():
        by_doc[info["document"]].append((pid, T.tokens(info["text"], drop_marker=False)))
    out = collections.Counter()
    for document, rec in records:
        q = T.tokens(rec["source_quote"], drop_marker=False)
        hit = [pid for pid, toks in by_doc[document] if touches(toks, q)]
        if not hit:
            out["unscored"] += 1
        elif any(final[p]["label"] == "obligation" for p in hit):
            out["true_positive"] += 1
        else:
            out["false_positive"] += 1
            out["false_positive_" + final[hit[0]]["label"]] += 1
    return dict(out)


def runs_for(extracted_by_doc, documents):
    """The `runs[document]` structure `score.trace_all` expects, with Step D skipped (survivors are the extracted records)."""
    chunks = CS.load_document_chunks(*documents)
    out = {}
    for document in documents:
        extracted = extracted_by_doc.get(document, [])
        out[document] = {
            "chunk_tokens": {c["chunk_id"]: T.tokens(c["text"], drop_marker=False) for c in chunks[document]},
            "extracted": extracted, "normalized": extracted, "failure_codes": {}, "gate_failures": set(), "parse_failed_chunks": set(),
        }
    return out


def score_run(ledger_dir, final, index, obligations, pages):
    ledger = OR.Ledger(Path(ledger_dir) / "discovery.jsonl")
    records = RD.extracted_records(ledger)
    by_doc = collections.defaultdict(list)
    for document, rec in records:
        by_doc[document].append(rec)
    documents = sorted({index[i]["document"] for i in index})
    traces = DEV.trace_all(obligations, index, runs_for(by_doc, documents), None)
    boot = DEV.page_bootstrap(traces, False, pages=pages)["extracted"]
    summary = RD.summarize(ledger)
    return {
        "traces": traces,
        "recall": boot["primary"], "recall_partly_counted": boot["lenient"],
        "precision": precision_tally(records, final, index),
        "records": len(records), "status": summary["status"],
        "mean_prompt_tokens": summary["mean_prompt_tokens"], "mean_answer_tokens": summary["mean_answer_tokens"],
        "mean_wall_seconds": summary["mean_wall_seconds"],
    }


def precision_rate(p):
    scored = p.get("true_positive", 0) + p.get("false_positive", 0)
    return round(p.get("true_positive", 0) / scored, 3) if scored else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", nargs="+", required=True, metavar="NAME=DIR")
    ap.add_argument("--baseline", help="the run name that every other run is compared with (paired, page bootstrap)")
    ap.add_argument("--out")
    args = ap.parse_args()
    final, index, obligations, pages = load_dev_labels()
    results, traces = {}, {}
    for spec in args.runs:
        name, _, directory = spec.partition("=")
        r = score_run(Path(directory).expanduser(), final, index, obligations, pages)
        traces[name] = r.pop("traces")
        r["precision_rate"] = precision_rate(r["precision"])
        results[name] = r
    if args.baseline:
        for name in results:
            if name != args.baseline:
                results[name]["vs_" + args.baseline] = DEV.paired_difference(traces[name], traces[args.baseline], "extracted", pages=pages)
    results["_meta"] = {"obligations": len(obligations), "pages": len(pages), "rubric": "WP-45.1(e) version 1 labels"}
    text = json.dumps(results, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
