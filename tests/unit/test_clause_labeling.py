"""Clause labeling (pipeline/clause_labeling.py): frozen prompt, strict parse, batching, ledger and resume, failures, rows and citations. No model is called: the
Ollama call is a fake. Expected values are written by hand from the design (extraction-replacement-design_2026-10-22.md, sections 1 and 2)."""
import hashlib
import json
import re
from pathlib import Path

import pytest
import requests

from pipeline import clause_labeling as cl
from pipeline.sentence_expand import tidy

REPO = Path(__file__).resolve().parents[2]
FROZEN_SHA = "b9b20379597d04b346f6d7f30b1e6df6257f86fd15c372588dc06a1bbdd8dbc4"

CHUNKS = [
    {"chunk_id": 0, "raw_text": "3.1. Purpose. This manual sets policy.\n3.1.1. Units shall keep logs. Units shall not share passwords.",
     "section_title_path": ["CHAPTER 3", "3.1. Purpose."], "section_ref_path": ["3.1"], "parent_header_text": "3.1. Purpose."},
    {"chunk_id": 1, "raw_text": "Table 3.1. Roles.\n| Role | Duty |\n|---|---|\n| ISSM | Reviews logs and shall sign |",
     "section_title_path": ["CHAPTER 3", "3.2. Roles."], "section_ref_path": ["3.2"], "parent_header_text": "3.2. Roles."},
    {"chunk_id": 2, "raw_text": "The ISSM may approve   waivers.", "section_title_path": ["CHAPTER 4", "4.2. Waivers."], "section_ref_path": ["4.2"]},
    {"chunk_id": 3, "raw_text": "Personnel will comply.", "section_title_path": [], "section_ref_path": []},
]
# The fake model's answer for each clause, by its words (the clause list is written out by hand in test_deterministic_batching_in_document_order).
EXPECTED_ROWS = [  # (chunk_id, clause_index, label, source_quote, source_ref, origin)
    (0, 2, "DUTY", "Units shall keep logs.", "3.1.1", "own_number"),
    (0, 3, "PROHIBITION", "Units shall not share passwords.", "3.1.1", "number_above"),
    (1, 2, "DUTY", "| ISSM | Reviews logs and shall sign |", "Table 3.1", "table_caption"),
    (2, 0, "PERMISSION", "The ISSM may approve waivers.", "4.2", "section_path"),
    (3, 0, "DUTY", "Personnel will comply.", "", "none"),
]


def _clauses_in(prompt):
    return re.findall(r"\[\d+\]\nContext: [^\n]*\nClause: ([^\n]*)", prompt)


def _label(text):
    if "shall not" in text:
        return "PROHIBITION"
    if " may " in text:
        return "PERMISSION"
    if "shall" in text or "will" in text:
        return "DUTY"
    return "NOT_REQUIREMENT"


class FakeModel:
    """Answers like a well-behaved model; `script` overrides answers for given call numbers (a string, or an exception to raise)."""

    def __init__(self, script=None):
        self.script = script or {}
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        step = self.script.get(len(self.prompts))
        if isinstance(step, Exception):
            raise step
        if step is not None:
            return step
        return json.dumps([{"id": i, "label": _label(t)} for i, t in enumerate(_clauses_in(prompt), 1)])


def _write_chunks(tmp_path, chunks=CHUNKS):
    p = tmp_path / "doc_chunks.jsonl"
    p.write_text("".join(json.dumps(c) + "\n" for c in chunks), encoding="utf-8")
    return p


def _read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _run(tmp_path, call):
    out = cl.run(str(_write_chunks(tmp_path)), str(tmp_path / "out"), model="ornith:35b", call=call)
    return _read(out)


# ---- prompt
def test_the_prompt_file_is_the_frozen_one():
    path = REPO / "pipeline" / "prompts" / "clause_label_v3.txt"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN_SHA
    assert cl.PROMPT_SHA256 == FROZEN_SHA
    assert cl.load_prompt().count("{CLAUSES}") == 1


def test_a_changed_prompt_file_is_refused(tmp_path):
    p = tmp_path / "p.txt"
    p.write_bytes((REPO / "pipeline" / "prompts" / "clause_label_v3.txt").read_bytes() + b" ")
    with pytest.raises(RuntimeError, match="frozen"):
        cl.load_prompt(p)


def test_the_prompt_is_filled_by_replace_and_keeps_its_json_braces():
    item = {"text": "Units shall  keep logs.", "heading": "3.1. Purpose.", "ref": "3.1", "ctx_lead": None}
    prompt = cl.build_prompt(cl.load_prompt(), [item])
    assert '[{"id": 1, "label": "DUTY"}, {"id": 2, "label": "NOT_REQUIREMENT"}]' in prompt
    assert "{CLAUSES}" not in prompt
    assert prompt.endswith("[1]\nContext: Heading: 3.1. Purpose. | Paragraph: 3.1\nClause: Units shall keep logs.\n")


def test_clause_block_cuts_each_context_field_and_the_clause_to_its_limit():
    item = {"text": "c" * 1500, "heading": "h" * 200, "ref": "r" * 100, "ctx_lead": "l" * 400}
    block = cl.clause_block([item, {"text": "Second.", "heading": "", "ref": "", "ctx_lead": None}])
    assert block == ("[1]\nContext: Heading: " + "h" * 150 + " | Paragraph: " + "r" * 60 + " | Lead-in line above: " + "l" * 300 + "\nClause: " + "c" * 1200
                     + "\n\n[2]\nContext: (none)\nClause: Second.")


# ---- parse
def test_parse_a_valid_answer():
    assert cl.parse('[{"id": 1, "label": "DUTY"}, {"id": 2, "label": "NOT_REQUIREMENT"}]', 2) == ["DUTY", "NOT_REQUIREMENT"]
    assert cl.parse('[{"id": 2, "label": "permission"}, {"id": "[1]", "label": "not requirement"}]', 2) == ["NOT_REQUIREMENT", "PERMISSION"]


def test_parse_ignores_text_around_the_json():
    assert cl.parse('Here you go:\n```json\n[{"id": 1, "label": "UNSURE"}]\n```\nDone.', 1) == ["UNSURE"]


def test_parse_refuses_a_missing_or_extra_id():
    assert cl.parse('[{"id": 1, "label": "DUTY"}]', 2) is None
    assert cl.parse('[{"id": 1, "label": "DUTY"}, {"id": 2, "label": "DUTY"}, {"id": 3, "label": "DUTY"}]', 2) is None


def test_parse_refuses_an_unknown_label_or_a_non_object():
    assert cl.parse('[{"id": 1, "label": "OBLIGATION"}]', 1) is None
    assert cl.parse('[1]', 1) is None
    assert cl.parse("no json here", 1) is None
    assert cl.parse('[{"id": 1, "label": "DUTY"', 1) is None


# ---- batching
def test_deterministic_batching_in_document_order():
    clauses = cl.document_clauses(CHUNKS)
    assert [(c["chunk_id"], c["clause_index"], c["text"]) for c in clauses] == [
        (0, 0, "3.1. Purpose. "),
        (0, 1, "This manual sets policy."),
        (0, 2, "Units shall keep logs. "),
        (0, 3, "Units shall not share passwords."),
        (1, 0, "Table 3.1. Roles."),
        (1, 1, "| Role | Duty |"),
        (1, 2, "| ISSM | Reviews logs and shall sign |"),
        (2, 0, "The ISSM may approve   waivers."),
        (3, 0, "Personnel will comply."),
    ]
    batches = cl.make_batches(clauses)
    assert [(b["batch_id"], b["clause_keys"], b["chunk_ids"]) for b in batches] == [
        ("b00000", [[0, 0], [0, 1], [0, 2], [0, 3]], [0]),
        ("b00001", [[1, 0], [1, 1], [1, 2], [2, 0]], [1, 2]),
        ("b00002", [[3, 0]], [3]),
    ]
    assert cl.make_batches(cl.document_clauses(CHUNKS)) == batches


# ---- the run
def test_rows_are_the_flagged_clauses_with_citations_and_exact_anchors(tmp_path):
    rows = _run(tmp_path, FakeModel())
    assert [(r["chunk_id"], r["clause_index"], r["clause_label"], r["source_quote"], r["source_ref"], r["source_ref_origin"]) for r in rows] == EXPECTED_ROWS
    for r in rows:
        assert r["anchor_status"] == "exact"
        assert r["schema_version"] == "3.0" and r["pipeline_version"] == "2.0"
        assert r["label_prompt_sha"] == FROZEN_SHA and r["extraction_model"] == "ornith:35b"
        assert r["description"] == "" and r["domain_tags"] == [] and r["requirement_type"] == ""
        assert r["requirement_id"] == f"R-{r['chunk_id']}-{r['clause_index']}"
    assert rows[3]["anchor_start"] == 0 and rows[3]["anchor_end"] == 31


def test_invariant_tidy_of_the_anchored_source_slice_is_the_quote(tmp_path):
    raw = {c["chunk_id"]: c["raw_text"] for c in CHUNKS}
    rows = _run(tmp_path, FakeModel())
    assert rows
    for r in rows:
        assert raw[r["chunk_id"]][r["anchor_start"]:r["anchor_end"]] == r["anchor_text"]
        assert tidy(raw[r["chunk_id"]][r["anchor_start"]:r["anchor_end"]]) == r["source_quote"]


def test_not_requirement_clauses_are_not_written(tmp_path):
    rows = _run(tmp_path, FakeModel())
    assert all(r["clause_label"] != "NOT_REQUIREMENT" for r in rows)
    assert (0, 1) not in {(r["chunk_id"], r["clause_index"]) for r in rows}  # "This manual sets policy."


def test_a_second_attempt_rescues_a_bad_first_answer(tmp_path):
    model = FakeModel({1: "I think these are duties."})
    rows = _run(tmp_path, model)
    assert len(model.prompts) == 4  # batch 1 twice, then batches 2 and 3
    assert [(r["chunk_id"], r["clause_index"]) for r in rows] == [(0, 2), (0, 3), (1, 2), (2, 0), (3, 0)]
    ledger = _read(tmp_path / "out" / "doc_raw_responses.jsonl")
    assert (ledger[0]["status"], ledger[0]["attempts"]) == ("complete", 2)
    assert _read(tmp_path / "out" / "doc_parse_failures.jsonl") == []


def test_an_unparsed_batch_makes_every_clause_unsure_and_logs_a_parse_failure(tmp_path):
    model = FakeModel({1: "nonsense", 2: '[{"id": 1, "label": "DUTY"}]'})
    rows = _run(tmp_path, model)
    assert [(r["chunk_id"], r["clause_index"], r["clause_label"]) for r in rows if r["chunk_id"] == 0] == [
        (0, 0, "UNSURE"), (0, 1, "UNSURE"), (0, 2, "UNSURE"), (0, 3, "UNSURE")]
    failures = _read(tmp_path / "out" / "doc_parse_failures.jsonl")
    assert len(failures) == 1
    assert failures[0]["batch_id"] == "b00000" and failures[0]["error"] == "unparsed_labels"
    assert failures[0]["clause_keys"] == [[0, 0], [0, 1], [0, 2], [0, 3]]
    assert failures[0]["raw_answers"] == ["nonsense", '[{"id": 1, "label": "DUTY"}]']
    assert _read(tmp_path / "out" / "doc_raw_responses.jsonl")[0]["status"] == "unparsed"


def test_a_connection_failure_fails_the_batch_and_its_chunks_get_no_rows(tmp_path):
    model = FakeModel({2: requests.ConnectionError("refused")})  # batch 2 holds chunks 1 and 2
    rows = _run(tmp_path, model)
    assert [(r["chunk_id"], r["clause_index"]) for r in rows] == [(0, 2), (0, 3), (3, 0)]
    ledger = _read(tmp_path / "out" / "doc_raw_responses.jsonl")
    assert [(r["batch_id"], r["status"]) for r in ledger] == [("b00000", "complete"), ("b00001", "failed"), ("b00002", "complete")]
    assert ledger[1]["labels"] is None and "refused" in ledger[1]["error"]


def test_the_ledger_line_records_the_batch(tmp_path):
    _run(tmp_path, FakeModel())
    first = _read(tmp_path / "out" / "doc_raw_responses.jsonl")[0]
    assert first["batch_id"] == "b00000" and first["chunk_ids"] == [0] and first["clause_keys"] == [[0, 0], [0, 1], [0, 2], [0, 3]]
    assert first["model"] == "ornith:35b" and first["prompt_sha"] == FROZEN_SHA
    assert first["labels"] == ["NOT_REQUIREMENT", "NOT_REQUIREMENT", "DUTY", "PROHIBITION"]
    assert first["raw_answer"].startswith("[{") and first["status"] == "complete"


def test_resume_reuses_finished_batches_and_redoes_failed_ones(tmp_path):
    _run(tmp_path, FakeModel({2: requests.ConnectionError("refused")}))
    again = FakeModel()
    rows = _run(tmp_path, again)
    assert len(again.prompts) == 1
    assert "[3]\nContext: Heading: 3.2. Roles. | Paragraph: 3.2\nClause: | ISSM | Reviews logs and shall sign |" in again.prompts[0]
    assert [(r["chunk_id"], r["clause_index"]) for r in rows] == [(0, 2), (0, 3), (1, 2), (2, 0), (3, 0)]
    third = FakeModel()
    _run(tmp_path, third)
    assert third.prompts == []


def test_resume_does_not_reuse_another_models_answers(tmp_path):
    _run(tmp_path, FakeModel())
    other = FakeModel()
    cl.run(str(_write_chunks(tmp_path)), str(tmp_path / "out"), model="llama3.1:8b", call=other)
    assert len(other.prompts) == 3


def test_a_run_of_failed_batches_stops_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "MAX_FAILED_IN_A_ROW", 2)
    model = FakeModel({1: requests.ConnectionError("down"), 2: requests.ConnectionError("down")})
    rows = _run(tmp_path, model)
    assert len(model.prompts) == 2 and rows == []
    assert [r.get("error") for r in _read(tmp_path / "out" / "doc_raw_responses.jsonl")] == ["down", "down", "not_attempted"]


def test_a_stable_id_comes_from_the_existing_recipe_when_the_document_is_known(tmp_path):
    from pipeline.parse_and_normalize import compute_stable_id
    out = cl.run(str(_write_chunks(tmp_path)), str(tmp_path / "out"), model="m", call=FakeModel(), document_id="doc-1")
    first = _read(out)[0]
    assert first["requirement_id"] == compute_stable_id(document_id="doc-1", source_ref="3.1.1", source_quote="Units shall keep logs.", chunk_id=0,
                                                        requirement_type="", description="")
    assert first["requirement_id"].startswith("REQ-")


# ---- citations
def test_each_source_ref_origin():
    chunk = {"chunk_id": 9, "raw_text": "A2.1. Scope text here.\nMore text follows.\n- 2.5.1.1. The ISSO shall act.", "section_title_path": ["Attachment 2"]}
    clauses = cl.document_clauses([chunk])
    assert cl.source_refs(chunk, chunk["raw_text"], clauses) == [("A2.1", "own_number"), ("A2.1", "number_above"), ("2.5.1.1", "own_number")]
    assert cl.source_refs({"section_title_path": ["X"], "section_ref_path": ["7.3"]}, "Do it.", cl.document_clauses([{"chunk_id": 1, "raw_text": "Do it."}])) == [
        ("7.3", "section_path")]


def test_a_number_inside_a_table_cell_is_not_the_rows_paragraph():
    chunk = {"chunk_id": 1, "raw_text": "| 3.4.1 | Review logs |"}
    clauses = cl.document_clauses([chunk])
    assert cl.source_refs(chunk, chunk["raw_text"], clauses) == [("", "none")]


# ---- the Ollama call
class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


def test_think_is_off_and_retried_without_it_for_a_model_that_refuses_it(monkeypatch):
    bodies = []

    def post(url, json, timeout):
        bodies.append(dict(json))
        if "think" in json:
            return _Resp(400, text='{"error":"model does not support thinking"}')
        return _Resp(200, {"message": {"content": "[]"}})

    monkeypatch.setattr(requests, "post", post)
    assert cl.ollama_chat("p", model="m", ollama_url="http://ollama.invalid:11434/") == "[]"
    assert bodies[0]["think"] is False and "think" not in bodies[1]
    assert bodies[0]["options"] == {"temperature": 0, "num_ctx": 8192, "num_predict": 300}
    assert bodies[0]["messages"] == [{"role": "user", "content": "p"}]


def test_request_errors_are_retried_with_backoff_then_raised(monkeypatch):
    sleeps, calls = [], []
    monkeypatch.setattr(cl, "_sleep", sleeps.append)

    def post(url, json, timeout):
        calls.append(url)
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(OSError):
        cl.ollama_chat("p", model="m", ollama_url="http://ollama.invalid:11434")
    assert sleeps == [2, 4, 8] and len(calls) == 4
    assert calls[0] == "http://ollama.invalid:11434/api/chat"


def test_nothing_calls_the_writer_yet():
    users = [p for d in ("api", "cli", "core", "mcp_server", "pipeline", "services") for p in (REPO / d).rglob("*.py")
             if "clause_labeling" in p.read_text(encoding="utf-8") and p.name != "clause_labeling.py"]
    assert users == []


# ---- reviewer findings on #363
def test_parse_refuses_a_duplicate_id():
    # Codex P2: ids 1, 1, 2 were accepted and one label silently dropped.
    assert cl.parse('[{"id": 1, "label": "DUTY"}, {"id": 1, "label": "NOT_REQUIREMENT"}, {"id": 2, "label": "DUTY"}]', 2) is None


def test_a_section_path_stored_as_a_string_still_gives_the_citation():
    # Codex P2: older chunk files store the path as "['1', '1.3']"; the prompt showed 1.3 but the row lost it.
    chunk = {"chunk_id": 4, "raw_text": "Do it.", "section_title_path": "['CHAPTER 1', 'Scope']", "section_ref_path": "['1', '1.3']"}
    assert cl.source_refs(chunk, chunk["raw_text"], cl.document_clauses([chunk])) == [("1.3", "section_path")]
    titled = {"chunk_id": 5, "raw_text": "Do it.", "section_title_path": "['CHAPTER 1', '1.4. Scope.']"}
    assert cl.source_refs(titled, titled["raw_text"], cl.document_clauses([titled])) == [("1.4", "section_path")]


def test_a_retried_batch_leaves_one_ledger_line_so_the_run_reads_as_complete(tmp_path):
    # Codex P2: index_replace.extraction_gaps counts every "failed" line, so a failure redone on resume must not stay in the ledger.
    from pipeline.index_replace import extraction_gaps
    _run(tmp_path, FakeModel({2: requests.ConnectionError("refused")}))
    ledger_path = tmp_path / "out" / "doc_raw_responses.jsonl"
    assert extraction_gaps(ledger_path) == {"failed": 1}
    _run(tmp_path, FakeModel())
    assert [(r["batch_id"], r["status"]) for r in _read(ledger_path)] == [("b00000", "complete"), ("b00001", "complete"), ("b00002", "complete")]
    assert extraction_gaps(ledger_path) == {}


def test_batches_left_after_a_stopped_run_are_recorded_as_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "MAX_FAILED_IN_A_ROW", 1)
    _run(tmp_path, FakeModel({1: requests.ConnectionError("down")}))
    ledger = _read(tmp_path / "out" / "doc_raw_responses.jsonl")
    assert [(r["batch_id"], r["status"], r.get("error")) for r in ledger] == [
        ("b00000", "failed", "down"), ("b00001", "failed", "not_attempted"), ("b00002", "failed", "not_attempted")]
