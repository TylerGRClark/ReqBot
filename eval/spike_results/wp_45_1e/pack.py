"""WP-45.1(e): build the labeling pack from the frozen page draw (offline; no LLM, no Qdrant, no pipeline output).

The pack holds the pieces of the drawn pages, in page order, and nothing from the extraction pipeline. RUBRIC.md and
check_labels.py in audit_pack/ are the source files; this script writes pack_a.md and a manifest with the hashes.

Run from the repo root (after draw.py):
  python3 eval/spike_results/wp_45_1e/pack.py
"""

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
PACK_DIR = _HERE / "audit_pack"
FROZEN = _HERE / "outputs" / "pages_frozen.json"
MANIFEST = _HERE / "outputs" / "pack_manifest.json"


def build_pack(frozen):
    parts = [
        "# Source-based obligation sample, pass A: pieces of source pages\n\n"
        "Read RUBRIC.md first. Each page below is cut into numbered pieces in the order they appear. Label every piece. "
        "There is no pass B.\n"
    ]
    for document, entry in frozen["documents"].items():
        for page in sorted(entry["pieces"], key=int):
            parts.append(f"\n## {document}, page {int(page)}\n")
            parts.extend(f"[{p['id']}] {p['text']}\n" for p in entry["pieces"][page])
    return "".join(parts)


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    (PACK_DIR / "pack_a.md").write_text(build_pack(frozen), encoding="utf-8")
    manifest = {
        "pieces_total": frozen["pieces_total"],
        "pieces_sha256": frozen["pieces_sha256"],
        "pages_frozen_sha256": sha256_of(FROZEN),
        "sha256": {
            n: sha256_of(PACK_DIR / n) for n in ("pack_a.md", "RUBRIC.md", "check_labels.py")
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    sys.exit(main())
