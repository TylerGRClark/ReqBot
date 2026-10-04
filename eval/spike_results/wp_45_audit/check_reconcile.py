"""F08/F09: reconcile the live requirements index with the artifacts the resolver would index (read-only)."""

import collections
import json
import logging
import os
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
logging.disable(logging.CRITICAL)
from core import config as _config
from core.artifact_resolver import resolve_latest_requirement_files
from pipeline.embed_and_index import QDRANT_UUID_NAMESPACE
from qdrant_client import QdrantClient

cfg = _config.load()
q = QdrantClient(url=cfg.qdrant_url, timeout=30)
files = resolve_latest_requirement_files(cfg.processed_dir_path())
expected = {}
for doc_key, p in files.items():
    for line in open(p):
        if line.strip():
            r = json.loads(line)
            if (r.get("source_quote") or "").strip():
                expected[str(uuid.uuid5(QDRANT_UUID_NAMESPACE, r["requirement_id"]))] = (
                    doc_key,
                    r["requirement_id"],
                )
live, offset = {}, None
while True:
    pts, offset = q.scroll(
        "grc_requirements", limit=500, with_payload=["source_pdf", "document_id"], offset=offset
    )
    live.update({str(pt.id): pt.payload for pt in pts})
    if offset is None:
        break
print(f"resolved documents={len(files)} expected={len(expected)} live={len(live)}")
print(
    f"expected but missing from Qdrant={len([e for e in expected if e not in live])}; in Qdrant but not in artifacts={len([p for p in live if p not in expected])}"
)
ids = collections.defaultdict(set)
for pl in live.values():
    ids[pl.get("source_pdf")].add(pl.get("document_id"))
print(
    "source PDFs with more than one document_id in the live index:",
    sum(1 for v in ids.values() if len(v) > 1),
)
