"""Remove a document from the library (docs/WEB_UI_PARITY_PLAN.md, section 9, stage 6).

A removal is never a delete. The document's run folders are moved to `<processed_dir>/.trash/<removal time>/`, its points leave both search collections, and nothing else is
touched: another document, the uploaded PDF kept under `.uploads` and every job record stay where they are. Putting a document back is moving its folders back out of the trash
and running a rebuild.

Rules:
  - It needs an explicit confirmation: the caller must say `confirm` and repeat the document's exact key.
  - It is refused while an ingest or draft-questions job for that document is queued or running (the caller passes the active jobs in; this module does not read the queue).
  - The search collections are cleaned first and the folders moved second. The folders are what a retry looks documents up by, so if the second step fails the document is still
    listed and removing it again finishes the job; the other order could leave search hits for a document that can no longer be named.
"""
import re
import shutil
import time
from pathlib import Path

DOCS_COLLECTION = "grc_requirements"
CONTEXT_COLLECTION = "grc_context"
TRASH = ".trash"


class ConfirmationRequired(ValueError):
    """The request did not carry `confirm` and the document's exact key."""


class RemoveBlocked(Exception):
    """A job for this document is queued or running."""

    def __init__(self, job_ids: list[str]):
        super().__init__(f"jobs for this document are queued or running: {', '.join(job_ids)}")
        self.job_ids = job_ids


def run_folders(processed_dir: Path, doc_key: str) -> list[Path]:
    """The run folders of a document: `<doc_key>_<YYYYMMDD>_<HHMMSS>` directly under the processed folder."""
    pattern = re.compile(rf"^{re.escape(doc_key)}_\d{{8}}_\d{{6}}$")
    root = Path(processed_dir)
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and pattern.match(p.name))


def _check_key(doc_key: str) -> str:
    key = (doc_key or "").strip()
    if not key or key.startswith(".") or re.search(r"[\\/\x00-\x1f*?\[\]]", key):
        raise ValueError(f"not a document key: {doc_key!r}")
    return key


def describe(processed_dir: Path, doc_key: str) -> dict:
    """What removing this document would move, without doing anything."""
    key = _check_key(doc_key)
    folders = run_folders(processed_dir, key)
    if not folders:
        raise LookupError(f"No document {key!r} is in the library.")
    return {"document": key, "run_folders": [f.name for f in folders]}


def remove_document(processed_dir: Path, doc_key: str, *, confirm: bool, confirm_name: str, active_jobs: list[dict], client=None, now: float | None = None) -> dict:
    """Remove a document: points out of both collections, run folders into the trash. `client` is a Qdrant client (an in-memory stand-in in tests); None means "no index to clean"."""
    key = _check_key(doc_key)
    if confirm is not True or confirm_name != key:
        raise ConfirmationRequired("Removing a document needs confirm=true and its exact key repeated as confirm_name; nothing was removed.")
    folders = run_folders(processed_dir, key)
    if not folders:
        raise LookupError(f"No document {key!r} is in the library.")
    busy = [j["id"] for j in active_jobs
            if j.get("state") in ("queued", "running") and ((j.get("params") or {}).get("stem") == key or (j.get("params") or {}).get("doc_key") == key)]
    if busy:
        raise RemoveBlocked(busy)

    removed = {DOCS_COLLECTION: 0, CONTEXT_COLLECTION: 0}
    if client is not None:
        from pipeline import index_replace

        for collection in removed:
            try:
                removed[collection] = index_replace.delete_document_points(client, collection, f"{key}.pdf" if collection == DOCS_COLLECTION else f"{key}_chunks.jsonl")
            except Exception as e:  # nothing has been moved yet: the document is exactly as it was apart from points already deleted, and a retry finishes it
                raise RuntimeError(f"The search index could not be cleaned ({collection}): {e}. Nothing was moved; run the removal again.") from e

    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now or time.time()))
    trash = Path(processed_dir) / TRASH / stamp
    trash.mkdir(parents=True, exist_ok=True)
    moved = []
    for folder in folders:
        dest = trash / folder.name
        shutil.move(str(folder), str(dest))
        moved.append(folder.name)
    return {"document": key, "run_folders_moved": moved, "trash": str(trash), "points_removed": {"requirements": removed[DOCS_COLLECTION], "context": removed[CONTEXT_COLLECTION]}}
