#!/usr/bin/env python3
"""WP-45.11: score arms against the source-based recall sample and compare them run to run (offline; reads scratch runs only).

  python3 score_arms.py --arms B0a B0b T1 --out outputs/arms_report.json
  python3 score_arms.py --arms B0a B0b --pair B0a B0b          # print the obligations that differ between two arms

Recall: the 74 adjudicated, unflagged obligations of WP-45.1(e) (`wp_45_1e/`), traced through each arm's Step C records and Step D survivors exactly as that
work did (`loss_trace.trace_piece`). Run level (all 13 documents): chunks, Step C ledger rows (one per chunk; the pipeline does not persist the number of model requests, so cost is wall time), records, Step D survivors and failure codes, and the overlap of the
normalized quote sets between two arms. Every number is a count; differences are reported as pairs, never as rates of change, and the noise floor is the
difference between the two replicate arms.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit", _ROOT / "eval/spike_results/wp_45_10"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402
import score as S  # noqa: E402  (wp_45_1e)

SCRATCH = Path.home() / "wp45_11_scratch"
E1 = _ROOT / "eval/spike_results/wp_45_1e"
SAMPLE_DOCS = ("DODI 8410.03", "afman17-2101", "NIST.SP.800-125")


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def obligations():
    """(index of all pieces, the 74 adjudicated unflagged obligation ids)."""
    frozen = json.loads(S.FROZEN.read_text(encoding="utf-8"))
    index = S.piece_index(frozen)
    labels = S.load_labels(E1 / "labels")
    final = S.resolve(labels, S.parse_answers((E1 / "labels" / "adjudication.txt").read_text(encoding="utf-8")))
    ids = {i for i, r in final.items() if r["label"] == "obligation" and not r["flagged"]}
    return index, ids


def arm_dir(arm, doc, scratch=SCRATCH):
    return Path(scratch) / arm / doc


def recall_traces(arm, index, ids, scratch=SCRATCH):
    runs = {d: S.load_run(arm_dir(arm, d, scratch), d) for d in SAMPLE_DOCS}
    return S.trace_all(ids, index, runs, None)


def status_counts(traces):
    c = collections.Counter()
    for t in traces.values():
        c["chunked"] += bool(t["chunk_ids"])
        c["extracted_covered"] += t["status"].get("extracted") == "covered"
        c["extracted_partial"] += t["status"].get("extracted") == "partial"
        c["survived_step_d_covered"] += t["status"].get("survived_step_d") == "covered"
    return dict(c)


def trace_excerpt(trace):
    """What explains an obligation's status in one arm: its status at each stage and the Step C / Step D records that cover or reject it."""
    return {"status": trace["status"], "shares": trace["shares"], "first_loss": trace["first_loss"], "covering_extracted": trace["covering_extracted"],
            "covering_surviving": trace["covering_surviving"], "rejected_ids": trace["rejected_ids"]}


def paired(ta, tb, key="extracted"):
    """Obligations found (covered) in A and not in B, and the reverse."""
    a = {i for i, t in ta.items() if t["status"].get(key) == "covered"}
    b = {i for i, t in tb.items() if t["status"].get(key) == "covered"}
    return {"only_first": sorted(a - b), "only_second": sorted(b - a), "both": len(a & b), "neither": len(set(ta) - a - b)}


ARTIFACTS = ("{doc}_chunks.jsonl", "{doc}_extracted_requirements.jsonl", "{doc}_requirements_normalized.jsonl", "{doc}_raw_responses.jsonl", "arm_record.json")


def check_complete(arm, scratch=SCRATCH):
    """Refuse to score an arm unless all 13 documents finished: every artifact present and the pipeline's return code 0 (an interrupted or failed run would
    otherwise read as zero or partial counts and as recall losses). Every problem is listed at once."""
    problems = []
    for doc in sorted(common.pinned_documents()):
        d = arm_dir(arm, doc, scratch)
        for pattern in ARTIFACTS:
            if not (d / pattern.format(doc=doc)).exists():
                problems.append(f"{arm}/{doc}: missing {pattern.format(doc=doc)}")
        rec = d / "arm_record.json"
        if rec.exists() and json.loads(rec.read_text(encoding="utf-8")).get("returncode") != 0:
            problems.append(f"{arm}/{doc}: the pipeline did not exit 0")
        raw_path, chunks_path = d / f"{doc}_raw_responses.jsonl", d / f"{doc}_chunks.jsonl"
        if raw_path.exists() and chunks_path.exists():
            raw = [json.loads(x) for x in raw_path.read_text(encoding="utf-8").splitlines() if x.strip()]
            n_chunks = sum(1 for x in chunks_path.read_text(encoding="utf-8").splitlines() if x.strip())
            # run_pipeline exits 0 even when a chunk's requests were exhausted (status "failed"); such a chunk is a missing observation, not a finding
            failed = [r.get("chunk_id") for r in raw if r.get("status") == "failed"]
            if failed:
                problems.append(f"{arm}/{doc}: Step C failed on chunks {failed}")
            if len(raw) != n_chunks:
                problems.append(f"{arm}/{doc}: {len(raw)} Step C ledger rows for {n_chunks} chunks")
    if problems:
        raise SystemExit("the arm is not complete, so it is not scored:\n  " + "\n  ".join(problems))


def run_level(arm, scratch=SCRATCH):
    check_complete(arm, scratch)
    out, quotes = {}, {}
    for doc in sorted(common.pinned_documents()):
        d = arm_dir(arm, doc, scratch)
        rd = lambda name: [json.loads(x) for x in (d / name).read_text(encoding="utf-8").splitlines() if x.strip()] if (d / name).exists() else []  # noqa: E731
        extracted, normalized, failures = rd(f"{doc}_extracted_requirements.jsonl"), rd(f"{doc}_requirements_normalized.jsonl"), rd(f"{doc}_normalization_failures.jsonl")
        raw = rd(f"{doc}_raw_responses.jsonl")
        record = json.loads((d / "arm_record.json").read_text(encoding="utf-8")) if (d / "arm_record.json").exists() else {}
        out[doc] = {"chunks": len(rd(f"{doc}_chunks.jsonl")), "step_c_ledger_rows": len(raw), "records": len(extracted), "survivors": len(normalized),
                    "failure_codes": dict(collections.Counter(f.get("error", "unknown") for f in failures)), "wall_seconds": record.get("wall_seconds")}
        quotes[doc] = {norm(r.get("source_quote", "")) for r in normalized}
    return out, quotes


def overlap(qa, qb):
    """Jaccard overlap of the normalized surviving quote sets, per document and overall."""
    per, inter, union = {}, 0, 0
    for doc in qa:
        i, u = len(qa[doc] & qb[doc]), len(qa[doc] | qb[doc])
        per[doc] = {"shared": i, "only_first": len(qa[doc] - qb[doc]), "only_second": len(qb[doc] - qa[doc]), "jaccard": round(i / u, 3) if u else None}
        inter += i
        union += u
    return {"overall_jaccard": round(inter / union, 4) if union else None, "per_document": per}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--pair", nargs=2, metavar=("A", "B"), help="also print the obligations found in only one of the two arms (both must be in --arms, in that order)")
    ap.add_argument("--scratch", default=str(SCRATCH))
    ap.add_argument("--out")
    args = ap.parse_args()
    index, ids = obligations()
    assert len(ids) == 74, f"expected the 74 adjudicated unflagged obligations, got {len(ids)}"
    for arm in args.arms:
        check_complete(arm, args.scratch)  # before anything is traced: a partial run must not produce recall numbers
    traces = {arm: recall_traces(arm, index, ids, args.scratch) for arm in args.arms}
    levels, quotes = {}, {}
    for arm in args.arms:
        levels[arm], quotes[arm] = run_level(arm, args.scratch)
    report = {"obligations": len(ids), "arms": {}, "pairs": {}}
    for arm in args.arms:
        tot = {k: sum(v[k] for v in levels[arm].values()) for k in ("chunks", "step_c_ledger_rows", "records", "survivors")}
        codes = collections.Counter()
        for v in levels[arm].values():
            codes.update(v["failure_codes"])
        report["arms"][arm] = {"recall": status_counts(traces[arm]), "totals": tot, "failure_codes": dict(codes), "per_document": levels[arm]}
    for i, a in enumerate(args.arms):
        for b in args.arms[i + 1:]:
            p = paired(traces[a], traces[b])
            for k in ("only_first", "only_second"):
                p[k] = [{"id": x, "document": index[x]["document"], "page": index[x]["page"], "text": index[x]["text"], "trace_first": trace_excerpt(traces[a][x]),
                         "trace_second": trace_excerpt(traces[b][x])} for x in p[k]]
            report["pairs"][f"{a} vs {b}"] = {"recall_extracted": p, "quote_overlap": overlap(quotes[a], quotes[b])}
    for arm, v in report["arms"].items():
        print(arm, v["recall"], v["totals"])
    if args.pair:
        want = f"{args.pair[0]} vs {args.pair[1]}"
        if want not in report["pairs"]:
            raise SystemExit(f"--pair {args.pair}: both arms must be in --arms and the order must follow it (looked for {want!r} in {sorted(report['pairs'])})")
        for side in ("only_first", "only_second"):
            for o in report["pairs"][want]["recall_extracted"][side]:
                print(f"{side}: {o['id']} ({o['document']}, p{o['page']}): {o['text'][:200]}")
    for k, v in report["pairs"].items():
        print(k, "| only first:", len(v["recall_extracted"]["only_first"]), "only second:", len(v["recall_extracted"]["only_second"]), "| quote Jaccard", v["quote_overlap"]["overall_jaccard"])
    if args.out:
        Path(_HERE / args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(_HERE / args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
