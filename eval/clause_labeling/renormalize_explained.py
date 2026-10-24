#!/usr/bin/env python3
"""PREREG10 measurement 1 (no model): rebuild only the explained layer of existing requirement rows, with or without the heading lead-in, into scratch copies of the run folders.

    python3 eval/clause_labeling/renormalize_explained.py --src DIR --out DIR --arm control|heading

Each `<doc>_<timestamp>` folder under --src is copied to --out/<arm>/ and its `*_requirements_normalized.jsonl` gets new explained_text / explained_parts / explain_notes from
pipeline.sentence_expand.explain_records, called the way pipeline/parse_and_normalize.py calls it. Labels, roots (source_quote) and anchors are not touched. `control` switches the
heading rule off (monkeypatch), so it reproduces the rows as the current main builds them.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from pipeline import lead_in, sentence_expand  # noqa: E402


def renormalize(folder: Path, arm: str) -> dict:
    (norm_path,) = folder.glob("*_requirements_normalized.jsonl")
    (chunks_path,) = folder.glob("*_chunks.jsonl")
    chunks = [json.loads(ln) for ln in open(chunks_path, encoding="utf-8") if ln.strip()]
    raw = {c["chunk_id"]: c.get("raw_text") or c.get("text") or "" for c in chunks}
    sec = {c["chunk_id"]: (tuple(c.get("section_ref_path") or ()), tuple(c.get("section_title_path") or ())) for c in chunks}
    recs = [json.loads(ln) for ln in open(norm_path, encoding="utf-8") if ln.strip()]
    saved = lead_in.heading_lead_in
    if arm == "control":
        lead_in.heading_lead_in = lambda path: None
    try:
        new, counts = sentence_expand.explain_records(recs, raw, sec)
    finally:
        lead_in.heading_lead_in = saved
    norm_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in new), encoding="utf-8")
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", required=True, choices=["control", "heading"])
    a = ap.parse_args()
    dst_root = Path(a.out).expanduser() / a.arm
    for folder in sorted(p for p in Path(a.src).expanduser().iterdir() if p.is_dir()):
        dst = dst_root / folder.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(folder, dst)
        print(folder.name, renormalize(dst, a.arm), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
