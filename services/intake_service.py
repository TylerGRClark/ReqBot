"""Getting a PDF into the library as an admin: uploads, the inbox folder and the same-file rules (docs/WEB_UI_PARITY_PLAN.md, section 6, stage 4).

Only an admin adds documents. There is no end-user upload, and the server is never handed a path by a caller: an uploaded PDF is stored under
`<processed_dir>/.uploads/<upload id>/<plain file name>`, and the only folder it reads PDFs from is the configured inbox. The PDF's stem is the document key everywhere in ReqBot,
so the stored name is the name the admin uploaded (made plain), never a generated one.

Checks on every PDF, uploaded or in the inbox: a plain `.pdf` file name; the first bytes are `%PDF-`; the size is under a cap (default 100 MB); the page count, read in a child
process with memory and CPU limits so a hostile file cannot take the server with it, is under a cap (default 1,500) and the file opens at all. An upload is written to disk as it
arrives and the cap is enforced while it streams, because a chunked request need not carry a length.

The limits are environment variables, not config.json keys, so the Settings screen (which edits config.json from a browser) cannot raise them:
REQBOT_MAX_UPLOAD_MB, REQBOT_MAX_PDF_PAGES, REQBOT_INBOX_DIR (default `<processed_dir>/.inbox`).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

DEFAULT_MAX_UPLOAD_MB = 100
DEFAULT_MAX_PAGES = 1500
ENV_MAX_UPLOAD_MB = "REQBOT_MAX_UPLOAD_MB"
ENV_MAX_PAGES = "REQBOT_MAX_PDF_PAGES"
ENV_INBOX = "REQBOT_INBOX_DIR"
PAGE_COUNT_TIMEOUT_SECONDS = 60
INBOX_LIST_LIMIT = 200
UPLOAD_ID = re.compile(r"^UP-\d{8}-\d{6}-[0-9a-f]{6}$")
_NAME_CHARS = re.compile(r"[^A-Za-z0-9 ._()\-]")
_PAGE_COUNT_CODE = (
    "import resource, sys\n"
    "resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))\n"
    "resource.setrlimit(resource.RLIMIT_CPU, (45, 45))\n"
    "import pypdfium2\n"
    "d = pypdfium2.PdfDocument(sys.argv[1])\n"
    "print(len(d))\n"
)


class IntakeError(Exception):
    """A PDF was refused. `code` is stable for a screen to branch on; `status` is the HTTP status that fits."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


# ---------------------------------------------------------------------------
# Limits and places
# ---------------------------------------------------------------------------

def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
        return value if value > 0 else default
    except ValueError:
        return default


def max_upload_bytes() -> int:
    return _env_int(ENV_MAX_UPLOAD_MB, DEFAULT_MAX_UPLOAD_MB) * 1024 * 1024


def max_pages() -> int:
    return _env_int(ENV_MAX_PAGES, DEFAULT_MAX_PAGES)


def uploads_dir(processed_dir: Path) -> Path:
    return Path(processed_dir) / ".uploads"


def inbox_dir(processed_dir: Path) -> Path:
    env = (os.environ.get(ENV_INBOX) or "").strip()
    return Path(env).expanduser() if env else Path(processed_dir) / ".inbox"


def clean_filename(name: str) -> str:
    """A plain file name: no path parts, only letters, digits, space and . _ ( ) -, and a lower-case `.pdf` extension. A name that has nothing left, or does not end in .pdf, is refused."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not base.lower().endswith(".pdf"):
        raise IntakeError("not_pdf", "Only .pdf files can be added.", 415)
    stem = _NAME_CHARS.sub("_", base[:-4]).strip(" .")
    if not stem or stem.startswith("."):
        raise IntakeError("bad_name", "The file name has no usable characters.", 400)
    return stem[:120] + ".pdf"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def page_count(path: Path) -> int:
    """The number of pages, read by a child process under memory and CPU limits. A file that does not open as a PDF, or that takes too long, is refused."""
    try:
        r = subprocess.run([sys.executable, "-c", _PAGE_COUNT_CODE, str(path)], capture_output=True, text=True, timeout=PAGE_COUNT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise IntakeError("unreadable", "The file took too long to read as a PDF.", 422) from None
    if r.returncode != 0 or not r.stdout.strip().isdigit():
        raise IntakeError("unreadable", "The file could not be read as a PDF.", 422)
    return int(r.stdout.strip())


def check_pdf_file(path: Path) -> tuple[int, int]:
    """(size, pages) of a PDF already on disk (an inbox file), applying the same rules as an upload."""
    size = path.stat().st_size
    if size > max_upload_bytes():
        raise IntakeError("too_large", f"The file is larger than the {max_upload_bytes() // (1024 * 1024)} MB limit.", 413)
    with open(path, "rb") as f:
        if f.read(5) != b"%PDF-":
            raise IntakeError("not_pdf", "The file is not a PDF (it does not start with %PDF-).", 415)
    pages = page_count(path)
    if pages > max_pages():
        raise IntakeError("too_many_pages", f"The PDF has {pages} pages; the limit is {max_pages()}.", 422)
    return size, pages


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------

class UploadWriter:
    """Writes one upload to disk as it arrives. `write()` each chunk, then `finish()`; on any error `abort()` removes what was written."""

    def __init__(self, processed_dir: Path, filename: str, *, max_bytes: int | None = None):
        self.name = clean_filename(filename)
        self.max_bytes = max_bytes or max_upload_bytes()
        self.id = f"UP-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.dir = uploads_dir(processed_dir) / self.id
        self.dir.mkdir(parents=True)
        self._part = self.dir / (self.name + ".part")
        self._file = open(self._part, "wb")
        self._hash = hashlib.sha256()
        self._head = b""
        self.size = 0

    def write(self, chunk: bytes) -> None:
        if not chunk:
            return
        self.size += len(chunk)
        if self.size > self.max_bytes:
            raise IntakeError("too_large", f"The file is larger than the {self.max_bytes // (1024 * 1024)} MB limit.", 413)
        if len(self._head) < 5:
            self._head += chunk[: 5 - len(self._head)]
            if len(self._head) >= 5 and self._head != b"%PDF-":
                raise IntakeError("not_pdf", "The file is not a PDF (it does not start with %PDF-).", 415)
        self._hash.update(chunk)
        self._file.write(chunk)

    def finish(self) -> dict:
        self._file.close()
        if self._head != b"%PDF-":
            raise IntakeError("not_pdf", "The file is not a PDF (it does not start with %PDF-).", 415)
        final = self.dir / self.name
        os.replace(self._part, final)
        pages = page_count(final)
        if pages > max_pages():
            raise IntakeError("too_many_pages", f"The PDF has {pages} pages; the limit is {max_pages()}.", 422)
        meta = {"upload_id": self.id, "filename": self.name, "stem": final.stem, "size": self.size, "pages": pages, "sha256": self._hash.hexdigest(),
                "path": str(final), "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        (self.dir / "upload.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta

    def abort(self) -> None:
        try:
            self._file.close()
        except OSError:
            pass
        shutil.rmtree(self.dir, ignore_errors=True)


def read_upload(processed_dir: Path, upload_id: str) -> dict:
    """The record written when an upload finished. Only an id of the exact shape this module makes is looked up, so no path can be built from caller input."""
    if not UPLOAD_ID.match(upload_id or ""):
        raise IntakeError("no_such_upload", "No such upload.", 404)
    try:
        meta = json.loads((uploads_dir(processed_dir) / upload_id / "upload.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise IntakeError("no_such_upload", "No such upload.", 404) from None
    if not Path(meta.get("path", "")).is_file():
        raise IntakeError("no_such_upload", "The uploaded file is no longer there.", 404)
    return meta


def renamed_copy(src: Path, new_stem: str, processed_dir: Path) -> Path:
    """Copy a PDF under another stem (keep both versions of a document) into a fresh upload folder and return the new path."""
    folder = uploads_dir(processed_dir) / f"UP-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    folder.mkdir(parents=True)
    dest = folder / f"{new_stem}.pdf"
    shutil.copy2(src, dest)
    return dest


# ---------------------------------------------------------------------------
# The library and the queue
# ---------------------------------------------------------------------------

def library_documents(processed_dir: Path) -> dict[str, dict]:
    """{document key: {"hash": sha256 of its PDF, "source_pdf": file name, "path": requirements file}} for the newest run of each document in the library."""
    from core.artifact_resolver import doc_key_from_requirements_path

    latest: dict[str, Path] = {}
    root = Path(processed_dir)
    if not root.exists():
        return {}
    for p in root.rglob("*_requirements_normalized.jsonl"):
        key = doc_key_from_requirements_path(p)
        if key not in latest or p.stat().st_mtime > latest[key].stat().st_mtime:
            latest[key] = p
    out: dict[str, dict] = {}
    for key, path in latest.items():
        try:
            with open(path, encoding="utf-8") as f:
                first = next((json.loads(line) for line in f if line.strip()), {})
        except (OSError, ValueError):
            first = {}
        out[key] = {"hash": first.get("document_hash_full", ""), "source_pdf": first.get("source_pdf", ""), "path": str(path)}
    return out


def classify(processed_dir: Path, stem: str, sha256: str, jobs: list[dict]) -> dict:
    """Where a PDF stands against the library and the queue:
      new                          nothing by that name or with that content
      same_content                 this name is in the library with identical content (nothing to do)
      same_content_other_name      identical content is in the library under another name (`document` says which)
      same_name_different_content  this name is in the library, with different content (replace, or keep both)
      queued                       an ingest of this name is already queued or running
    """
    for j in jobs:
        if j.get("kind") == "ingest" and j.get("state") in ("queued", "running") and (j.get("params") or {}).get("stem") == stem:
            return {"status": "queued", "document": stem, "job_id": j["id"]}
    lib = library_documents(processed_dir)
    existing = lib.get(stem)
    if existing and existing["hash"] and existing["hash"] == sha256:
        return {"status": "same_content", "document": stem}
    other = next((k for k, d in lib.items() if k != stem and d["hash"] and d["hash"] == sha256), None)
    if other:
        return {"status": "same_content_other_name", "document": other}
    if existing:
        return {"status": "same_name_different_content", "document": stem}
    return {"status": "new", "document": None}


def free_stem(processed_dir: Path, stem: str, jobs: list[dict]) -> str:
    """`<stem>_2`, `<stem>_3`, ... the first name that is neither in the library nor in the queue."""
    taken = set(library_documents(processed_dir)) | {(j.get("params") or {}).get("stem") for j in jobs if j.get("state") in ("queued", "running")}
    n = 2
    while f"{stem}_{n}" in taken:
        n += 1
    return f"{stem}_{n}"


def inbox_pdfs(folder: Path) -> dict[str, Path]:
    """{name: path} of the PDFs directly in the inbox. Regular files only: a symbolic link, a hidden file or anything in a sub-folder is left out, so a link cannot make the
    server read a file from somewhere else."""
    root = folder.resolve()
    out: dict[str, Path] = {}
    for p in folder.iterdir():
        if p.name.startswith(".") or p.suffix.lower() != ".pdf" or p.is_symlink() or not p.is_file():
            continue
        if p.resolve().parent != root:
            continue
        out[p.name] = p
    return out


def list_inbox(processed_dir: Path, jobs: list[dict]) -> dict:
    """The PDFs in the inbox with where each stands (see `inbox_pdfs` for what counts)."""
    folder = inbox_dir(processed_dir)
    if not folder.is_dir():
        return {"folder": str(folder), "exists": False, "files": [], "truncated": False}
    files = []
    pdfs = inbox_pdfs(folder)
    entries = [pdfs[name] for name in sorted(pdfs)]
    for p in entries[:INBOX_LIST_LIMIT]:
        try:
            digest = file_sha256(p)
        except OSError:
            continue
        files.append({"name": p.name, "size": p.stat().st_size, **classify(processed_dir, p.stem, digest, jobs), "sha256": digest})
    return {"folder": str(folder), "exists": True, "files": files, "truncated": len(entries) > INBOX_LIST_LIMIT}
