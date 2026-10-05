"""WP-45.7: the chunks the discovery runs read, for the development and held-out sets (offline; no LLM).

Discovery runs only on the chunks that touch the labeled pages (plan 4.2), not on whole documents. For the held-out set that is
the frozen `selected_chunk_ids` of `outputs/heldout_frozen.json`; for the development set it is every chunk whose page range
touches a page drawn in WP-45.1(e). Chunk files are the pinned ones (WP-44 manifest hashes; CNSSI 1253 pinned by sha256).
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_audit", _ROOT / "eval/spike_results/wp_45_1e"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _inputs  # noqa: E402
import draw_heldout as H  # noqa: E402

HELDOUT_FROZEN = _HERE / "outputs" / "heldout_frozen.json"
DEV_FROZEN = _ROOT / "eval/spike_results/wp_45_1e/outputs/pages_frozen.json"
SETS = ("dev", "heldout")


def _chunks(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def load_document_chunks(*documents):
    """{document: [chunk records]} from the pinned chunk files (and the pinned CNSSI 1253 file)."""
    inputs = _inputs.corpus_inputs("chunks")
    inputs.update(H._catalog_inputs())
    return {d: _chunks(inputs[d]["chunks"]) for d in documents}


def heldout_chunks():
    """[(document, chunk)] for the frozen held-out selection, in document then chunk order."""
    frozen = json.loads(HELDOUT_FROZEN.read_text(encoding="utf-8"))
    docs = load_document_chunks(*sorted(frozen["documents"]))
    out = []
    for document in sorted(frozen["documents"]):
        wanted = set(frozen["documents"][document]["selected_chunk_ids"])
        out += [(document, c) for c in docs[document] if c["chunk_id"] in wanted]
    return out


def dev_chunks():
    """[(document, chunk)] for every chunk of the three development documents that touches a WP-45.1(e) drawn page."""
    frozen = json.loads(DEV_FROZEN.read_text(encoding="utf-8"))
    docs = load_document_chunks(*sorted(frozen["documents"]))
    out = []
    for document in sorted(frozen["documents"]):
        drawn = [int(p) for p in frozen["documents"][document]["drawn"]]
        wanted = set(H.select_chunks(docs[document], drawn))
        out += [(document, c) for c in docs[document] if c["chunk_id"] in wanted]
    return out


def chunk_set(name):
    if name == "dev":
        return dev_chunks()
    if name == "heldout":
        return heldout_chunks()
    raise ValueError(f"set must be one of {SETS}")


def spread(items, n):
    """n items spread evenly over the list (a deterministic pilot sample), or all of them if n is None or large."""
    if not n or n >= len(items):
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]
