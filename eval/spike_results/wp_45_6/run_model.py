"""WP-45.6: run Step C and Step D for one pinned document with one extraction model, into a scratch directory.

Measurement only. Nothing is written to ~/documents/processed, to Qdrant, or to the repo. The pinned inputs (chunks, and for
the baseline the 8B's extracted records) are verified against the WP-44 manifest and copied; the existing pipeline is then run
unchanged on the copy.

  --stage C   copy the pinned chunks and run Step C (this model's extraction) + Step D + parent-stem reconstruction
  --stage D   copy the pinned chunks AND the pinned 8B extracted records and run Step D only, so the 8B baseline is judged by the
              SAME Step D rules as the new model (the pinned normalized files are from July and Step D has changed since)

Step D.5 enrichment and the D.6 gate are skipped (neither is compared and neither changes the quotes).

Run from the repo root, for example:
  python3 eval/spike_results/wp_45_6/run_model.py --doc "DODI 8410.03" --model qwen2.5:14b --stage C
"""

import argparse
import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _inputs import corpus_inputs  # noqa: E402

DEFAULT_SCRATCH = Path.home() / "reqbot-work/scratch/wp45_6_scratch"
BASELINE_MODEL = "llama3.1:8b-instruct-q4_K_M"


def model_tag(model):
    return model.replace(":", "_").replace("/", "_")


def poll_vram(ollama_url, model, samples, stop):
    """Sample /api/ps while the run goes: the largest size_vram seen for this model, in bytes."""
    while not stop.is_set():
        try:
            with urllib.request.urlopen(f"{ollama_url}/api/ps", timeout=5) as r:
                for m in json.load(r).get("models", []):
                    if m.get("name") == model or m.get("model") == model:
                        samples.append({"size": m.get("size"), "size_vram": m.get("size_vram")})
        except Exception:
            pass
        stop.wait(10)


def status_summary(raw_path):
    """Per-chunk completion states from Step C's raw_responses.jsonl. Token counts are not in the ledger (the pipeline does
    not persist them), so none are reported rather than zeros."""
    out = {
        "chunks": 0,
        "status": {},
        "done_reason": {},
        "prompt_hashes": [],
    }
    if not raw_path.exists():
        return out
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out["chunks"] += 1
        out["status"][r.get("status", "unknown")] = (
            out["status"].get(r.get("status", "unknown"), 0) + 1
        )
        dr = r.get("done_reason") or "n/a"
        out["done_reason"][dr] = out["done_reason"].get(dr, 0) + 1
        if r.get("prompt_hash") and r["prompt_hash"] not in out["prompt_hashes"]:
            out["prompt_hashes"].append(r["prompt_hash"])
    return out


def _positive_int(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be a positive integer")
    return n


def main():
    from core import config as _config

    cfg = _config.load()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--doc", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--stage", choices=("C", "D"), required=True)
    ap.add_argument("--scratch", default=str(DEFAULT_SCRATCH))
    ap.add_argument("--ollama-url", default=cfg.ollama_url)
    ap.add_argument(
        "--timeout",
        type=_positive_int,
        default=300,
        help="per-request timeout; the 8B baseline ran at 120",
    )
    ap.add_argument("--max-chunks", type=_positive_int, default=None)
    args = ap.parse_args()

    inputs = corpus_inputs("chunks", "extracted", "normalized")
    if args.doc not in inputs:
        sys.exit(f"{args.doc} is not one of the pinned documents")
    files = inputs[args.doc]
    pdf = _ROOT / "raw_pdfs" / f"{args.doc}.pdf"
    if not pdf.exists():
        sys.exit(f"source PDF not found: {pdf}")

    tag = "8b_current_stepD" if args.stage == "D" else model_tag(args.model)
    out_dir = Path(args.scratch) / tag / args.doc
    if out_dir.exists() and any(out_dir.iterdir()):
        sys.exit(
            f"{out_dir} is not empty; refusing to mix runs (delete it or choose another --scratch)"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(files["chunks"], out_dir / files["chunks"].name)
    if args.stage == "D":
        shutil.copy2(files["extracted"], out_dir / files["extracted"].name)
        raw = files["chunks"].parent / f"{args.doc}_raw_responses.jsonl"
        if raw.exists():
            shutil.copy2(raw, out_dir / raw.name)

    cmd = [
        sys.executable,
        str(_ROOT / "pipeline/run_pipeline.py"),
        str(pdf),
        "--output-dir",
        str(out_dir),
        "--skip-to",
        args.stage,
        "--extraction-model",
        args.model,
        "--enrichment-model",
        BASELINE_MODEL,
        "--skip-enrichment",
        "--skip-description-gate",
        "--ollama-url",
        args.ollama_url,
        "--timeout",
        str(args.timeout),
    ]
    if args.max_chunks:
        cmd += ["--max-chunks", str(args.max_chunks)]

    samples, stop = [], threading.Event()
    poller = None
    if args.stage == "C":
        poller = threading.Thread(
            target=poll_vram, args=(args.ollama_url, args.model, samples, stop), daemon=True
        )
        poller.start()
    started = time.time()
    with open(out_dir / "run.log", "w", encoding="utf-8") as log:
        proc = subprocess.run(cmd, cwd=_ROOT, stdout=log, stderr=subprocess.STDOUT)
    wall = time.time() - started
    stop.set()
    if poller:
        poller.join(timeout=15)  # the poller must be done before its samples are read

    digests = {}
    try:
        with urllib.request.urlopen(f"{args.ollama_url}/api/tags", timeout=10) as r:
            digests = {m["name"]: m.get("digest") for m in json.load(r).get("models", [])}
    except Exception:
        pass
    summary = status_summary(out_dir / f"{args.doc}_raw_responses.jsonl")
    record = {
        "doc": args.doc,
        "stage": args.stage,
        "model": args.model
        if args.stage == "C"
        else f"{args.model} (extraction pinned from July; Step D re-run now)",
        "model_digest": digests.get(args.model),
        "returncode": proc.returncode,
        "wall_seconds": round(wall, 1),
        "ollama_url": args.ollama_url,
        "timeout_seconds": args.timeout,
        "max_chunks": args.max_chunks,
        "step_c": summary if args.stage == "C" else None,
        "max_vram_bytes": max((s["size_vram"] or 0 for s in samples), default=None),
        "max_loaded_bytes": max((s["size"] or 0 for s in samples), default=None),
        "command": cmd[1:],
        "out_dir": str(out_dir),
    }
    (out_dir / "run_record.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k not in ("command",)}, indent=1))
    if proc.returncode:
        sys.exit(f"pipeline exited {proc.returncode}; see {out_dir / 'run.log'}")


if __name__ == "__main__":
    main()
