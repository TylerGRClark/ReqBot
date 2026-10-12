"""Remove a document from the library (docs/WEB_UI_PARITY_PLAN.md, section 9, stage 6).

A removal is never a delete. The document's run folders are moved to `<processed_dir>/.trash/<removal time>/`, its points leave both search collections, and nothing else is
touched: another document, the uploaded PDF kept under `.uploads` and every job record stay where they are. Putting a document back is moving its folders back out of the trash
and running a rebuild.

Rules:
  - It needs an explicit confirmation: the caller must say `confirm` and repeat the document's exact key.
  - It is refused while an ingest or draft-questions job for that document is queued or running, or while a rebuild of the library is (a rebuild reads the saved documents when it
    starts and would put a removed one straight back into search). The caller passes the active jobs in; this module does not read the queue.
  - A document is found the way the library lists it, from its saved `*_requirements_normalized.jsonl`, wherever its folder is and whatever the folder is called; a folder that
    holds only this document is moved whole, and a folder shared with other documents (or the processed folder itself) gives up only this document's own files.
  - The search collections are cleaned first and the folders moved second. The folders are what a retry looks documents up by, so if the second step fails the document is still
    listed and removing it again finishes the job; the other order could leave search hits for a document that can no longer be named.
"""
import re
import shutil
import time
from pathlib import Path

from core.artifact_resolver import doc_key_from_requirements_path

DOCS_COLLECTION = "grc_requirements"
CONTEXT_COLLECTION = "grc_context"
TRASH = ".trash"
# the files a run writes for one document, as `<key>_<suffix>`; only these are ever moved out of a folder shared with other documents
ARTIFACT_SUFFIXES = (
    "ancestry.json", "chunks.jsonl", "extracted_requirements.jsonl", "raw_responses.jsonl", "parse_failures.jsonl", "normalization_failures.jsonl",
    "requirements_normalized.jsonl", "requirements_enriched.jsonl", "requirements_gated.jsonl", "final_output.json", "stats.json", "audit_questions.jsonl", "kinds.jsonl",
)


class ConfirmationRequired(ValueError):
    """The request did not carry `confirm` and the document's exact key."""


class RemoveBlocked(Exception):
    """A job for this document is queued or running."""

    def __init__(self, job_ids: list[str]):
        super().__init__(f"jobs for this document are queued or running: {', '.join(job_ids)}")
        self.job_ids = job_ids


def _mine(folder: Path, doc_key: str) -> list[Path]:
    """The document's own artifact files directly in a folder."""
    names = {f"{doc_key}_{suffix}" for suffix in ARTIFACT_SUFFIXES}
    return sorted(p for p in folder.iterdir() if p.is_file() and p.name in names)


def artifact_folders(processed_dir: Path, doc_key: str) -> list[tuple[Path, bool]]:
    """(folder, whole): every folder that holds this document's saved requirements, found the way the library lists documents (a `*_requirements_normalized.jsonl` whose key is
    this document's), skipping hidden folders (the trash, uploads, jobs, inbox). `whole` is True when everything in the folder is this document's, so the folder can move as it
    is; False when it is shared with other documents or is the processed folder itself, and only the document's own files may move."""
    root = Path(processed_dir).resolve()
    if not root.is_dir():
        return []
    folders: dict[Path, bool] = {}
    for p in root.rglob("*_requirements_normalized.jsonl"):
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts[:-1]) or doc_key_from_requirements_path(p) != doc_key:
            continue
        folder = p.parent
        mine = {f.name for f in _mine(folder, doc_key)}
        everything = {c.name for c in folder.iterdir()}
        folders[folder] = folder != root and everything == mine
    return sorted(folders.items())


def run_folders(processed_dir: Path, doc_key: str) -> list[Path]:
    """The folders that hold the document (see `artifact_folders`)."""
    return [f for f, _whole in artifact_folders(processed_dir, doc_key)]


def _collection_present(client, name: str) -> bool:
    """False only when the index says the collection does not exist (HTTP 404); an unreachable index raises, so it is never mistaken for "already clean"."""
    try:
        client.get_collection(name)
        return True
    except Exception as e:
        if getattr(e, "status_code", None) == 404 or "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
            return False
        raise


def _check_key(doc_key: str) -> str:
    key = (doc_key or "").strip()
    if not key or key.startswith(".") or re.search(r"[\\/\x00-\x1f*?\[\]]", key):
        raise ValueError(f"not a document key: {doc_key!r}")
    return key


def describe(processed_dir: Path, doc_key: str) -> dict:
    """What removing this document would move, without doing anything."""
    key = _check_key(doc_key)
    folders = artifact_folders(processed_dir, key)
    if not folders:
        raise LookupError(f"No document {key!r} is in the library.")
    root = Path(processed_dir).resolve()
    return {"document": key, "run_folders": [str(f.relative_to(root)) if f != root else "." for f, _whole in folders]}


def remove_document(processed_dir: Path, doc_key: str, *, confirm: bool, confirm_name: str, active_jobs: list[dict], client=None, now: float | None = None) -> dict:
    """Remove a document: points out of both collections, run folders into the trash. `client` is a Qdrant client (an in-memory stand-in in tests); None means "no index to clean"."""
    key = _check_key(doc_key)
    if confirm is not True or confirm_name != key:
        raise ConfirmationRequired("Removing a document needs confirm=true and its exact key repeated as confirm_name; nothing was removed.")
    folders = artifact_folders(processed_dir, key)
    if not folders:
        raise LookupError(f"No document {key!r} is in the library.")
    busy = [j["id"] for j in active_jobs
            if j.get("state") in ("queued", "running")
            and (j.get("kind") == "reindex" or (j.get("params") or {}).get("stem") == key or (j.get("params") or {}).get("doc_key") == key)]
    if busy:
        raise RemoveBlocked(busy)

    removed = {DOCS_COLLECTION: 0, CONTEXT_COLLECTION: 0}
    if client is not None:
        from pipeline import index_replace

        for collection in removed:
            try:
                if not _collection_present(client, collection):
                    continue  # nothing was ever indexed there (a document ingested without indexing, a fresh install): already clean
                removed[collection] = index_replace.delete_document_points(client, collection, f"{key}.pdf" if collection == DOCS_COLLECTION else f"{key}_chunks.jsonl")
            except Exception as e:  # nothing has been moved yet: the document is exactly as it was apart from points already deleted, and a retry finishes it
                raise RuntimeError(f"The search index could not be cleaned ({collection}): {e}. Nothing was moved; run the removal again.") from e

    root = Path(processed_dir).resolve()
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now or time.time()))
    trash = root / TRASH / stamp
    trash.mkdir(parents=True, exist_ok=True)
    moved, files = [], 0
    for folder, whole in folders:
        label = folder.name if folder != root else "(processed folder)"
        dest = trash / (folder.name if folder != root else "_flat")
        n = 1
        while dest.exists():  # two folders with the same name in different places
            n += 1
            dest = trash / f"{folder.name}_{n}"
        if whole:
            files += sum(1 for c in folder.iterdir())
            shutil.move(str(folder), str(dest))
        else:
            dest.mkdir(parents=True)
            for f in _mine(folder, key):
                shutil.move(str(f), str(dest / f.name))
                files += 1
        moved.append(label)
    return {"document": key, "run_folders_moved": moved, "files_moved": files, "trash": str(trash),
            "points_removed": {"requirements": removed[DOCS_COLLECTION], "context": removed[CONTEXT_COLLECTION]}}
