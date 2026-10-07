"""WP-45.10: shared helpers for the Docling configuration audit (offline; no LLM; scratch only).

The 13 pinned documents, their source-PDF SHA-256 check against `eval/spike_results/wp_44/after_replay_summary.json`, the installed Docling package
versions (a manifest line in every output), and the cache location. Conversions and re-chunked outputs are cached under `~/wp45_10_cache/`, outside
the repository; nothing here touches `pipeline/`, a Step C cache, a corpus file or Qdrant. See docs/PHASE45_WP4510_PLAN.md.
"""

import hashlib
import json
import sys
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (ROOT,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

PINNED = ROOT / "eval" / "spike_results" / "wp_44" / "after_replay_summary.json"
PDF_DIR = ROOT / "raw_pdfs"
CACHE = Path.home() / "wp45_10_cache"
PACKAGES = ("docling", "docling-core", "docling-parse", "docling-ibm-models")


def pinned_documents():
    """{document name: expected pdf sha256} for the 13 pinned documents."""
    docs = json.loads(PINNED.read_text(encoding="utf-8"))["documents"]
    return {name: rec["pdf_sha256"] for name, rec in docs.items()}


def pdf_path(name):
    return PDF_DIR / f"{name}.pdf"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_pdfs():
    """Refuse to run on a PDF whose bytes differ from the pinned corpus: returns the list of problems (empty when all 13 match)."""
    problems = []
    for name, want in sorted(pinned_documents().items()):
        path = pdf_path(name)
        if not path.exists():
            problems.append(f"{name}: {path} does not exist")
        elif sha256(path) != want:
            problems.append(f"{name}: sha256 differs from the pinned corpus")
    return problems


def versions():
    out = {}
    for pkg in PACKAGES:
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


def tag():
    """Cache tag from the installed docling version, so 2.94.0 and a newer release never share files."""
    return "d" + (versions()["docling"] or "none")


def cache_dir(kind, variant, release_tag=None, create=True):
    """Cache directory of `release_tag` (default: the installed release's tag), so a comparison can read two releases' files side by side."""
    path = CACHE / (release_tag or tag()) / kind / variant
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def check_manifest(directory, variant):
    """Write the version manifest of a new cache directory; for an existing one, refuse to reuse it unless every recorded package version matches the
    installed set (a release can stay at the same `docling` version while an unpinned dependency such as `docling-core` changes)."""
    path = directory / "_manifest.json"
    now = {"variant": variant, "versions": versions()}
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved != now:
            raise SystemExit(f"{path} records {saved}, but the installed set is {now}: refusing to reuse cached files from a different dependency set")
    else:
        path.write_text(json.dumps(now, indent=1), encoding="utf-8")
