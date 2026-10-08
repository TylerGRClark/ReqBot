#!/usr/bin/env python3
"""WP-45.8 Stage A: run the frozen selection resolver over every record of a processed corpus, into a scratch directory only (docs/PHASE45_WP458_PLAN.md section 3).

  python3 shadow_run.py run    --source processed            # newest run of each document under ~/documents/processed
  python3 shadow_run.py run    --source arm:T2a              # the scratch arm ~/wp45_11_scratch/T2a/<document>/
  python3 shadow_run.py report --source processed            # counts, routes, seeded sample, substring gate -> outputs/
  python3 shadow_run.py rerun  --source processed            # the seeded 200-record determinism rerun
  python3 shadow_run.py drills                               # failure drills (no model needed)

Nothing here writes to the pipeline, the Step C cache, any `*_requirements_*.jsonl`, Qdrant or the repository's data: the ledger, the shadow output and the report go
to `~/wp45_8_scratch/<label>/` (outputs/ in this folder holds only the small committed reports). The resolver is the one frozen in WP-45.7e, unchanged: menu_v2,
kind prompt, tier R2, model, digest and inference parameters come from the frozen choice, and every pinned resolver file is checked against the frozen manifest.

The string that would be attached is fixed by the plan, before any retrieval measure: the chosen actor span and the chosen parent span (each verbatim), joined with " | "
when both exist; empty when neither.
"""

import argparse
import collections
import hashlib
import json
import random
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
W7 = _ROOT / "eval/spike_results/wp_45_7"
for _p in (_HERE, W7, _ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bundle as B  # noqa: E402
import kind_selection as K  # noqa: E402
import menu_v2 as M2  # noqa: E402
import ollama_run as OR  # noqa: E402
import run_selection as RS  # noqa: E402
import run_stage_c as RSC  # noqa: E402
import score_resolver as SR  # noqa: E402

SCRATCH = Path.home() / "wp45_8_scratch"
PROCESSED = Path.home() / "documents" / "processed"
REGISTRY = "v6"
# Files that may differ from the frozen manifest, each with the reason checked below. pipeline/chunk_text.py was changed by the merged T2 table fix (#249):
# the resolver's import closure uses only `_normalize_heading` from it (through parse_and_normalize), whose text is unchanged.
ALLOWED_DRIFT = {"pipeline/chunk_text.py": "_normalize_heading"}
DETERMINISM_SIZE, SAMPLE_SIZE, SEED = 200, 40, 45


def attach_string(actor, parent):
    """The fixed Stage B string: actor span and parent span joined with " | " when both exist, one when one exists, empty when neither."""
    return " | ".join(x for x in ((actor or "").strip(), (parent or "").strip()) if x)


def check_code():
    """The frozen manifest check of WP-45.7e, except for the declared drift. Returns the list of drifted files; raises SystemExit for any other difference."""
    manifest = json.loads((W7 / "outputs" / SR.FROZEN_CODE[REGISTRY]).read_text(encoding="utf-8"))
    pinned = {**manifest["files"], **manifest.get("sealed_until_c2", {})}
    drifted = [rel for rel, want in pinned.items()
               if (not (_ROOT / rel).exists()) or hashlib.sha256((_ROOT / rel).read_bytes()).hexdigest() != want]
    unexpected = [rel for rel in drifted if rel not in ALLOWED_DRIFT]
    if unexpected:
        raise SystemExit(f"resolver files differ from the frozen manifest: {unexpected}")
    if drifted:
        import re
        import subprocess

        freeze = subprocess.run(["git", "log", "--format=%H", "-n", "1", "--", "eval/spike_results/wp_45_7/outputs/" + SR.FROZEN_CODE[REGISTRY]],
                                cwd=_ROOT, capture_output=True, text=True).stdout.strip()
        for rel, func in ALLOWED_DRIFT.items():
            pat = re.compile(rf"^def {func}\(.*?(?=^def |\Z)", re.S | re.M)
            then = pat.search(subprocess.run(["git", "show", f"{freeze}:{rel}"], cwd=_ROOT, capture_output=True, text=True).stdout)
            now = pat.search((_ROOT / rel).read_text(encoding="utf-8"))
            if not (then and now and then.group(0) == now.group(0)):
                raise SystemExit(f"{rel}: {func} differs from the frozen version; the resolver's behaviour may have changed")
    return drifted


def newest_runs(root=PROCESSED):
    """{document: run directory}: the newest timestamped directory of each document (names are <document>_<YYYYMMDD>_<HHMMSS>)."""
    best = {}
    for d in sorted(Path(root).iterdir()):
        if d.is_dir() and d.name.count("_") >= 2:
            doc, day, clock = d.name.rsplit("_", 2)
            if day.isdigit() and clock.isdigit() and (doc not in best or d.name > best[doc].name):
                best[doc] = d
    return best


def _lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()] if Path(path).exists() else []


def load_source(source):
    """{document: {"chunks": {chunk_id: chunk}, "step": {chunk_id: [Step C records]}, "records": [final records], "dir": path}} for a source."""
    if source == "processed":
        if not PROCESSED.is_dir():
            raise SystemExit(f"{PROCESSED} does not exist: nothing to shadow")
        dirs = newest_runs()
    elif source.startswith("arm:"):
        name = source[4:]
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise SystemExit("--source arm:NAME takes a plain arm name")
        base = Path.home() / "wp45_11_scratch" / name
        if not base.is_dir():
            raise SystemExit(f"{base} does not exist")
        dirs = {d.name: d for d in sorted(base.iterdir()) if d.is_dir()}
    else:
        raise SystemExit("--source is 'processed' or 'arm:NAME'")
    out = {}
    for doc, d in sorted(dirs.items()):
        chunks = {c["chunk_id"]: c for c in _lines(d / f"{doc}_chunks.jsonl")}
        records = _lines(d / f"{doc}_requirements_enriched.jsonl") or _lines(d / f"{doc}_requirements_normalized.jsonl")
        step = {}
        for r in _lines(d / f"{doc}_extracted_requirements.jsonl"):
            step.setdefault(r.get("chunk_id"), []).append(r)
        if records:
            out[doc] = {"chunks": chunks, "step": step, "records": records, "dir": str(d)}
    if not out:
        raise SystemExit(f"no document with records found for --source {source}")
    return out


def candidates_from(docs):
    """(candidates, skipped): one candidate per record that has a chunk to read; a record without a chunk id, or whose chunk is missing or empty, is not sent and is
    reported with the reason (it still appears in the shadow output, flagged)."""
    cands, skipped = [], []
    for doc, info in docs.items():
        for rec in info["records"]:
            rid, cid, quote = rec.get("requirement_id"), rec.get("chunk_id"), rec.get("source_quote") or ""
            why = ("no chunk id" if cid is None else "chunk not found" if cid not in info["chunks"] else
                   "empty chunk" if not (info["chunks"][cid].get("text") or info["chunks"][cid].get("raw_text")) else "no quote" if not quote.strip() else None)
            if why:
                skipped.append({"document": doc, "requirement_id": rid, "reason": why})
            else:
                cands.append({"candidate_id": rid, "document": doc, "chunk_id": cid, "quote": quote})
    return cands, skipped


def snapshot(docs):
    """{document: {dir, chunks_sha256, records_sha256, step_sha256}}: which input files a run read, so a report can refuse to join a ledger to different inputs."""
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None  # noqa: E731
    out = {}
    for doc, info in docs.items():
        d = Path(info["dir"])
        records = d / f"{doc}_requirements_enriched.jsonl"
        out[doc] = {"dir": str(d), "chunks_sha256": sha(d / f"{doc}_chunks.jsonl"),
                    "records_sha256": sha(records if records.exists() else d / f"{doc}_requirements_normalized.jsonl"),
                    "step_sha256": sha(d / f"{doc}_extracted_requirements.jsonl")}
    return out


def check_snapshot(docs, label, scratch=SCRATCH):
    """Refuse to report on a ledger whose inputs are not the ones the run read."""
    info = json.loads((Path(scratch) / label / "run_info.json").read_text(encoding="utf-8"))
    have, want = snapshot(docs), info.get("sources")
    if want is None or have != want:
        changed = sorted(d for d in set(have) | set(want or {}) if (want or {}).get(d) != have.get(d))
        raise SystemExit(f"the input files changed since {label} was run (or were not recorded): {changed}; re-run, do not join a ledger to other inputs")


def run(source, label, ollama_url, limit_ids=None, scratch=SCRATCH, log=print):
    drift = check_code()
    frozen = SR.frozen_choice(REGISTRY)
    docs = load_source(source)
    cands, skipped = candidates_from(docs)
    if limit_ids is not None:
        cands = [c for c in cands if c["candidate_id"] in limit_ids]
    out = Path(scratch) / label
    out.mkdir(parents=True, exist_ok=True)
    info = {"label": label, "source": source, "sources": snapshot(docs), "drifted_files_allowed": drift,
            "records": sum(len(i["records"]) for i in docs.values()), "candidates": len(cands), "not_sent": skipped,
            "model": frozen["model"], "tier": frozen["tier"], "prompt_hash": K.prompt_hash()}
    try:
        digest = OR.model_digest(ollama_url, frozen["model"])
    except Exception as e:  # noqa: BLE001  (server unreachable or model absent: no change, flag only -- every record keeps its production stem)
        info.update(digest=None, resolver_unavailable=repr(e), calls_made=0, wall_seconds=0)
        (out / "run_info.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
        log(f"resolver unavailable: {e!r}; no calls made, every record will be flagged")
        return info
    if digest != frozen["digest"]:
        raise SystemExit(f"the model file differs from the frozen one: {digest!r} against {frozen['digest']!r}")
    ledger = RSC._StampedLedger(out / "resolver.jsonl", RSC.menu_identity(REGISTRY))
    started = time.time()
    by_doc = {d: (i["chunks"], i["step"]) for d, i in docs.items()}
    with RSC._menu_module(M2):
        calls = RS.run_candidates(cands, by_doc, tier=frozen["tier"], model=frozen["model"], digest=digest, run_label=label, ledger=ledger,
                                  ollama_url=ollama_url, num_ctx=int(frozen["num_ctxs"][0]), num_predict=int(frozen["num_predicts"][0]),
                                  temperature=float(frozen["temperatures"][0]), log=log, design=K)
    info.update(calls_made=calls, wall_seconds=round(time.time() - started, 1), digest=digest)
    (out / "run_info.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    return info


def shadow_rows(docs, ledger_path, unavailable=False):
    """One row per input record, in input order: the production stem, the resolver's answer (or why it abstained) and the string that would be attached."""
    ledger = {}
    for rec in _lines(ledger_path):
        ledger[(rec["document"], rec["candidate_id"])] = rec
    cands, skipped = candidates_from(docs)
    reason = {(s["document"], s["requirement_id"]): s["reason"] for s in skipped}
    rows = []
    for doc, info in docs.items():
        for rec in info["records"]:
            key = (doc, rec.get("requirement_id"))
            row = {"document": doc, "requirement_id": rec.get("requirement_id"), "chunk_id": rec.get("chunk_id"), "production_stem": rec.get("parent_stem") or "",
                   "resolver_string": "", "kind": None, "strength": None, "actor": "", "parent": "", "flag": None}
            led = ledger.get(key)
            if key in reason:
                row["flag"] = f"not sent: {reason[key]}"
            elif led is None:
                row["flag"] = "resolver unavailable" if unavailable else "no ledger entry"
            elif led["status"] != "complete" or not led.get("answer"):
                row["flag"] = f"resolver abstained: {led['status']}"
            else:
                ans = led["answer"]
                row.update(kind=(led.get("selection") or {}).get("kind"), strength=ans["status"]["value"], actor=ans["actor"]["value"] or "",
                           parent=ans["parent"]["value"] or "")
                row["resolver_string"] = attach_string(row["actor"], row["parent"])
                if any(i["severity"] == "error" for i in led.get("issues", [])):
                    row["flag"] = "checker error"
            rows.append(row)
    return rows


def route(row):
    p, r = bool(row["production_stem"].strip()), bool(row["resolver_string"].strip())
    if row["flag"] and not r:
        return "no resolver answer"
    if not p and r:
        return "production none -> resolver some"
    if p and not r:
        return "production some -> resolver none"
    if p and r:
        return "same" if B.normalize(row["production_stem"]).lower() == B.normalize(row["resolver_string"]).lower() else "both some, different"
    return "both none"


def substring_failures(rows, docs):
    """Spans the resolver returned that are not a substring (after the resolver's own normalization) of any text of the document's chunks."""
    bad = []
    haystack = {}
    for doc, info in docs.items():
        parts = []
        for c in info["chunks"].values():
            parts += [c.get("text") or "", c.get("raw_text") or "", c.get("breadcrumb") or ""]
            parts += [str(c.get(k) or "") for k in ("parent_header_text", "parent_context")]
        haystack[doc] = B.normalize(" \n ".join(parts))
    for row in rows:
        for name in ("actor", "parent"):
            span = row[name]
            if span and B.normalize(span) not in haystack[row["document"]]:
                bad.append({"document": row["document"], "requirement_id": row["requirement_id"], "field": name, "span": span})
    return bad


def report(source, label, scratch=SCRATCH):
    docs = load_source(source)
    check_snapshot(docs, label, scratch)
    out = Path(scratch) / label
    unavailable = bool(json.loads((out / "run_info.json").read_text(encoding="utf-8")).get("resolver_unavailable"))
    rows = shadow_rows(docs, out / "resolver.jsonl", unavailable)
    n_in = sum(len(i["records"]) for i in docs.values())
    routes = collections.Counter(route(r) for r in rows)
    kinds = collections.Counter(r["kind"] or "none" for r in rows)
    not_requirement = sum(1 for r in rows if r["kind"] not in (None, "requirement"))
    ledger = _lines(out / "resolver.jsonl")
    secs = [r["meta"].get("wall_seconds") for r in ledger if r.get("meta") and r["meta"].get("wall_seconds")]
    changed = [r for r in rows if route(r) in ("production none -> resolver some", "both some, different", "production some -> resolver none")]
    sample = sorted(random.Random(SEED).sample(changed, min(SAMPLE_SIZE, len(changed))), key=lambda r: (r["document"], r["requirement_id"]))
    bad = substring_failures(rows, docs)
    summary = {
        "source": source, "label": label, "documents": len(docs), "input_records": n_in, "output_rows": len(rows), "dropped_records": n_in - len(rows),
        "calls_in_ledger": len(ledger), "statuses": dict(collections.Counter(r["status"] for r in ledger)),
        "seconds_per_call_mean": round(sum(secs) / len(secs), 2) if secs else None, "seconds_total": round(sum(secs), 1),
        "with_resolver_string": sum(bool(r["resolver_string"]) for r in rows), "kinds": dict(kinds), "kind_other_than_requirement": not_requirement, "flags": dict(collections.Counter(r["flag"] or "none" for r in rows)),
        "no_menu": sum(1 for r in ledger if r.get("menu") == []), "routes_vs_production": dict(routes),
        "span_not_in_document": len(bad), "gate": {"zero_dropped_records": n_in == len(rows), "zero_spans_outside_document": not bad},
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "shadow_output.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return summary, sample, bad


def determinism(source, base_label, ollama_url, scratch=SCRATCH, log=print):
    """Re-run a seeded 200-record sample under a new label and list every answer that differs from the first run."""
    rows = [r for r in _lines(Path(scratch) / base_label / "shadow_output.jsonl") if not (r["flag"] or "").startswith("not sent")]
    picked = sorted(random.Random(SEED).sample(rows, min(DETERMINISM_SIZE, len(rows))), key=lambda r: (r["document"], r["requirement_id"]))
    ids = {r["requirement_id"] for r in picked}
    check_snapshot(load_source(source), base_label, scratch)
    label = base_label + "_rerun"
    run(source, label, ollama_url, limit_ids=ids, scratch=scratch, log=log)
    docs = load_source(source)
    second = {(r["document"], r["requirement_id"]): r for r in shadow_rows(docs, Path(scratch) / label / "resolver.jsonl")}
    differ = []
    for r in picked:
        s = second[(r["document"], r["requirement_id"])]
        if (r["kind"], r["actor"], r["parent"], r["flag"]) != (s["kind"], s["actor"], s["parent"], s["flag"]):
            differ.append({"document": r["document"], "requirement_id": r["requirement_id"], "first": [r["kind"], r["actor"], r["parent"], r["flag"]],
                           "second": [s["kind"], s["actor"], s["parent"], s["flag"]]})
    return {"sample": len(picked), "identical": len(picked) - len(differ), "different": len(differ), "differences": differ}


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("run", "report", "rerun", "drills"))
    ap.add_argument("--source", default="processed")
    ap.add_argument("--label")
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--scratch", default=str(SCRATCH))
    args = ap.parse_args()
    label = args.label or "wp458_shadow_" + args.source.replace(":", "_")
    if args.cmd == "run":
        print(json.dumps(run(args.source, label, args.ollama_url, scratch=args.scratch), indent=1))
    elif args.cmd == "report":
        summary, sample, bad = report(args.source, label, args.scratch)
        (_HERE / "outputs").mkdir(exist_ok=True)
        (_HERE / "outputs" / f"{label}_report.json").write_text(json.dumps({"summary": summary, "sample_of_changed_records": sample, "spans_not_in_document": bad}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=1))
    elif args.cmd == "rerun":
        res = determinism(args.source, label, args.ollama_url, args.scratch)
        (_HERE / "outputs").mkdir(exist_ok=True)
        (_HERE / "outputs" / f"{label}_determinism.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in res.items() if k != "differences"}, indent=1))
    else:
        import drills
        print(json.dumps(drills.run_all(), indent=1))


if __name__ == "__main__":
    main()
