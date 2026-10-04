"""WP-45.0.2: Step C completion ledger.

A chunk counts as done only when its answer finished and its output is durable: failed requests and
unparseable answers are retried on resume, a cut-off answer gets one larger retry (sized from the prompt,
inside the context window) and is otherwise kept and flagged, the raw record is written last as the
completion marker, and a retry replaces a chunk's earlier rows instead of duplicating them.

The LLM is a scripted fake (_Llm) that returns a chosen outcome per call, so every path is exercised and
every Ollama call is counted. No network.
"""
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

import pipeline.llm_extract_requirements as L
from pipeline.llm_extract_requirements import (
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_TRUNCATED,
    _drop_chunk_rows,
    _prompt_tokens,
    _record_status,
    call_ollama,
    process_chunk,
    run,
)

# ---------------------------------------------------------------------------
# scripted fake LLM
# ---------------------------------------------------------------------------

def _items(marker, n):
    return [{"source_quote": f"Systems shall protect {marker} control {i}.", "source_ref": str(i)} for i in range(n)]


def _ok(marker, n=1, prompt_tokens=900):
    return ("resp", json.dumps({"requirements": _items(marker, n)}), {"done_reason": "stop", "prompt_eval_count": prompt_tokens})


def _cut(marker, n=1, prompt_tokens=900):
    """An answer that hit the output limit mid-object: n complete items, then a fragment."""
    text = json.dumps({"requirements": _items(marker, n)})[:-2] + ', {"source_quote": "Systems shall cut o'
    return ("resp", text, {"done_reason": "length", "prompt_eval_count": prompt_tokens})


def _empty():
    return ("resp", json.dumps({"requirements": []}), {"done_reason": "stop", "prompt_eval_count": 900})


BAD = ("resp", "this is not json at all", {"done_reason": "stop", "prompt_eval_count": 900})
RAISE = ("raise",)


class _Llm:
    """Stands in for call_ollama. script maps a marker found in the prompt to a list of outcomes, consumed
    one per call (the last one repeats)."""

    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []  # (marker, num_predict, timeout)

    def __call__(self, prompt, model, base_url, timeout, max_retries=3, json_schema=None, *,
                 num_predict=OLLAMA_NUM_PREDICT, meta=None):
        marker = next(m for m in self.script if m in prompt)
        self.calls.append((marker, num_predict, timeout))
        queue = self.script[marker]
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if outcome[0] == "raise":
            raise requests.ConnectionError("boom")
        _, text, info = outcome
        if meta is not None:
            meta.update(info)
        return text

    def count(self, marker):
        return sum(1 for c in self.calls if c[0] == marker)


def _chunks(path, texts):
    path.write_text("".join(json.dumps({"chunk_id": cid, "text": text}) + "\n" for cid, text in texts.items()))


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()] if Path(path).exists() else []


def _run(tmp_path, texts, llm, model="m", **kwargs):
    chunks = tmp_path / "doc_chunks.jsonl"
    _chunks(chunks, texts)
    tags = MagicMock(json=lambda: {"models": [{"name": model}]})
    with patch.object(L, "call_ollama", llm), patch.object(L.requests, "get", return_value=tags):
        return run(str(chunks), str(tmp_path), model=model, ollama_url="http://x", **kwargs)


def _files(tmp_path):
    return (
        _rows(tmp_path / "doc_raw_responses.jsonl"),
        _rows(tmp_path / "doc_extracted_requirements.jsonl"),
        _rows(tmp_path / "doc_parse_failures.jsonl"),
    )


TEXTS = {0: "Chunk ALPHA text.", 1: "Chunk BRAVO text."}


# ---------------------------------------------------------------------------
# call_ollama: the allowance is a parameter, the response metadata is reported
# ---------------------------------------------------------------------------

def _post_returning(data):
    response = MagicMock()
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return patch.object(L.requests, "post", return_value=response)


def test_call_ollama_defaults_to_the_named_allowance_and_returns_text():
    with _post_returning({"response": "hi"}) as post:
        out = call_ollama("p", "m", "http://x")
    assert out == "hi"
    assert post.call_args.kwargs["json"]["options"]["num_predict"] == OLLAMA_NUM_PREDICT == 4096
    assert post.call_args.kwargs["json"]["options"]["num_ctx"] == OLLAMA_NUM_CTX


def test_call_ollama_honors_a_larger_allowance_and_fills_meta():
    meta = {}
    data = {"response": "hi", "done_reason": "length", "prompt_eval_count": 31, "eval_count": 6000}
    with _post_returning(data) as post:
        out = call_ollama("p", "m", "http://x", num_predict=6000, meta=meta)
    assert out == "hi"
    assert post.call_args.kwargs["json"]["options"]["num_predict"] == 6000
    assert meta == {"done_reason": "length", "prompt_eval_count": 31, "eval_count": 6000}


# ---------------------------------------------------------------------------
# process_chunk: status, truncation detection, and the bounded larger retry
# ---------------------------------------------------------------------------

def _chunk(text="Chunk ALPHA text."):
    return {"chunk_id": 7, "text": text}


def _process(llm, text="Chunk ALPHA text.", timeout=100):
    with patch.object(L, "call_ollama", llm):
        return process_chunk(_chunk(text), model="m", base_url="http://x", timeout=timeout)


def test_a_finished_answer_is_complete():
    llm = _Llm({"ALPHA": [_ok("ALPHA", 2)]})
    raw, reqs, failure = _process(llm)
    assert (raw["status"], raw["done_reason"], raw["num_predict"], raw["retried_larger"]) == (
        STATUS_COMPLETE, "stop", OLLAMA_NUM_PREDICT, False)
    assert len(reqs) == 2 and failure is None
    assert not any(r.get("recovered_truncated") for r in reqs)
    assert len(llm.calls) == 1


def test_a_valid_empty_answer_is_complete():
    raw, reqs, failure = _process(_Llm({"ALPHA": [_empty()]}))
    assert raw["status"] == STATUS_COMPLETE and reqs == [] and failure is None


def test_a_request_error_is_failed():
    raw, reqs, failure = _process(_Llm({"ALPHA": [RAISE]}))
    assert raw["status"] == STATUS_FAILED and reqs == []
    assert failure["error"].startswith("ollama_request_failed")
    assert raw["raw_response"].startswith("ERROR:")


def test_unparseable_output_is_failed():
    raw, reqs, failure = _process(_Llm({"ALPHA": [BAD]}))
    assert raw["status"] == STATUS_FAILED and reqs == []
    assert failure["error"] == "json_parse_failed"


def test_a_cut_off_answer_gets_one_larger_retry_sized_from_the_prompt():
    llm = _Llm({"ALPHA": [_cut("ALPHA", 1, prompt_tokens=1000), _ok("ALPHA", 3, prompt_tokens=1000)]})
    raw, reqs, failure = _process(llm, timeout=100)

    room = OLLAMA_NUM_CTX - 1000 - L._CTX_MARGIN
    assert [c[1] for c in llm.calls] == [OLLAMA_NUM_PREDICT, room]
    assert room > OLLAMA_NUM_PREDICT
    assert llm.calls[1][2] > llm.calls[0][2]  # a longer answer is given a proportionally longer timeout
    assert raw["status"] == STATUS_COMPLETE and raw["retried_larger"] is True and raw["num_predict"] == room
    assert len(reqs) == 3 and failure is None
    assert not any(r.get("recovered_truncated") for r in reqs)


def test_the_retry_never_exceeds_the_window():
    llm = _Llm({"ALPHA": [_cut("ALPHA", 1, prompt_tokens=2500), _ok("ALPHA")]})
    _process(llm)
    assert llm.calls[1][1] + 2500 <= OLLAMA_NUM_CTX


def test_no_retry_when_the_window_has_no_room_and_the_chunk_is_kept_flagged():
    llm = _Llm({"ALPHA": [_cut("ALPHA", 2, prompt_tokens=4200)]})  # 8192 - 4200 - 64 < 4096
    raw, reqs, failure = _process(llm)
    assert len(llm.calls) == 1
    assert raw["status"] == STATUS_TRUNCATED and raw["retried_larger"] is False
    assert len(reqs) == 2 and all(r["recovered_truncated"] for r in reqs)
    assert failure is None


def test_when_the_retry_is_also_cut_off_the_better_recovery_wins():
    more = _Llm({"ALPHA": [_cut("ALPHA", 1), _cut("ALPHA", 3)]})
    raw, reqs, _ = _process(more)
    assert (raw["status"], len(reqs), raw["num_predict"] > OLLAMA_NUM_PREDICT) == (STATUS_TRUNCATED, 3, True)

    fewer = _Llm({"ALPHA": [_cut("ALPHA", 3), _cut("ALPHA", 1)]})
    raw, reqs, _ = _process(fewer)
    assert (raw["status"], len(reqs), raw["num_predict"]) == (STATUS_TRUNCATED, 3, OLLAMA_NUM_PREDICT)
    assert len(fewer.calls) == 2  # exactly one retry, never a loop


def test_a_failed_retry_keeps_the_first_answer():
    raw, reqs, _ = _process(_Llm({"ALPHA": [_cut("ALPHA", 2), RAISE]}))
    assert raw["status"] == STATUS_TRUNCATED and raw["retried_larger"] is True
    assert len(reqs) == 2 and raw["num_predict"] == OLLAMA_NUM_PREDICT


def test_a_cut_off_answer_with_nothing_recoverable_is_failed_not_kept():
    cut_nothing = ("resp", '{"requirements": [{"source_quote": "Systems shall cu', {"done_reason": "length", "prompt_eval_count": 900})
    raw, reqs, failure = _process(_Llm({"ALPHA": [cut_nothing]}))
    assert raw["status"] == STATUS_FAILED and reqs == []
    assert failure["error"] == "json_parse_failed" and failure["truncated"] is True


def test_ollamas_done_reason_alone_marks_a_chunk_truncated():
    """Even if the JSON happens to parse whole, done_reason "length" means the allowance was hit."""
    whole = ("resp", json.dumps({"requirements": _items("ALPHA", 1)}), {"done_reason": "length", "prompt_eval_count": 4200})
    raw, reqs, _ = _process(_Llm({"ALPHA": [whole]}))
    assert raw["status"] == STATUS_TRUNCATED and reqs[0]["recovered_truncated"] is True


def test_prompt_size_falls_back_to_a_cautious_estimate_when_ollama_reports_none():
    assert _prompt_tokens({"prompt_eval_count": 31}, "x" * 300) == 31
    assert _prompt_tokens({}, "x" * 300) == 100
    assert _prompt_tokens({"prompt_eval_count": 0}, "x" * 301) == 101


# ---------------------------------------------------------------------------
# _record_status and _drop_chunk_rows
# ---------------------------------------------------------------------------

def test_record_status_uses_the_written_status_else_classifies_the_stored_response():
    assert _record_status({"status": "truncated", "raw_response": "garbage"}) == STATUS_TRUNCATED
    # records written before WP-45.0.2 have no status
    assert _record_status({"raw_response": "ERROR: boom"}) == STATUS_FAILED
    assert _record_status({"raw_response": "not json"}) == STATUS_FAILED
    assert _record_status({"raw_response": ""}) == STATUS_FAILED
    assert _record_status({"raw_response": json.dumps({"requirements": []})}) == STATUS_COMPLETE
    assert _record_status({"raw_response": _cut("A", 2)[1]}) == STATUS_TRUNCATED


def test_drop_chunk_rows_removes_only_those_chunks_and_keeps_odd_lines(tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_text('{"chunk_id": 1, "v": "a"}\n{"chunk_id": 2, "v": "b"}\nnot json\n{"chunk_id": 1, "v": "c"}\n\n')
    assert _drop_chunk_rows(path, {1}) == 2
    assert path.read_text() == '{"chunk_id": 2, "v": "b"}\nnot json\n'
    assert not (tmp_path / "f.jsonl.tmp").exists()
    assert _drop_chunk_rows(path, {99}) == 0
    assert _drop_chunk_rows(tmp_path / "missing.jsonl", {1}) == 0


# ---------------------------------------------------------------------------
# run(): resume semantics
# ---------------------------------------------------------------------------

def test_a_failed_request_is_retried_on_resume_and_its_requirements_land(tmp_path):
    """The audit's F02 reproduction: before this change the failed chunk was a permanent cache hit."""
    first = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [RAISE]})
    _run(tmp_path, TEXTS, first)
    raw, reqs, fails = _files(tmp_path)
    assert [r["status"] for r in raw] == [STATUS_COMPLETE, STATUS_FAILED]
    assert [r["chunk_id"] for r in reqs] == [0] and len(fails) == 1

    second = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO", 2)]})
    _run(tmp_path, TEXTS, second)

    assert second.count("ALPHA") == 0 and second.count("BRAVO") == 1
    raw, reqs, fails = _files(tmp_path)
    assert [r["status"] for r in raw] == [STATUS_COMPLETE, STATUS_COMPLETE]  # one record per chunk
    assert sorted(r["requirement_id"] for r in reqs) == ["R-0-0", "R-1-0", "R-1-1"]
    assert fails == []  # the earlier failure row was replaced, not kept


def test_unparseable_output_is_retried_on_resume(tmp_path):
    _run(tmp_path, TEXTS, _Llm({"ALPHA": [BAD], "BRAVO": [_ok("BRAVO")]}))
    second = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO")]})
    _run(tmp_path, TEXTS, second)
    assert (second.count("ALPHA"), second.count("BRAVO")) == (1, 0)
    assert len(_files(tmp_path)[1]) == 2


def test_a_truncated_chunk_is_kept_not_retried_and_the_summary_names_it(tmp_path, caplog):
    first = _Llm({"ALPHA": [_cut("ALPHA", 2, prompt_tokens=4200)], "BRAVO": [_ok("BRAVO")]})
    with caplog.at_level(logging.WARNING):
        _run(tmp_path, TEXTS, first)
    assert "hit the output limit and may be missing requirements" in caplog.text
    assert "[0]" in caplog.text

    caplog.clear()
    second = _Llm({"ALPHA": [_ok("ALPHA", 9)], "BRAVO": [_ok("BRAVO")]})
    with caplog.at_level(logging.WARNING):
        _run(tmp_path, TEXTS, second)
    assert second.calls == []  # nothing re-asked: no loop on a chunk that will cut off again
    assert "hit the output limit" in caplog.text  # still reported on the resume
    assert sorted(r["requirement_id"] for r in _files(tmp_path)[1]) == ["R-0-0", "R-0-1", "R-1-0"]


def test_a_crash_between_the_requirements_and_the_raw_record_does_not_duplicate_rows(tmp_path):
    """Order is requirements, failures, then the raw record last. Crash on that last write for chunk 1."""
    real_append = L.append_jsonl

    def crash_on_chunk_one_raw(record, handle):
        if "prompt_hash" in record and record["chunk_id"] == 1:
            raise RuntimeError("simulated crash")
        real_append(record, handle)

    with patch.object(L, "append_jsonl", crash_on_chunk_one_raw), pytest.raises(RuntimeError):
        _run(tmp_path, TEXTS, _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO", 2)]}))
    raw, reqs, _ = _files(tmp_path)
    assert [r["chunk_id"] for r in raw] == [0]                      # chunk 1 never got its completion marker
    assert sorted(r["requirement_id"] for r in reqs) == ["R-0-0", "R-1-0", "R-1-1"]  # but its rows were written

    second = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO", 2)]})
    _run(tmp_path, TEXTS, second)
    assert (second.count("ALPHA"), second.count("BRAVO")) == (0, 1)
    raw, reqs, _ = _files(tmp_path)
    assert sorted(r["requirement_id"] for r in reqs) == ["R-0-0", "R-1-0", "R-1-1"]  # no duplicates
    assert [r["chunk_id"] for r in raw] == [0, 1]


def test_identical_chunk_text_is_accounted_per_chunk_not_per_prompt(tmp_path):
    """Two chunks with the same text share a prompt hash. Chunk 1 failing must not be hidden by chunk 0
    having succeeded (the split-paragraph twins in the real corpus look exactly like this)."""
    twins = {0: "Chunk TWIN text.", 1: "Chunk TWIN text."}
    _run(tmp_path, twins, _Llm({"TWIN": [_ok("TWIN"), RAISE]}))
    assert [r["status"] for r in _files(tmp_path)[0]] == [STATUS_COMPLETE, STATUS_FAILED]

    second = _Llm({"TWIN": [_ok("TWIN")]})
    _run(tmp_path, twins, second)
    assert len(second.calls) == 1  # only chunk 1
    assert sorted(r["chunk_id"] for r in _files(tmp_path)[1]) == [0, 1]


def test_a_renumbered_chunk_is_re_extracted_not_matched_to_the_old_numbering(tmp_path):
    _run(tmp_path, {0: "Chunk ALPHA text.", 1: "Chunk BRAVO text."}, _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO")]}))
    second = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO")]})
    _run(tmp_path, {0: "Chunk BRAVO text.", 1: "Chunk ALPHA text."}, second)  # same texts, swapped ids
    assert len(second.calls) == 2
    raw, reqs, _ = _files(tmp_path)
    assert sorted(r["chunk_id"] for r in raw) == [0, 1] and len(reqs) == 2  # replaced, not appended


def test_a_valid_empty_result_stays_cached(tmp_path):
    _run(tmp_path, TEXTS, _Llm({"ALPHA": [_empty()], "BRAVO": [_ok("BRAVO")]}))
    second = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO")]})
    _run(tmp_path, TEXTS, second)
    assert second.calls == []
    assert _files(tmp_path)[0][0]["status"] == STATUS_COMPLETE


def test_a_different_model_does_not_reuse_the_cache(tmp_path):
    _run(tmp_path, TEXTS, _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO")]}), model="m")
    second = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO")]})
    _run(tmp_path, TEXTS, second, model="other")
    assert len(second.calls) == 2


def test_records_written_before_the_ledger_are_classified_from_their_stored_response(tmp_path):
    """No status field: an ok record counts as finished, an ERROR record is retried. Resuming an old run
    directory therefore costs nothing extra."""
    chunks = tmp_path / "doc_chunks.jsonl"
    _chunks(chunks, TEXTS)
    template = L.PASS1_PROMPT_TEMPLATE
    from core.profiles import default_profile
    rendered = template.replace("{obligation_verbs}", ", ".join(default_profile()["obligation_verbs"]))
    legacy = [
        {"chunk_id": 0, "model": "m", "prompt_hash": L._prompt_hash_for(rendered, TEXTS[0]),
         "raw_response": _ok("ALPHA")[1], "timestamp": "t"},
        {"chunk_id": 1, "model": "m", "prompt_hash": L._prompt_hash_for(rendered, TEXTS[1]),
         "raw_response": "ERROR: boom", "timestamp": "t"},
    ]
    (tmp_path / "doc_raw_responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in legacy))
    (tmp_path / "doc_extracted_requirements.jsonl").write_text(json.dumps({"chunk_id": 0, "requirement_id": "R-0-0"}) + "\n")
    (tmp_path / "doc_parse_failures.jsonl").write_text(json.dumps({"chunk_id": 1, "error": "ollama_request_failed"}) + "\n")

    second = _Llm({"ALPHA": [_ok("ALPHA")], "BRAVO": [_ok("BRAVO")]})
    _run(tmp_path, TEXTS, second)

    assert (second.count("ALPHA"), second.count("BRAVO")) == (0, 1)
    raw, reqs, fails = _files(tmp_path)
    assert [r["chunk_id"] for r in raw] == [0, 1] and raw[1]["status"] == STATUS_COMPLETE
    assert sorted(r["requirement_id"] for r in reqs) == ["R-0-0", "R-1-0"] and fails == []


def test_a_clean_run_then_a_resume_makes_no_second_pass(tmp_path):
    llm = _Llm({"ALPHA": [_ok("ALPHA", 2)], "BRAVO": [_ok("BRAVO", 3)]})
    _run(tmp_path, TEXTS, llm)
    assert len(llm.calls) == 2
    before = (tmp_path / "doc_extracted_requirements.jsonl").read_bytes()

    again = _Llm({"ALPHA": [_ok("ALPHA", 9)], "BRAVO": [_ok("BRAVO", 9)]})
    _run(tmp_path, TEXTS, again)
    assert again.calls == []
    assert (tmp_path / "doc_extracted_requirements.jsonl").read_bytes() == before


# ---------------------------------------------------------------------------
# Legacy (pre-ledger) run directories: the old loop wrote the raw record BEFORE the requirements, so an
# interrupted old run can hold a parseable raw record whose rows never landed. Such a chunk is unfinished.
# ---------------------------------------------------------------------------

def _legacy_dir(tmp_path, records, rows):
    """A run directory as the pre-ledger code left it: status-less raw records plus requirement rows."""
    from core.profiles import default_profile
    template = L.PASS1_PROMPT_TEMPLATE.replace("{obligation_verbs}", ", ".join(default_profile()["obligation_verbs"]))
    _chunks(tmp_path / "doc_chunks.jsonl", TEXTS)
    raw = [
        {"chunk_id": cid, "model": "m", "prompt_hash": L._prompt_hash_for(template, TEXTS[cid]),
         "raw_response": response, "timestamp": "t"}
        for cid, response in records
    ]
    (tmp_path / "doc_raw_responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in raw))
    (tmp_path / "doc_extracted_requirements.jsonl").write_text(
        "".join(json.dumps({"chunk_id": cid, "requirement_id": f"R-{cid}-{j}"}) + "\n" for cid, j in rows)
    )


def test_a_legacy_record_whose_rows_never_landed_is_redone(tmp_path):
    """Crash after the raw write, before the requirements: parseable answer, zero rows on disk."""
    _legacy_dir(tmp_path, [(0, _ok("ALPHA", 2)[1]), (1, _ok("BRAVO", 1)[1])], rows=[(0, 0), (0, 1)])
    second = _Llm({"ALPHA": [_ok("ALPHA", 2)], "BRAVO": [_ok("BRAVO", 1)]})
    _run(tmp_path, TEXTS, second)

    assert (second.count("ALPHA"), second.count("BRAVO")) == (0, 1)  # only the chunk with no rows
    assert sorted(r["requirement_id"] for r in _files(tmp_path)[1]) == ["R-0-0", "R-0-1", "R-1-0"]


def test_a_legacy_record_with_only_some_of_its_rows_is_redone_without_duplicates(tmp_path):
    _legacy_dir(tmp_path, [(0, _ok("ALPHA", 3)[1])], rows=[(0, 0)])  # crashed after 1 of 3 rows
    second = _Llm({"ALPHA": [_ok("ALPHA", 3)], "BRAVO": [_ok("BRAVO", 1)]})
    _run(tmp_path, TEXTS, second)

    assert second.count("ALPHA") == 1
    assert sorted(r["requirement_id"] for r in _files(tmp_path)[1] if r["chunk_id"] == 0) == ["R-0-0", "R-0-1", "R-0-2"]


def test_a_legacy_record_whose_rows_all_landed_is_not_redone(tmp_path):
    _legacy_dir(tmp_path, [(0, _ok("ALPHA", 2)[1]), (1, _empty()[1])], rows=[(0, 0), (0, 1)])  # chunk 1: valid empty, 0 rows
    second = _Llm({"ALPHA": [_ok("ALPHA", 9)], "BRAVO": [_ok("BRAVO", 9)]})
    _run(tmp_path, TEXTS, second)
    assert second.calls == []
