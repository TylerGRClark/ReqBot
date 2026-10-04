"""Shared input check for the WP-45 corpus scripts: stop before measuring if a pinned input is missing or changed."""

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = _ROOT / "eval/spike_results/wp_44/manifest.json"
FILENAMES = {
    "chunks": "{doc}_chunks.jsonl",
    "extracted": "{doc}_extracted_requirements.jsonl",
    "normalized": "{doc}_requirements_normalized.jsonl",
}
# WP-44.1 removed three junk records from these two documents after the manifest was written
# (docs/PHASE44_REQUIREMENTS.md: 220 -> 218 and 289 -> 288), so their normalized hash is expected to differ.
NORMALIZED_EDITED_AFTER_MANIFEST = {"DODI 5200.48", "afi10-2402"}


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned_documents():
    return json.loads(MANIFEST.read_text())["documents"]


def corpus_inputs(*kinds):
    """Return {doc: {kind: Path}} for the pinned documents, by exact filename.

    Exits non-zero, listing every problem at once, if a file is missing or its sha256 differs from
    the manifest (other than the two documented WP-44.1 edits). Nothing is measured on partial input.
    """
    from core import config as _config

    processed = _config.load().processed_dir_path()
    inputs, problems = {}, []
    for doc, m in pinned_documents().items():
        run_dir = processed / m["run_dir"]
        inputs[doc] = {}
        for kind in kinds:
            path = run_dir / FILENAMES[kind].format(doc=doc)
            if not path.exists():
                problems.append(f"missing: {path}")
                continue
            expected_edit = kind == "normalized" and doc in NORMALIZED_EDITED_AFTER_MANIFEST
            if not expected_edit and sha256_of(path) != m[f"{kind}_sha256"]:
                problems.append(f"changed since the WP-44 manifest: {path}")
            inputs[doc][kind] = path
    if problems:
        sys.exit(
            "pinned inputs are not usable, corpus measurement not run:\n  " + "\n  ".join(problems)
        )
    note = ""
    if "normalized" in kinds:
        note = f" (normalized for {', '.join(sorted(NORMALIZED_EDITED_AFTER_MANIFEST))} excepted: edited by WP-44.1)"
    print(
        f"inputs: {len(inputs)} pinned documents; {', '.join(kinds)} found by exact name, "
        f"sha256 matches the WP-44 manifest{note}"
    )
    return inputs


def pdf_inputs(raw_pdfs):
    """Return {doc: Path} for the pinned documents' source PDFs; exit non-zero listing any that are missing."""
    paths = {doc: Path(raw_pdfs) / f"{doc}.pdf" for doc in pinned_documents()}
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        sys.exit("pinned PDFs are not available, nothing measured:\n  " + "\n  ".join(missing))
    return paths
