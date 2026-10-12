"""Replace a document in the index without a gap (docs/WEB_UI_PARITY_PLAN.md, section 6, "Replace without a gap").

An ordinary indexing run only adds and overwrites: a point's ID comes from the requirement's own ID, so unchanged requirements are overwritten in place, but a requirement that the
new run no longer has stays behind as a stale point. To replace a document properly the indexer, after it has written the new run's points:

  1. checks the new run is complete: every expected point is present in the collection (the check `reqbot reindex` already makes before it swaps an index); and only then
  2. removes the document's points that are not in the new expected set (matched by `source_pdf`; nothing else is touched).

The old points are therefore never removed before the new ones are in. A failure at any moment leaves the old document fully searchable plus whatever new points were written,
and a retry converges. An incomplete run (an embedding failed and was skipped) prunes nothing.
"""
import logging

from qdrant_client import models

log = logging.getLogger(__name__)

BATCH = 256


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
