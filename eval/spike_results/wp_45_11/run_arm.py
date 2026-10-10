#!/usr/bin/env python3
"""WP-45.11: run one arm (Step C, Step D, parent-stem reconstruction) on a set of chunk files, into a fresh scratch directory (no LLM changes, no production writes).

  python3 run_arm.py --arm B0a --chunks d2.94.0:256
  python3 run_arm.py --arm T1  --chunks d2.122.0-core2.100.0:default
  python3 run_arm.py --arm B0a --chunks d2.94.0:256 --docs "DODI 8410.03" --max-chunks 3      # a smoke test

`--chunks TAG:LABEL` names the chunk files written by `wp_45_10/rechunk.py` (`~/reqbot-work/scratch/wp45_10_cache/TAG/chunks/LABEL/<doc>_chunks.jsonl`). Each document is copied into
`~/reqbot-work/scratch/wp45_11_scratch/<arm>/<doc>/` and the existing pipeline is run unchanged with `--skip-to C`, so arms differ only in the chunk files. The 13 pinned PDFs are
hash-checked; every run records the chunk file hash, the Docling package versions of the chunk cache, the model digest, the command and the Step C status counts.
An arm directory that already holds a document is never reused.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_10", _ROOT / "eval/spike_results/wp_45_6"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import common  # noqa: E402  (wp_45_10: pinned documents, PDF hashes, cache location)
from run_model import status_summary  # noqa: E402  (wp_45_6: Step C completion counts from raw_responses.jsonl)

SCRATCH = Path.home() / "reqbot-work/scratch/wp45_11_scratch"
MODEL = "llama3.1:8b-instruct-q4_K_M"


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chunk_dir(spec):
    tag, _, label = spec.partition(":")
    if not tag or not label:
        raise SystemExit(f"--chunks is TAG:LABEL, for example d2.94.0:256; got {spec!r}")
    return tag, label, common.CACHE / tag / "chunks" / label


def run_doc(arm, doc, spec, model, ollama_url, timeout, max_chunks, scratch=SCRATCH):
    tag, label, source = chunk_dir(spec)
    chunks = source / f"{doc}_chunks.jsonl"
    if not chunks.exists():
        raise SystemExit(f"{chunks} does not exist")
    out_dir = Path(scratch) / arm / doc
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"{out_dir} is not empty; arms never reuse a directory")
    out_dir.mkdir(parents=True)
    shutil.copy2(chunks, out_dir / chunks.name)
    pdf = common.pdf_path(doc)
    cmd = [sys.executable, str(_ROOT / "pipeline/run_pipeline.py"), str(pdf), "--output-dir", str(out_dir), "--skip-to", "C", "--extraction-model", model,
           "--enrichment-model", MODEL, "--skip-enrichment", "--skip-description-gate", "--ollama-url", ollama_url, "--timeout", str(timeout)]
    if max_chunks:
        cmd += ["--max-chunks", str(max_chunks)]
    started = time.time()
    with open(out_dir / "run.log", "w", encoding="utf-8") as log:
        proc = subprocess.run(cmd, cwd=_ROOT, stdout=log, stderr=subprocess.STDOUT)
    digest = None
    try:
        with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=10) as r:
            digest = {m["name"]: m.get("digest") for m in json.load(r).get("models", [])}.get(model)
    except Exception:
        pass
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True).stdout.strip() or None
    record = {"git_head": head, "arm": arm, "doc": doc, "chunks_spec": spec, "chunks_sha256": sha256_file(chunks), "chunk_manifest": common.read_manifest("chunks", label, tag),
              "docs_manifest": common.read_manifest("docs", "baseline", tag), "model": model, "model_digest": digest, "returncode": proc.returncode,
              "wall_seconds": round(time.time() - started, 1), "max_chunks": max_chunks, "step_c": status_summary(out_dir / f"{doc}_raw_responses.jsonl"),
              "command": cmd[1:]}
    (out_dir / "arm_record.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return record


def main():
    from core import config as _config
    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", required=True)
    ap.add_argument("--chunks", required=True, help="TAG:LABEL of the chunk files")
    ap.add_argument("--docs", nargs="*")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument("--timeout", type=int, default=120, help="per-request timeout; the 8B baseline ran at 120")
    ap.add_argument("--max-chunks", type=int)
    ap.add_argument("--scratch", default=str(SCRATCH))
    args = ap.parse_args()
    problems = common.verify_pdfs()
    if problems:
        sys.exit("source PDFs differ from the pinned corpus:\n  " + "\n  ".join(problems))
    for doc in args.docs or sorted(common.pinned_documents()):
        rec = run_doc(args.arm, doc, args.chunks, args.model, args.ollama_url, args.timeout, args.max_chunks, scratch=args.scratch)
        print(doc, "rc", rec["returncode"], f"{rec['wall_seconds']}s", rec["step_c"]["status"], flush=True)
        if rec["returncode"]:
            sys.exit(f"pipeline exited {rec['returncode']} for {doc}; see {Path(args.scratch) / args.arm / doc / 'run.log'}")


if __name__ == "__main__":
    main()
