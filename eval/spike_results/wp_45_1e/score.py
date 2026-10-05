"""WP-45.1(e): adjudication sheet, adjudicated labels, the trace of every obligation, and the recall report.

  python3 eval/spike_results/wp_45_1e/score.py sheet --labels-dir DIR --out SHEET.md
  python3 eval/spike_results/wp_45_1e/score.py report --labels-dir DIR --answers ADJUDICATION.txt --out-dir outputs [--no-index]

`sheet` lists every piece the two labelers labeled differently, plus 10 seeded spot-checks of agreements (5 agreed
obligations, 5 agreed non-obligations). An answers file has one line per ruling, `PIECE-ID: label`, `#` for comments.
`report` needs every disagreement ruled on. Uncertainty is a page-level bootstrap (the 12 sampled pages are resampled with
their pieces kept together), because pieces on one page are not independent.
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _HERE, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import segment as S  # noqa: E402
import loss_trace as T  # noqa: E402

LABELERS = ("claude", "codex")
LABELS = ("obligation", "lead_in", "scope", "not_obligation")
SEED = "wp45.1e"
BOOT_SEED = 451  # numpy needs an integer seed
RESAMPLES = 10_000
SCRATCH = Path.home() / "wp45_6_scratch"
FROZEN = _HERE / "outputs" / "pages_frozen.json"
STAGES = ("chunked", "extracted", "survived_step_d", "indexed")


# ----- labels, adjudication ---------------------------------------------------------------------------------------


def read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_labels(labels_dir):
    return {
        who: {r["id"]: r for r in read_jsonl(Path(labels_dir) / f"labels_{who}_a.jsonl")}
        for who in LABELERS
    }


def piece_index(frozen):
    out = {}
    for document, entry in frozen["documents"].items():
        for page, pieces in entry["pieces"].items():
            ordered = [p["id"] for p in pieces]
            for k, p in enumerate(pieces):
                out[p["id"]] = {
                    "document": document,
                    "page": int(page),
                    "text": p["text"],
                    "before": ordered[max(0, k - 3) : k],
                    "after": ordered[k + 1 : k + 2],
                }
    return out


def disagreements(labels):
    """Pieces where the labelers differ on whether the piece is an obligation. A difference between two non-obligation
    labels (scope, lead_in, not_obligation) changes no count, so it needs no ruling."""
    a, b = (labels[w] for w in LABELERS)
    return sorted(
        i for i in a if (a[i]["label"] == "obligation") != (b[i]["label"] == "obligation")
    )


def non_obligation_differences(labels):
    a, b = (labels[w] for w in LABELERS)
    return sorted(
        i for i in a if a[i]["label"] != b[i]["label"] and i not in set(disagreements(labels))
    )


def spot_checks(labels, seed=SEED, per_kind=5):
    a, b = (labels[w] for w in LABELERS)
    out = []
    for kind in ("obligation", "not_obligation"):
        agreed = sorted(i for i in a if a[i]["label"] == b[i]["label"] == kind)
        random.Random(f"{seed}/spot/{kind}").shuffle(agreed)
        out += agreed[:per_kind]
    return out


def sheet(labels, index):
    dis, spot = disagreements(labels), spot_checks(labels)

    def block(pid):
        info = index[pid]
        ctx = "\n".join(f"    [{i}] {index[i]['text']}" for i in info["before"])
        after = "\n".join(f"    [{i}] {index[i]['text']}" for i in info["after"])
        lines = [
            f"### {pid}  ({info['document']}, page {info['page']})",
            "Before:",
            ctx or "    (start of page)",
        ]
        lines += [
            "**Piece:**",
            f"    [{pid}] {info['text']}",
            "After:",
            after or "    (end of page)",
        ]
        for w in LABELERS:
            r = labels[w][pid]
            lines.append(
                f"- **{w}**: {r['label']}; segment_ok {r['segment_ok']}; note: {r.get('note', '')}"
            )
        return "\n".join(lines)

    head = (
        "# Adjudication sheet (WP-45.1e)\n\n"
        f"{len(dis)} disagreements about whether a piece is an obligation, then {len(spot)} agreements to spot-check "
        f"({len(non_obligation_differences(labels))} other pieces differ only between non-obligation labels and need no "
        "ruling). Answer with one line per piece, "
        f"`PIECE-ID: label` where label is one of {', '.join(LABELS)}; for a spot-check write the label you think is "
        "right (the same label confirms the agreement).\n"
    )
    return (
        head
        + "\n## Disagreements\n\n"
        + "\n\n".join(block(p) for p in dis)
        + "\n\n## Spot-checks of agreements\n\n"
        + "\n\n".join(block(p) for p in spot)
        + "\n"
    )


def parse_answers(text):
    out = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pid, _, label = line.partition(":")
        label = label.strip()
        if label not in LABELS:
            raise ValueError(f"line {n}: {label!r} is not one of {LABELS}")
        out[pid.strip()] = label
    return out


def resolve(labels, answers):
    """Final {piece id: {"label", "flagged"}}; raises if a disagreement has no ruling. 'flagged' = either labeler said the
    segmentation was wrong."""
    a, b = (labels[w] for w in LABELERS)
    unresolved = [i for i in disagreements(labels) if i not in answers]
    if unresolved:
        raise ValueError(f"disagreements without a ruling: {unresolved}")
    final = {}
    for pid in a:
        label = answers.get(
            pid, a[pid]["label"]
        )  # an unruled difference is between two non-obligation labels
        final[pid] = {
            "label": label,
            "flagged": not (a[pid]["segment_ok"] and b[pid]["segment_ok"]),
        }
    return final


def label_sets(labels, final):
    """The obligation id sets for the primary view and the two bounds."""
    a, b = (labels[w] for w in LABELERS)
    return {
        "adjudicated": {i for i, r in final.items() if r["label"] == "obligation"},
        "both_agree": {i for i in a if a[i]["label"] == b[i]["label"] == "obligation"},
        "either": {i for i in a if "obligation" in (a[i]["label"], b[i]["label"])},
    }


# ----- loading a run to trace -------------------------------------------------------------------------------------


def load_run(directory, doc):
    d = Path(directory)
    chunks = {c["chunk_id"]: c for c in read_jsonl(d / f"{doc}_chunks.jsonl")}
    extracted = read_jsonl(d / f"{doc}_extracted_requirements.jsonl")
    normalized = read_jsonl(d / f"{doc}_requirements_normalized.jsonl")
    failures = {
        f.get("requirement_id"): f.get("error", "unknown")
        for f in read_jsonl(d / f"{doc}_normalization_failures.jsonl")
    }
    gate = {
        f.get("requirement_id") for f in read_jsonl(d / f"{doc}_description_gate_failures.jsonl")
    }
    parse_failed = {f.get("chunk_id") for f in read_jsonl(d / f"{doc}_parse_failures.jsonl")}
    return {
        "chunk_tokens": {cid: T.tokens(c["text"], drop_marker=False) for cid, c in chunks.items()},
        "extracted": extracted,
        "normalized": normalized,
        "failure_codes": failures,
        "gate_failures": gate,
        "parse_failed_chunks": parse_failed,
    }


def live_ids(qdrant_url, collection="grc_requirements"):
    from qdrant_client import QdrantClient

    client = QdrantClient(url=qdrant_url)
    ids, offset = set(), None
    while True:
        batch, offset = client.scroll(
            collection, limit=512, offset=offset, with_payload=True, with_vectors=False
        )
        ids.update(p.payload["requirement_id"] for p in batch)
        if offset is None:
            return ids


def trace_all(obligation_ids, index, runs, indexed):
    """{piece id: trace} for the obligations, using runs[document]."""
    out = {}
    for pid in sorted(obligation_ids):
        info = index[pid]
        run = runs[info["document"]]
        t = T.trace_piece(
            info["text"],
            run["chunk_tokens"],
            run["extracted"],
            run["normalized"],
            indexed,
            run["failure_codes"],
        )
        t["document"], t["page"] = info["document"], info["page"]
        if t["first_loss"] == "rejected_step_d":
            t["rejection_codes"] = sorted(
                {
                    run["failure_codes"].get(r, "removed after Step D (no failure record)")
                    for r in t["rejected_ids"]
                }
            )
        if t["first_loss"] == "not_extracted" and t["chunk_ids"]:
            t["chunk_parse_failed"] = any(c in run["parse_failed_chunks"] for c in t["chunk_ids"])
        if t["first_loss"] == "not_indexed":
            t["description_gate"] = any(r in run["gate_failures"] for r in t["covering_surviving"])
        out[pid] = t
    return out


# ----- the report -------------------------------------------------------------------------------------------------


def stage_flags(trace, with_index):
    """Per-stage 0/1 flags (primary: covered) and (partly counted as found)."""
    names = ["extracted", "survived_step_d"] + (["indexed"] if with_index else [])
    chunked = 1 if trace["chunk_ids"] else 0
    primary = {"chunked": chunked}
    lenient = {"chunked": chunked}
    for n in names:
        st = trace["status"].get(n)
        primary[n] = 1 if st == "covered" else 0
        lenient[n] = 1 if st in ("covered", "partial") else 0
    return primary, lenient


def page_bootstrap(traces, with_index, resamples=RESAMPLES, seed=BOOT_SEED):
    """Recall by stage with page-level bootstrap intervals; returns {stage: {...}}."""
    pages = sorted({(t["document"], t["page"]) for t in traces.values()})
    stages = [s for s in STAGES if s != "indexed" or with_index]
    per_page = {
        p: {"n": 0, "primary": collections.Counter(), "lenient": collections.Counter()}
        for p in pages
    }
    for t in traces.values():
        e = per_page[(t["document"], t["page"])]
        e["n"] += 1
        pr, le = stage_flags(t, with_index)
        e["primary"].update(pr)
        e["lenient"].update(le)
    n = np.array([per_page[p]["n"] for p in pages], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pages), size=(resamples, len(pages))) if pages else None
    out = {}
    for view in ("primary", "lenient"):
        for s in stages:
            hit = np.array([per_page[p][view][s] for p in pages], dtype=float)
            total = n.sum()
            point = hit.sum() / total if total else float("nan")
            lo = hi = float("nan")
            if idx is not None and total:
                num, den = hit[idx].sum(axis=1), n[idx].sum(axis=1)
                ok = den > 0
                lo, hi = np.percentile(num[ok] / den[ok], [2.5, 97.5])
            out.setdefault(s, {})[view] = {
                "recall": float(point),
                "interval": [float(lo), float(hi)],
                "n": int(total),
                "hits": int(hit.sum()),
            }
    return out


def loss_table(traces):
    c = collections.Counter(t["first_loss"] or "survived_all_stages" for t in traces.values())
    return dict(c)


def loss_bootstrap(traces, resamples=RESAMPLES, seed=BOOT_SEED):
    """Share of the obligations first lost at each step, with page-level bootstrap intervals (the routing rule uses these)."""
    cats = ["never_chunked", "not_extracted", "partly_extracted", "rejected_step_d", "not_indexed"]
    pages = sorted({(t["document"], t["page"]) for t in traces.values()})
    pos = {p: k for k, p in enumerate(pages)}
    n = np.zeros(len(pages))
    counts = {c: np.zeros(len(pages)) for c in cats}
    for t in traces.values():
        k = pos[(t["document"], t["page"])]
        n[k] += 1
        if t["first_loss"] in counts:
            counts[t["first_loss"]][k] += 1
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pages), size=(resamples, len(pages))) if pages else None
    den = n[idx].sum(axis=1) if idx is not None else None
    out = {}
    for c in cats:
        point = counts[c].sum() / n.sum() if n.sum() else float("nan")
        lo = hi = float("nan")
        if idx is not None:
            ok = den > 0
            lo, hi = np.percentile(counts[c][idx].sum(axis=1)[ok] / den[ok], [2.5, 97.5])
        out[c] = {
            "count": int(counts[c].sum()),
            "share": float(point),
            "interval": [float(lo), float(hi)],
        }
    return out


def by_document(traces, with_index):
    out = {}
    for doc in sorted({t["document"] for t in traces.values()}):
        sub = {k: v for k, v in traces.items() if v["document"] == doc}
        flags = [stage_flags(t, with_index)[0] for t in sub.values()]
        out[doc] = {
            "obligations": len(sub),
            **{s: sum(f[s] for f in flags) for s in flags[0]},
            "losses": loss_table(sub),
        }
    return out


def paired_difference(trace_a, trace_b, stage, resamples=RESAMPLES, seed=BOOT_SEED):
    """Recall(a) - recall(b) at a stage on the same pieces, with a page-level bootstrap interval, plus the pieces only a or
    only b covers. The counts matter because gains and losses on one page cancel in the page-level interval."""
    ids = sorted(set(trace_a) & set(trace_b))
    pages = sorted({(trace_a[i]["document"], trace_a[i]["page"]) for i in ids})
    pos = {p: k for k, p in enumerate(pages)}
    n = np.zeros(len(pages))
    da = np.zeros(len(pages))
    db = np.zeros(len(pages))
    only_a = only_b = 0
    for i in ids:
        k = pos[(trace_a[i]["document"], trace_a[i]["page"])]
        n[k] += 1
        fa, fb = (stage_flags(t[i], False)[0][stage] for t in (trace_a, trace_b))
        da[k] += fa
        db[k] += fb
        only_a += fa and not fb
        only_b += fb and not fa
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pages), size=(resamples, len(pages)))
    den = n[idx].sum(axis=1)
    ok = den > 0
    diff = (da[idx].sum(axis=1)[ok] - db[idx].sum(axis=1)[ok]) / den[ok]
    lo, hi = np.percentile(diff, [2.5, 97.5])
    return {
        "difference": float((da.sum() - db.sum()) / n.sum()),
        "interval": [float(lo), float(hi)],
        "n": int(n.sum()),
        "only_first_covers": int(only_a),
        "only_second_covers": int(only_b),
    }


def density(index, final, labels):
    per_doc = collections.defaultdict(lambda: collections.Counter())
    pages = collections.defaultdict(set)
    for pid, r in final.items():
        d = index[pid]["document"]
        per_doc[d][r["label"]] += 1
        pages[d].add(index[pid]["page"])
    return {
        d: {"pages": len(pages[d]), "pieces": sum(c.values()), **dict(c)}
        for d, c in per_doc.items()
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sheet")
    sp.add_argument("--labels-dir", required=True)
    sp.add_argument("--out", required=True)
    rp = sub.add_parser("report")
    rp.add_argument("--labels-dir", required=True)
    rp.add_argument("--answers", required=True)
    rp.add_argument("--out-dir", required=True)
    rp.add_argument("--scratch", default=str(SCRATCH))
    rp.add_argument(
        "--no-index",
        action="store_true",
        help="skip the live Qdrant read (production then stops at Step D)",
    )
    args = ap.parse_args()

    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    index = piece_index(frozen)
    labels = load_labels(args.labels_dir)
    missing = [w for w in LABELERS if len(labels[w]) != len(index)]
    if missing:
        sys.exit(f"label files incomplete for {missing}")
    if args.cmd == "sheet":
        Path(args.out).write_text(sheet(labels, index), encoding="utf-8")
        print(
            f"{len(disagreements(labels))} disagreements, {len(spot_checks(labels))} spot-checks -> {args.out}"
        )
        return

    from core import config as _config
    from _inputs import corpus_inputs

    final = resolve(labels, parse_answers(Path(args.answers).read_text(encoding="utf-8")))
    sets = label_sets(labels, final)
    flagged = {i for i, r in final.items() if r["flagged"]}
    inputs = corpus_inputs("chunks", "extracted", "normalized")
    docs = frozen["documents"]
    production_runs = {d: load_run(inputs[d]["chunks"].parent, d) for d in docs}
    indexed = None if args.no_index else live_ids(_config.load().qdrant_url)
    sanity = {}
    for d, run in production_runs.items():
        normalized_ids = {r["requirement_id"] for r in run["normalized"]}
        sanity[d] = {
            "chunks": len(run["chunk_tokens"]),
            "step_c_records": len(run["extracted"]),
            "step_d_survivors": len(normalized_ids),
            "survivors_in_live_index": None if indexed is None else len(normalized_ids & indexed),
        }
        if indexed is not None and not normalized_ids & indexed:
            sys.exit(
                f"{d}: none of the Step D survivors is in the live index; the id join is wrong"
            )
    out = {
        "frozen_pieces_sha256": frozen["pieces_sha256"],
        "label_counts": {
            who: dict(collections.Counter(r["label"] for r in labels[who].values()))
            for who in LABELERS
        },
        "agreement": {"pieces": len(index), "disagreements": len(disagreements(labels))},
        "obligations": {k: len(v) for k, v in sets.items()},
        "segmentation_flagged_pieces": len(flagged),
        "sanity": sanity,
        "density": density(index, final, labels),
        "views": {},
        "secondary": {},
    }
    traces_by_view = {}
    for view, ids in sets.items():
        primary_ids = ids - flagged
        traces = trace_all(primary_ids, index, production_runs, indexed)
        traces_by_view[view] = traces
        out["views"][view] = {
            "production": {
                "obligations": len(traces),
                "recall": page_bootstrap(traces, indexed is not None),
                "losses": loss_table(traces),
                "loss_shares": loss_bootstrap(traces),
                "by_document": by_document(traces, indexed is not None),
            }
        }
    # including the pieces someone flagged as badly cut
    all_traces = trace_all(sets["adjudicated"], index, production_runs, indexed)
    out["views"]["adjudicated"]["production_including_flagged"] = {
        "obligations": len(all_traces),
        "recall": page_bootstrap(all_traces, indexed is not None),
        "losses": loss_table(all_traces),
    }
    # fresh 8B and the 14B: same pieces, steps 1 to 3 only (never indexed)
    primary_ids = sets["adjudicated"] - flagged
    model_traces = {"production_8b_july": traces_by_view["adjudicated"]}
    for tag in ("llama3.1_8b-instruct-q4_K_M", "qwen2.5_14b"):
        runs = {d: load_run(Path(args.scratch) / tag / d, d) for d in docs}
        tr = trace_all(primary_ids, index, runs, None)
        model_traces[tag] = tr
        out["secondary"][tag] = {
            "obligations": len(tr),
            "recall": page_bootstrap(tr, False),
            "losses": loss_table(tr),
            "loss_shares": loss_bootstrap(tr),
            "by_document": by_document(tr, False),
        }
    out["paired"] = {}
    prod = model_traces["production_8b_july"]
    for tag in ("llama3.1_8b-instruct-q4_K_M", "qwen2.5_14b"):
        out["paired"][f"{tag}_minus_production"] = {
            s: paired_difference(model_traces[tag], prod, s)
            for s in ("extracted", "survived_step_d")
        }
    out["paired"]["qwen2.5_14b_minus_fresh_8b"] = {
        s: paired_difference(
            model_traces["qwen2.5_14b"], model_traces["llama3.1_8b-instruct-q4_K_M"], s
        )
        for s in ("extracted", "survived_step_d")
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    with open(out_dir / "traces.jsonl", "w", encoding="utf-8") as f:
        for name, tr in model_traces.items():
            for pid, t in sorted(tr.items()):
                f.write(json.dumps({"run": name, "piece": pid, **t}, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "obligations": out["obligations"],
                "views": {v: out["views"][v]["production"]["recall"] for v in out["views"]},
            },
            indent=1,
        )[:3000]
    )


if __name__ == "__main__":
    main()
