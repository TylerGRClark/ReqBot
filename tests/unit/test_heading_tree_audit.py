"""No-model diagnostic tests; these do not establish corpus attachment quality."""
import copy
import json

import pytest

from eval.heading_tree import audit as A


def chunk(cid, text, section="Roles"):
    return {"chunk_id": cid, "raw_text": text, "section_ref_path": ["2"], "section_title_path": [section]}


def test_previous_chunk_recovery_is_counted_without_editing_quotes():
    chunks = [chunk(0, "The operator shall:"), chunk(1, "(a) Review logs.\n(b) Retain records.")]
    before = copy.deepcopy(chunks)
    counts, cases = A.audit_document("example", chunks)
    assert counts["lead_in_previous_chunk"] == 2
    assert counts["list_shaped_clauses"] == 2
    assert chunks == before
    assert cases[1]["quote"] == "(a) Review logs."
    assert cases[1]["ctx_lead"] == "The operator shall:"
    assert cases[1]["same_chunk_ctx_lead"] is None


def test_section_boundary_prevents_previous_chunk_recovery():
    counts, cases = A.audit_document("example", [chunk(0, "The operator shall:", "Alpha"), chunk(1, "(a) Review logs.", "Beta")])
    assert counts.get("lead_in_previous_chunk", 0) == 0
    assert cases[-1]["ctx_lead"] is None


def test_same_chunk_and_more_distant_context_are_distinct():
    chunks = [chunk(0, "The operator shall:\n(a) Review logs."),
              chunk(1, "(b) Retain records."), chunk(2, "(c) Report anomalies.")]
    counts, cases = A.audit_document("example", chunks)
    assert counts["lead_in_same_chunk"] == 1
    assert counts["lead_in_previous_chunk"] == 1
    # Truth may still be the operator; the diagnostic explicitly does NOT call
    # the unrecovered case a true missing parent without source review.
    assert cases[-1]["recovery_route"] == "none"


@pytest.mark.parametrize("chunks", [[], [chunk(1, "Text."), chunk(1, "Other.")],
                                    [chunk(2, "Text."), chunk(1, "Other.")],
                                    [chunk(True, "Text.")], [chunk(1, "")]])
def test_bad_snapshots_are_refused(chunks):
    with pytest.raises(ValueError):
        A.audit_document("example", chunks)


def test_sample_hides_recovery_outputs_and_does_not_depend_on_them():
    chunks = [chunk(0, "The operator shall:\n(a) Review logs.\n(b) Retain records.")]
    _, cases = A.audit_document("example", chunks)
    sample = A.review_sample(cases, chunks, per_stratum=1)
    assert len(sample) == 2
    assert "ctx_lead" not in sample[0] and "labeler_block" not in sample[0]
    changed = copy.deepcopy(cases)
    for c in changed:
        c["ctx_lead"] = "DIFFERENT"
        c["recovery_route"] = "none"
    assert sample == A.review_sample(changed, chunks, per_stratum=1)
    assert all(s["review"]["actor"]["status"] == "unreviewed" for s in sample)


def manifest(tmp_path):
    data = (json.dumps(chunk(0, "The operator shall:\n(a) Review logs.")) + "\n").encode()
    (tmp_path / "chunks.jsonl").write_bytes(data)
    m = {"documents": {d: {"chunks": "chunks.jsonl", "chunks_sha256": A.sha(data)} for d in A.DOCS}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(m))
    return path, m


def test_cli_workflow_retains_unknown_metrics_and_never_overwrites(tmp_path):
    path, _ = manifest(tmp_path)
    before = (tmp_path / "chunks.jsonl").read_bytes()
    output = tmp_path / "scratch"
    summary = A.run(path, output)
    assert summary["model_calls"] == summary["production_writes"] == 0
    assert summary["attachment_accuracy"] is None
    assert summary["true_cross_chunk_relationship_rate"] is None
    assert set(summary["by_document"]) == set(A.DOCS)
    assert (tmp_path / "chunks.jsonl").read_bytes() == before
    saved = (output / "summary.json").read_bytes()
    with pytest.raises(FileExistsError):
        A.run(path, output)
    assert (output / "summary.json").read_bytes() == saved


def test_tampered_snapshot_fails_before_output_creation(tmp_path):
    path, _ = manifest(tmp_path)
    (tmp_path / "chunks.jsonl").write_text("{}\n")
    output = tmp_path / "scratch"
    with pytest.raises(ValueError, match="hash mismatch"):
        A.run(path, output)
    assert not output.exists()


def test_partial_document_manifest_is_not_silently_scored(tmp_path):
    path, m = manifest(tmp_path)
    del m["documents"][A.DOCS[0]]
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="exactly the seven"):
        A.run(path, tmp_path / "scratch")


def test_tables_are_not_counted_as_list_shaped():
    counts, _ = A.audit_document("example", [chunk(0, "| Actor | Action |\n|---|---|\n| Staff | Log events |")])
    assert counts["list_shaped_clauses"] == 0
    assert counts["table_shaped_clauses"] > 0
