"""WP-45.8 Stage A failure drills (no model): each failure must end in "no change, flag only" -- never a crash and never a dropped record.

Drills: Ollama unreachable; an empty chunk; an oversize chunk (the bundle trims it to fit the window, so it is sent trimmed; against the dead server it ends as an abstain); a record with no chunk id; a record whose chunk is missing. Each runs the shadow
runner's own candidate builder, the frozen `run_candidates` and `shadow_rows` on a tiny synthetic corpus built from one real record, against an unreachable server.
"""

import copy
import tempfile
from pathlib import Path

import menu_v2 as M2
import ollama_run as OR
import run_selection as RS
import run_stage_c as RSC
import kind_selection as K

import shadow_run as SH

DEAD = "http://127.0.0.1:9"  # nothing listens here: connection refused


def _corpus(docs):
    """A tiny corpus from the first real document: its first record and chunk, then one variant per drill."""
    doc = next(iter(docs))
    info = docs[doc]
    rec = next(r for r in info["records"] if r.get("chunk_id") in info["chunks"])
    chunk = info["chunks"][rec["chunk_id"]]
    variants = {}

    def make(name, *, chunk_override=None, rec_override=None, drop_chunk=False):
        c = copy.deepcopy(chunk)
        if chunk_override:
            c.update(chunk_override)
        r = {**copy.deepcopy(rec), "requirement_id": f"drill-{name}", **(rec_override or {})}
        chunks = {} if drop_chunk else {c["chunk_id"]: c}
        variants[name] = {"chunks": chunks, "step": {}, "records": [r], "dir": "synthetic"}

    make("ollama_unreachable")
    make("empty_chunk", chunk_override={"text": "", "raw_text": ""})
    make("oversize_chunk", chunk_override={"text": chunk["text"] + (" lorem ipsum" * 20000), "raw_text": chunk["raw_text"] + (" lorem ipsum" * 20000)})
    make("no_chunk_id", rec_override={"chunk_id": None})
    make("chunk_missing", drop_chunk=True)
    return doc, variants


def run_all():
    docs = SH.load_source("processed")
    doc, variants = _corpus(docs)
    frozen = SH.SR.frozen_choice(SH.REGISTRY)
    results = {}
    for name, info in variants.items():
        corpus = {doc: info}
        cands, skipped = SH.candidates_from(corpus)
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "resolver.jsonl"
            ledger = OR.Ledger(ledger_path)
            crashed = None
            try:
                with RSC._menu_module(M2):
                    RS.run_candidates(cands, {doc: (info["chunks"], info["step"])}, tier=frozen["tier"], model=frozen["model"], digest="drill", run_label="drill",
                                      ledger=ledger, ollama_url=DEAD, num_ctx=int(frozen["num_ctxs"][0]), num_predict=int(frozen["num_predicts"][0]),
                                      temperature=float(frozen["temperatures"][0]), log=lambda *a: None, design=K, timeout=5)
            except Exception as e:  # noqa: BLE001
                crashed = repr(e)
            rows = SH.shadow_rows(corpus, ledger_path)
        results[name] = {
            "crashed": crashed, "input_records": len(info["records"]), "output_rows": len(rows),
            "flag": rows[0]["flag"] if rows else None, "resolver_string": rows[0]["resolver_string"] if rows else None,
            "no_change_flag_only": crashed is None and len(rows) == len(info["records"]) and bool(rows[0]["flag"]) and rows[0]["resolver_string"] == "",
        }
    # the server is down when the run starts: the real `run` must still finish, write nothing but flags, and drop no record
    with tempfile.TemporaryDirectory() as tmp:
        info = SH.run("processed", "drill_unavailable", DEAD, scratch=tmp, log=lambda *a: None)
        rows = SH.shadow_rows(docs, Path(tmp) / "drill_unavailable" / "resolver.jsonl", bool(info.get("resolver_unavailable")))
    total = sum(len(i["records"]) for i in docs.values())
    results["unreachable_at_start"] = {"input_records": total, "output_rows": len(rows), "calls_made": info["calls_made"],
                                       "flags": sorted({r["flag"] for r in rows}),
                                       "no_change_flag_only": len(rows) == total and info["calls_made"] == 0 and all(r["flag"] and not r["resolver_string"] for r in rows)}
    results["all_pass"] = all(v["no_change_flag_only"] for k, v in results.items() if k != "all_pass")
    return results
