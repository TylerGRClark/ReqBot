#!/usr/bin/env python3
"""PREREG12: build a throwaway requirements collection (idxtest_*) from the newest run folder of every document.

Arms (the only difference is the text that is embedded and BM25-indexed; payload is the production payload):
  control : pipeline.embed_and_index.build_embedding_text unchanged
  head    : "Section: <section_title_path joined with ' > '>" line in front of the control text
  head1   : "Section: <last entry of section_title_path>" line in front of the control text
A row with an empty section_title_path is embedded exactly as in control.
Never touches grc_requirements / grc_context: refuses any collection name that does not start with idxtest_.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from pipeline import embed_and_index as EI  # noqa: E402
from idx_cut_gold import newest_normalized  # noqa: E402

_orig = EI.build_embedding_text


def heading_of(req: dict, arm: str) -> str:
    path = [p.strip() for p in (req.get("section_title_path") or []) if p and p.strip()]
    if not path or arm == "control":
        return ""
    return " > ".join(path) if arm == "head" else path[-1]


def make_builder(arm: str):
    def build(req: dict):
        base = _orig(req)
        if base is None:
            return None
        h = heading_of(req, arm)
        return f"Section: {h}\n{base}" if h else base
    return build


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["control", "head", "head1"])
    ap.add_argument("--processed", default=str(Path.home() / "documents" / "processed"))
    ap.add_argument("--out-dir", help="write build_<arm>.json (build_seconds) here for the report's cost gate")
    ap.add_argument("--delete", action="store_true", help="delete idxtest_<arm> and exit")
    a = ap.parse_args()
    from core import config
    cfg = config.load()
    name = f"idxtest_{a.arm}"
    assert name.startswith("idxtest_")
    from qdrant_client import QdrantClient
    qc = QdrantClient(url=cfg.qdrant_url)
    if a.delete:
        if qc.collection_exists(name):
            qc.delete_collection(name)
        print("deleted", name)
        return
    EI.build_embedding_text = make_builder(a.arm)
    t0 = time.time()
    first = True
    total = 0
    for key, (_, f) in sorted(newest_normalized(a.processed).items()):
        total += EI.run(f, qdrant_url=cfg.qdrant_url, ollama_url=cfg.ollama_url, recreate=first,
                        collection_name=name, payload_extras=EI.derived_payload_fields(f))
        first = False
    secs = time.time() - t0
    n = qc.get_collection(name).points_count
    rec = {"arm": a.arm, "collection": name, "indexed": total, "points": n, "build_seconds": round(secs, 1)}
    if a.out_dir:
        Path(a.out_dir, f"build_{a.arm}.json").write_text(json.dumps(rec))
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
