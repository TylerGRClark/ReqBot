#!/usr/bin/env python3
"""Read exact PREREG8 chunk snapshots; count context recovery, never call a model.

Candidate counts are not true attachment accuracy. Truth requires source review.
Only a new output directory is written; source bytes remain untouched.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline import clause_labeling as CL  # noqa: E402
from pipeline.clauses import LISTSTART, _as_list  # noqa: E402
from pipeline.lead_in import find_lead_in  # noqa: E402

DOCS = (
    "afi17-203", "afi13-550", "DODI 5200.01", "afi17-101", "afman17-204",
    "DODI 5200.48", "DODI 8551.01",
)
FROZEN_PROMPT = "b9b20379597d04b346f6d7f30b1e6df6257f86fd15c372588dc06a1bbdd8dbc4"
SEED = "heading-tree-v1"
PRODUCTION_PATHS = (
    "pipeline/clauses.py", "pipeline/clause_labeling.py", "pipeline/lead_in.py",
    "pipeline/table_header.py", "pipeline/sentence_expand.py",
    "pipeline/chunk_text.py", "services/checklist_audit.py",
    "services/checklist_service.py", "eval/clause_labeling/label_ctx_metrics.py",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw(chunk: dict) -> str:
    return chunk.get("raw_text") or chunk.get("text") or ""


def validate_chunks(chunks: list[dict]) -> None:
    if not chunks:
        raise ValueError("empty chunk snapshot")
    ids = []
    for chunk in chunks:
        cid = chunk.get("chunk_id")
        if type(cid) is not int or cid < 0:
            raise ValueError("chunk_id must be a non-negative integer")
        if not isinstance(raw(chunk), str) or not raw(chunk).strip():
            raise ValueError("chunk text must be nonempty")
        # chunk_unit accepts legacy list representations; reject malformed ones
        # here rather than silently collapsing distinct sections to empty paths.
        for field in ("section_ref_path", "section_title_path"):
            value = chunk.get(field, [])
            if not isinstance(value, list) and not _as_list(value):
                if value not in (None, "", "[]", "()"):
                    raise ValueError(f"invalid {field}")
        ids.append(cid)
    if len(ids) != len(set(ids)) or ids != sorted(ids):
        raise ValueError("chunk IDs must be unique and ordered")


def audit_document(document: str, chunks: list[dict]) -> tuple[dict, list[dict]]:
    validate_chunks(chunks)
    by_id = {c["chunk_id"]: c for c in chunks}
    counts = collections.Counter(chunks=len(chunks), clauses=0)
    cases = []
    for clause in CL.document_clauses(chunks):
        cid = clause["chunk_id"]
        chunk = by_id[cid]
        quote = clause["text"]
        if raw(chunk)[clause["start"]:clause["end"]] != quote:
            raise ValueError("clause source offsets do not reproduce quote")
        same = find_lead_in(raw(chunk), clause["start"])
        actual = clause["ctx_lead"]
        recovery = "same_chunk" if same else "previous_chunk" if actual else "none"
        counts["clauses"] += 1
        counts[f"lead_in_{recovery}"] += 1
        list_shaped = bool(LISTSTART.match(quote)) and not quote.lstrip().startswith("|")
        counts["list_shaped_clauses"] += list_shaped
        counts["table_shaped_clauses"] += quote.lstrip().startswith("|")
        counts["clauses_over_prompt_cut"] += len(quote) > CL.CLAUSE_CHARS
        cases.append({
            "document": document, "key": f"{cid}:{clause['clause_index']}",
            "chunk_id": cid, "clause_index": clause["clause_index"],
            "start": clause["start"], "end": clause["end"], "quote": quote,
            "list_shaped": list_shaped, "heading": clause["heading"], "ref": clause["ref"],
            "ctx_lead": actual, "same_chunk_ctx_lead": same,
            "recovery_route": recovery,
            "labeler_block": CL.clause_block([clause]),
        })
    return dict(counts), cases


def review_sample(cases: list[dict], chunks: list[dict], per_stratum: int = 10) -> list[dict]:
    """Sample without recovery outcomes; withhold automatic contexts from reviewer."""
    positions = {c["chunk_id"]: i for i, c in enumerate(chunks)}
    selected = []
    for list_shaped in (True, False):
        pool = [c for c in cases if c["list_shaped"] == list_shaped]
        ranked = sorted(pool, key=lambda c: sha(f"{SEED}|{c['document']}|{c['key']}".encode()))
        for c in ranked[:per_stratum]:
            i = positions[c["chunk_id"]]
            selected.append({
                k: c[k] for k in ("document", "key", "chunk_id", "clause_index", "start", "end", "quote", "heading", "ref")
            } | {
                "stratum": "list_shaped" if list_shaped else "other",
                "stratum_population": len(pool),
                "nearby_chunks": [{"chunk_id": n["chunk_id"], "raw_text": raw(n),
                                   "section_ref_path": n.get("section_ref_path", []),
                                   "section_title_path": n.get("section_title_path", [])}
                                  for n in chunks[max(0, i - 2):i + 3]],
                "review": {
                    "reviewer": "", "lead_in": {"status": "unreviewed"},
                    "actor": {"status": "unreviewed"}, "notes": "",
                },
            })
    return selected


def load_manifest(path: Path) -> tuple[dict, dict, list[dict]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    documents = manifest.get("documents", {})
    if set(documents) != set(DOCS):
        raise ValueError("manifest must name exactly the seven PREREG8 documents")
    snapshots, hashes, inventory = {}, {}, []
    for document in DOCS:
        entry = documents[document]
        source = Path(entry["chunks"])
        if not source.is_absolute():
            source = path.parent / source
        data = source.read_bytes()
        digest = sha(data)
        if digest != entry["chunks_sha256"]:
            raise ValueError(f"snapshot hash mismatch: {document}")
        chunks = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        validate_chunks(chunks)
        snapshots[document] = chunks
        hashes[document] = {"chunks_path": str(source.resolve()), "sha256": digest}
        inventory.append({"document": document, "docling_export_supplied": bool(entry.get("docling_export")),
                          "note": "Presence of an export path is not provenance validation."})
    return snapshots, hashes, inventory


def run(manifest_path: Path, output: Path) -> dict:
    # Validate all inputs before creating output. No production extraction or I/O
    # occurs through the imported pure clause/context functions.
    CL.load_prompt()
    if CL.PROMPT_SHA256 != FROZEN_PROMPT or CL.BATCH_SIZE != 4:
        raise ValueError("frozen prompt or batch size differs")
    snapshots, hashes, inventory = load_manifest(manifest_path)
    totals, by_document, cases, sample = collections.Counter(), {}, [], []
    for document, chunks in snapshots.items():
        counts, found = audit_document(document, chunks)
        totals.update(counts)
        by_document[document] = counts
        cases.extend(found)
        sample.extend(review_sample(found, chunks))
    summary = {
        "status": "candidate_counts_only_awaiting_source_review",
        "model_calls": 0, "production_writes": 0,
        "manifest_sha256": sha(manifest_path.read_bytes()),
        "prompt_sha256": FROZEN_PROMPT,
        "code_sha256": {p: sha((ROOT / p).read_bytes()) for p in PRODUCTION_PATHS},
        "input_snapshots": hashes, "inventory": inventory,
        "counts": dict(totals), "by_document": by_document,
        "sample_size": len(sample), "sample_seed": SEED,
        "true_cross_chunk_relationship_rate": None,
        "attachment_accuracy": None, "passage_window_recovery": None,
        "limits": [
            "List shape and colon recovery are candidates, not ground truth.",
            "Snapshot hashes require confirmation against original PREREG8 provenance.",
            "Review nearby chunks AND the full source/tree; local snippets can omit the true parent.",
            "Existing passage windows act downstream of the clause labeler.",
            "Gold metrics and source-tree feasibility have not been measured.",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("summary.json", summary), ("automatic-contexts.json", cases),
                        ("review-sample.json", sample)):
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New scratch directory; existing paths refused")
    args = parser.parse_args()
    summary = run(args.manifest, args.output)
    print(json.dumps({"status": summary["status"], "counts": summary["counts"]}))


if __name__ == "__main__":
    main()
