"""Replace a document in the index without a gap (docs/WEB_UI_PARITY_PLAN.md, section 6, "Replace without a gap").

An ordinary indexing run only adds and overwrites: a point's ID comes from the requirement's own ID, so unchanged requirements are overwritten in place, but a requirement that the
new run no longer has stays behind as a stale point. To replace a document properly the indexer, after it has written the new run's points:

  1. checks the new run is complete: every expected point is present in the collection (the check `reqbot reindex` already makes before it swaps an index); and only then
  2. removes the document's points that are not in the new expected set (matched by `source_pdf`; nothing else is touched).

The old points are therefore never removed before the new ones are in. A failure at any moment leaves the old document fully searchable plus whatever new points were written,
and a retry converges. An incomplete run prunes nothing: an embedding that failed and was skipped, or (checked by the caller with `extraction_gaps`) a chunk the model failed on or
whose answer was cut off. A run with no requirements at all prunes nothing either (that is far more likely a failed extraction than an edition with no rules).

"The document" is the file name: ReqBot's document key is the PDF's stem, so a replacement is a file of the same name. A file with another name is another document.
"""
import logging

from qdrant_client import models

log = logging.getLogger(__name__)

BATCH = 256


def extraction_gaps(raw_responses_path) -> dict:
    """{"failed": n, "truncated": m}: chunks of the run whose answer from the model failed or was cut off, read from the run's `*_raw_responses.jsonl`. A run with any of these is
    missing requirements that the old index may hold, so replacing on it would delete real rules; the caller keeps the old points and asks for a re-run (which retries those chunks).
    A missing file, or a record without a status (older runs), counts as no gap."""
    import json
    from pathlib import Path

    gaps = {"failed": 0, "truncated": 0}
    try:
        for line in Path(raw_responses_path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                status = json.loads(line).get("status")
            except ValueError:
                continue
            if status in gaps:
                gaps[status] += 1
    except OSError:
        pass
    return {k: v for k, v in gaps.items() if v}


def all_present(client, collection_name: str, expected_ids) -> bool:
    """True when every expected point ID exists in the collection."""
    ids = list(expected_ids)
    for start in range(0, len(ids), BATCH):
        part = ids[start:start + BATCH]
        found = client.retrieve(collection_name=collection_name, ids=part, with_payload=False, with_vectors=False)
        if len(found) != len(part):
            return False
    return True


def stale_ids(client, collection_name: str, source_pdf: str, expected_ids) -> list:
    """The IDs of points whose `source_pdf` is this document's and that are not in the expected set."""
    expected = set(expected_ids)
    flt = models.Filter(must=[models.FieldCondition(key="source_pdf", match=models.MatchValue(value=source_pdf))])
    stale, offset = [], None
    while True:
        points, offset = client.scroll(collection_name=collection_name, scroll_filter=flt, limit=BATCH, offset=offset, with_payload=False, with_vectors=False)
        stale.extend(p.id for p in points if str(p.id) not in expected)
        if offset is None:
            return stale


def prune_if_complete(client, collection_name: str, source_pdf: str, expected_ids, *, skipped: int = 0) -> int:
    """Remove the document's stale points once the new run is verified complete; returns how many were removed (0 when nothing was stale or the run was not complete)."""
    expected = {str(i) for i in expected_ids}
    if not source_pdf:
        log.warning("Replace: the document's records carry no source_pdf, so nothing is removed")
        return 0
    if skipped:
        log.warning("Replace: %d point(s) were skipped (embedding failed), so the old points are kept; run it again", skipped)
        return 0
    if not all_present(client, collection_name, expected):
        log.warning("Replace: the new run's points are not all in the index yet, so the old points are kept; run it again")
        return 0
    stale = stale_ids(client, collection_name, source_pdf, expected)
    for start in range(0, len(stale), BATCH):
        client.delete(collection_name=collection_name, points_selector=models.PointIdsList(points=stale[start:start + BATCH]))
    if stale:
        log.info("Replace: removed %d stale point(s) of %s from '%s'", len(stale), source_pdf, collection_name)
    return len(stale)
