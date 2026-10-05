"""WP-45.7: build the two labeling packs (offline; no LLM, no Qdrant, no pipeline output).

- pack_heldout.md: every piece of the frozen held-out label pages (outputs/heldout_frozen.json), in page order.
- pack_devkind.md: the development pages of WP-45.1(e) with the pieces that need a `kind` label marked: every adjudicated
  obligation, plus the adjudicated non-obligations that contain "may", "can" or a permission phrase (lowercase, so a date such as
  "22 MAY 2018" is not caught), because version 1 of the rubric excluded permissions and Tyler has since ruled that "should" and
  "may" statements are requirements. The marked pieces are listed in page order, never grouped by their earlier label, and
  the pack carries no earlier label, so the labelers cannot tell which were obligations before.

The pack text holds nothing from the extraction pipeline. RUBRIC.md and check_labels.py in label_pack/ are the source files;
this script writes the packs there and a manifest with the hashes.

Run from the repo root:
  python3 eval/spike_results/wp_45_7/pack.py
"""

import hashlib
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_DEV = _ROOT / "eval/spike_results/wp_45_1e"
if str(_DEV) not in sys.path:
    sys.path.insert(0, str(_DEV))

import score as DEV  # noqa: E402  (WP-45.1(e): label loading and adjudication, reused unchanged)

PACK_DIR = _HERE / "label_pack"
HELDOUT = _HERE / "outputs" / "heldout_frozen.json"
MANIFEST = _HERE / "outputs" / "pack_manifest.json"

# Lowercase on purpose: "22 MAY 2018" must not match. Descriptive uses ("hypervisors can ...") are caught too and are
# meant to be: the labelers answer `none` for them.
PERMISSION = re.compile(r"\b(?:may|can|permitted to|authorized to|allowed to)\b")


def heldout_pack(frozen):
    parts = [
        "# Held-out pages, pass A: pieces of source pages\n\n"
        "Read RUBRIC.md first. Each page below is cut into numbered pieces in the order they appear. Label every piece "
        "(label, kind, segment_ok, note).\n"
    ]
    for document, entry in frozen["documents"].items():
        for page in sorted(entry["pieces"], key=int):
            parts.append(f"\n## {document}, page {int(page)}\n")
            parts.extend(f"[{p['id']}] {p['text']}\n" for p in entry["pieces"][page])
    return "".join(parts)


def devkind_candidates(final, index):
    """Piece ids that need a kind label: adjudicated obligations plus non-obligations with permission wording."""
    return sorted(
        i
        for i, r in final.items()
        if r["label"] == "obligation" or PERMISSION.search(index[i]["text"])
    )


def devkind_pack(frozen, candidates):
    wanted = set(candidates)
    parts = [
        "# Development pages, kind pass: pieces marked for a second look\n\n"
        "Read RUBRIC.md first. A line that starts with an id in square brackets is a piece you label (give a kind, or none). "
        "An indented line is context only. Do not label context lines.\n"
    ]
    for document, entry in frozen["documents"].items():
        for page in sorted(entry["pieces"], key=int):
            pieces = entry["pieces"][page]
            if not any(p["id"] in wanted for p in pieces):
                continue
            parts.append(f"\n## {document}, page {int(page)}\n")
            for p in pieces:
                if p["id"] in wanted:
                    parts.append(f"[{p['id']}] {p['text']}\n")
                else:
                    parts.append(f"    {p['text']}\n")
    return "".join(parts)


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    held = json.loads(HELDOUT.read_text(encoding="utf-8"))
    dev_dir = _DEV / "labels"
    labels = DEV.load_labels(dev_dir)
    answers = DEV.parse_answers((dev_dir / "adjudication.txt").read_text(encoding="utf-8"))
    final = DEV.resolve(labels, answers)
    dev_frozen = json.loads((_DEV / "outputs" / "pages_frozen.json").read_text(encoding="utf-8"))
    index = DEV.piece_index(dev_frozen)
    candidates = devkind_candidates(final, index)
    PACK_DIR.mkdir(exist_ok=True)
    (PACK_DIR / "pack_heldout.md").write_text(heldout_pack(held), encoding="utf-8")
    (PACK_DIR / "pack_devkind.md").write_text(devkind_pack(dev_frozen, candidates), encoding="utf-8")
    n_obl = sum(1 for i in candidates if final[i]["label"] == "obligation")
    manifest = {
        "heldout_pieces": held["pieces_total"],
        "heldout_pieces_sha256": held["pieces_sha256"],
        "devkind_pieces": len(candidates),
        "devkind_adjudicated_obligations": n_obl,
        "devkind_permission_wording_non_obligations": len(candidates) - n_obl,
        "frozen_sha256": {
            "heldout_frozen.json": sha256_of(HELDOUT),
            "pages_frozen.json": sha256_of(_DEV / "outputs" / "pages_frozen.json"),
        },
        "sha256": {
            n: sha256_of(PACK_DIR / n)
            for n in ("pack_heldout.md", "pack_devkind.md", "RUBRIC.md", "check_labels.py")
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    sys.exit(main())
