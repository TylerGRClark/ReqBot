"""WP-45.7: the shared Ollama client, the scratch ledger and the discovery and resolver runners (offline; Ollama is faked)."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"
_ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit"):
        sys.path.insert(0, str(p))
    try:
        spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_1e", _ROOT / "eval/spike_results/wp_45_audit"):
            sys.path.remove(str(p))


@pytest.fixture(scope="module")
def mods():
    names = ["bundle", "resolver", "check_resolution", "ollama_run", "discovery_prompts", "run_discovery", "run_resolver"]
    return {n: _load(n) for n in names}


# ---- ledger and keys ---------------------------------------------------------------------------------------------------


def test_the_ledger_resumes_finished_records_and_redoes_failed_ones(mods, tmp_path):
    OR = mods["ollama_run"]
    ledger = OR.Ledger(tmp_path / "x" / "l.jsonl")
    ledger.append({"key": "a", "status": "complete"})
    ledger.append({"key": "b", "status": "failed"})
    ledger.append({"key": "c", "status": "window_overrun"})
    ledger.append({"key": "d", "status": "untreatable"})
    again = OR.Ledger(tmp_path / "x" / "l.jsonl")
    assert [again.done(k) for k in "abcd"] == [True, False, True, True]  # a failure is redone, everything else is kept
    again.append({"key": "b", "status": "complete"})  # the redo replaces the failure
    assert OR.Ledger(tmp_path / "x" / "l.jsonl").done("b")
    with pytest.raises(ValueError):
        again.append({"key": "e", "status": "maybe"})


def test_keys_change_with_the_run_label_the_model_digest_and_the_prompt(mods):
    OR = mods["ollama_run"]
    base = OR.discovery_key("DOC", 3, "p1", "digestA", "r1")
    assert base == OR.discovery_key("DOC", 3, "p1", "digestA", "r1")
    assert len({base, OR.discovery_key("DOC", 3, "p1", "digestA", "r2"), OR.discovery_key("DOC", 3, "p1", "digestB", "r1"),
                OR.discovery_key("DOC", 3, "p2", "digestA", "r1"), OR.discovery_key("DOC", 4, "p1", "digestA", "r1")}) == 5
    r = OR.resolver_key("DOC", "c1", 15, "q", "b", "p", "dg", "run")
    assert r != OR.resolver_key("DOC", "c1", 15, "q", "b", "p", "dg", "run2") and r != OR.resolver_key("DOC", "c1", 15, "q", "b2", "p", "dg", "run")
    # the same quote in different chunks or as different candidates is a different key
    assert r != OR.resolver_key("DOC", "c2", 15, "q", "b", "p", "dg", "run") and r != OR.resolver_key("DOC", "c1", 19, "q", "b", "p", "dg", "run")


def test_classify_names_overruns_truncation_and_completion(mods):
    OR = mods["ollama_run"]
    assert OR.classify({"prompt_eval_count": 5000, "eval_count": 500, "done_reason": "stop"}) == "complete"
    assert OR.classify({"prompt_eval_count": 5000, "eval_count": 500, "done_reason": "length"}) == "truncated"
    assert OR.classify({"prompt_eval_count": 7800, "eval_count": 400, "done_reason": "stop"}) == "window_overrun"
    assert OR.classify({"prompt_eval_count": 8192, "eval_count": 1, "done_reason": "stop"}) == "window_overrun"


# ---- discovery prompts and runner --------------------------------------------------------------------------------------


def test_d0_is_the_production_prompt_and_d1_replaces_the_definition_and_examples(mods):
    DP = mods["discovery_prompts"]
    d0, d1 = DP.template("D0"), DP.template("D1")
    assert "{obligation_verbs}" not in d0 and "MUST DO" in d0  # production wording, verbs filled in
    assert "MUST DO" not in d1 and "CANDIDATE" in d1 and "General background" not in d1  # the old broad exclusion is gone
    for arm in DP.ARMS:
        assert "{chunk_text}" in DP.template(arm) and "{source_ref_hints}" in DP.template(arm)
        assert "Chunk body" in DP.render(arm, "Chunk body")
    assert DP.prompt_hash("D0") != DP.prompt_hash("D1")
    assert "Records Officer" in d1 and "Records Officer" not in d0  # invented examples only in D1


def test_the_d1_examples_are_valid_json_in_the_output_shape(mods):
    DP = mods["discovery_prompts"]
    for text, quotes, refs in DP._D1_EXAMPLES:
        assert len(quotes) == len(refs)
        for q in quotes:
            assert q in text  # every example quote is verbatim from its example text


def _fake_chunks():
    return [("DOC", {"chunk_id": i, "text": f"[X] 1.{i} Administrators shall review logs {i}."}) for i in (1, 2, 3)]


def _fake_generate(reply, **meta):
    base = {"done_reason": "stop", "prompt_eval_count": 900, "eval_count": 60, "total_duration": 1, "load_duration": 0, "wall_seconds": 0.5}
    base.update(meta)
    calls = []

    def gen(prompt, model, url, **kw):
        calls.append((model, kw.get("schema") is not None, kw.get("temperature"), kw.get("num_ctx")))
        return reply if isinstance(reply, str) else reply(prompt), dict(base)

    gen.calls = calls
    return gen


def test_the_discovery_runner_writes_records_resumes_and_uses_the_schema(mods, tmp_path, monkeypatch):
    RD, OR = mods["run_discovery"], mods["ollama_run"]
    reply = json.dumps({"requirements": [{"source_quote": "Administrators shall review logs 1.", "source_ref": ""}]})
    gen = _fake_generate(reply)
    monkeypatch.setattr(OR, "generate", gen)
    ledger = OR.Ledger(tmp_path / "d.jsonl")
    kw = dict(arm="D1", model="m", digest="dg", run_label="r1", ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    assert RD.run_chunks(_fake_chunks(), **kw) == 3
    assert all(c == ("m", True, 0.1, 8192) for c in gen.calls)  # schema-constrained, pinned context and temperature
    assert RD.run_chunks(_fake_chunks(), **kw) == 0  # resume: nothing is called again
    rows = RD.extracted_records(ledger)
    assert len(rows) == 3 and rows[0][1]["requirement_id"] == "R-1-1" and rows[0][1]["source_quote"].startswith("Administrators")
    # another run label does not reuse these answers
    kw2 = dict(kw, run_label="r2", ledger=OR.Ledger(tmp_path / "d2.jsonl"))
    assert RD.run_chunks(_fake_chunks(), **kw2) == 3
    paths = RD.write_extracted(ledger, tmp_path)
    assert [p.name for p in paths] == ["DOC_extracted_requirements.jsonl"]
    assert len(paths[0].read_text().splitlines()) == 3
    s = RD.summarize(ledger)
    assert s["status"] == {"complete": 3} and s["records"] == 3 and s["mean_prompt_tokens"] == 900.0


def test_an_overrun_answer_is_kept_in_the_ledger_but_exports_no_records(mods, tmp_path, monkeypatch):
    RD, OR = mods["run_discovery"], mods["ollama_run"]
    reply = json.dumps({"requirements": [{"source_quote": "Administrators shall review logs 1.", "source_ref": ""}]})
    monkeypatch.setattr(OR, "generate", _fake_generate(reply, prompt_eval_count=8100, eval_count=300))
    ledger = OR.Ledger(tmp_path / "ov.jsonl")
    RD.run_chunks(_fake_chunks()[:1], arm="D1", model="m", digest="dg", run_label="ov", ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    assert [r["status"] for r in ledger.records.values()] == ["window_overrun"]
    assert RD.extracted_records(ledger) == []  # an invalid call credits no candidate; the chunk stays a miss
    assert RD.write_extracted(ledger, tmp_path) == []
    assert RD.summarize(ledger)["status"] == {"window_overrun": 1}  # but it is counted


def test_an_overrun_a_truncation_a_bad_answer_and_a_failed_request_are_recorded_not_dropped(mods, tmp_path, monkeypatch):
    RD, OR = mods["run_discovery"], mods["ollama_run"]
    good = json.dumps({"requirements": []})
    for name, gen, expected in (
        ("overrun", _fake_generate(good, prompt_eval_count=8000, eval_count=300), "window_overrun"),
        ("truncated", _fake_generate(good, done_reason="length"), "truncated"),
        ("unparseable", _fake_generate("not json at all"), "failed"),
    ):
        monkeypatch.setattr(OR, "generate", gen)
        ledger = OR.Ledger(tmp_path / f"{name}.jsonl")
        RD.run_chunks(_fake_chunks()[:1], arm="D0", model="m", digest="dg", run_label=name, ledger=ledger,
                      ollama_url="http://x", log=lambda *a: None)
        assert [r["status"] for r in ledger.records.values()] == [expected], name

    def boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(OR, "generate", boom)
    ledger = OR.Ledger(tmp_path / "failed.jsonl")
    RD.run_chunks(_fake_chunks()[:1], arm="D0", model="m", digest="dg", run_label="f", ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    rec = next(iter(ledger.records.values()))
    assert rec["status"] == "failed" and rec["raw_response"].startswith("ERROR:")
    assert not ledger.done(rec["key"])  # redone on the next run


def test_a_prompt_over_the_cap_is_untreatable_and_never_sent(mods, tmp_path, monkeypatch):
    RD, OR = mods["run_discovery"], mods["ollama_run"]
    gen = _fake_generate(json.dumps({"requirements": []}))
    monkeypatch.setattr(OR, "generate", gen)
    ledger = OR.Ledger(tmp_path / "u.jsonl")
    huge = [("DOC", {"chunk_id": 1, "text": "word " * 9000})]
    assert RD.run_chunks(huge, arm="D0", model="m", digest="dg", run_label="u", ledger=ledger, ollama_url="http://x", log=lambda *a: None) == 0
    assert gen.calls == [] and next(iter(ledger.records.values()))["status"] == "untreatable"


def test_prompt_sizes_report_the_cap(mods):
    RD = mods["run_discovery"]
    s = RD.prompt_sizes(_fake_chunks(), "D1")
    assert s["over_prompt_cap"] == 0 and s["cap"] == 6500 and s["max"] >= s["mean"] > 0


# ---- resolver runner ---------------------------------------------------------------------------------------------------


def _docs():
    chunks = {
        1: {"chunk_id": 1, "raw_text": "4.2 The Records Officer will:", "parent_header_text": "4.2 RECORDS", "section_ref_path": ["4", "4.2"], "section_title_path": ["4. DUTIES", "4.2 RECORDS"]},
        2: {"chunk_id": 2, "raw_text": "b. Reviews disposal schedules each year.", "parent_header_text": "4.2 RECORDS", "section_ref_path": ["4", "4.2"], "section_title_path": ["4. DUTIES", "4.2 RECORDS"]},
    }
    return {"DOC": (chunks, {})}


def _cand(quote="b. Reviews disposal schedules each year."):
    return [{"candidate_id": "DOC:1", "document": "DOC", "chunk_id": 2, "quote": quote}]


def test_the_resolver_runner_validates_answers_and_records_issues(mods, tmp_path, monkeypatch):
    RR, OR, R = mods["run_resolver"], mods["ollama_run"], mods["resolver"]
    good = copy.deepcopy(R.EXAMPLES[0]["answer"])
    gen = _fake_generate(json.dumps(good))
    monkeypatch.setattr(OR, "generate", gen)
    ledger = OR.Ledger(tmp_path / "r.jsonl")
    calls = RR.run_candidates(_cand(), _docs(), tier="R1", model="m", digest="dg", run_label="r", ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    assert calls == 1 and gen.calls[0][1] is True  # sent with the resolver schema
    rec = next(iter(ledger.records.values()))
    assert rec["status"] == "complete" and rec["answer"]["status"]["value"] == "obligation"
    assert rec["bundle"]["tier"] == "R1" and rec["bundle"]["spans"][0]["id"] == "E1"
    assert any(i["code"] in ("bad_evidence_id", "not_in_cited_span") for i in rec["issues"])  # example E3 is not in this bundle
    s = RR.summarize(ledger)
    assert s["parsed"] == 1 and s["shape_conformant"] == 1 and s["fixed_prompt_estimated_tokens"] == R.fixed_tokens()
    assert RR.run_candidates(_cand(), _docs(), tier="R1", model="m", digest="dg", run_label="r", ledger=ledger, ollama_url="http://x", log=lambda *a: None) == 0
    # a different tier or run label is a different key
    assert RR.run_candidates(_cand(), _docs(), tier="R2", model="m", digest="dg", run_label="r", ledger=ledger, ollama_url="http://x", log=lambda *a: None) == 1


def test_a_non_json_resolver_answer_is_a_failure_and_shape_problems_are_counted(mods, tmp_path, monkeypatch):
    RR, OR = mods["run_resolver"], mods["ollama_run"]
    monkeypatch.setattr(OR, "generate", _fake_generate("this is not json"))
    ledger = OR.Ledger(tmp_path / "bad.jsonl")
    RR.run_candidates(_cand(), _docs(), tier="R1", model="m", digest="dg", run_label="b", ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    assert next(iter(ledger.records.values()))["status"] == "failed"
    monkeypatch.setattr(OR, "generate", _fake_generate(json.dumps({"status": {"value": "obligation", "evidence": []}})))
    ledger2 = OR.Ledger(tmp_path / "shape.jsonl")
    RR.run_candidates(_cand(), _docs(), tier="R1", model="m", digest="dg", run_label="s", ledger=ledger2, ollama_url="http://x", log=lambda *a: None)
    s = RR.summarize(ledger2)
    assert s["parsed"] == 1 and s["shape_conformant"] == 0 and s["error_codes"].get("shape")


def test_an_unfittable_bundle_is_untreatable_and_never_sent(mods, tmp_path, monkeypatch):
    RR, OR, R = mods["run_resolver"], mods["ollama_run"], mods["resolver"]
    gen = _fake_generate("{}")
    monkeypatch.setattr(OR, "generate", gen)
    monkeypatch.setattr(R, "fixed_tokens", lambda: 6450)  # a fixed prompt that leaves no room for any bundle
    ledger = OR.Ledger(tmp_path / "ut.jsonl")
    RR.run_candidates(_cand(), _docs(), tier="R2", model="m", digest="dg", run_label="u", ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    assert gen.calls == [] and next(iter(ledger.records.values()))["status"] == "untreatable"


def test_the_runners_validate_numeric_options_like_the_project(mods):
    import argparse

    for mod in ("run_discovery", "run_resolver"):
        m = mods[mod]
        with pytest.raises(argparse.ArgumentTypeError):
            m._positive_int("0")
        with pytest.raises(argparse.ArgumentTypeError):
            m._non_negative_float("-0.1")
        assert m._non_negative_float("0") == 0.0 and m._positive_int("8192") == 8192


def test_the_resolver_loader_serves_pinned_and_catalog_documents_and_rejects_others(mods, tmp_path, monkeypatch):
    """Offline: the pinned-input helpers are faked, so this runs in CI where the corpus files do not exist."""
    RR = mods["run_resolver"]
    import _inputs
    import chunk_sets as CS

    extracted = tmp_path / "x.jsonl"
    extracted.write_text(json.dumps({"chunk_id": 1, "requirement_id": "R-1-1", "source_quote": "q"}) + "\n")
    monkeypatch.setattr(_inputs, "corpus_inputs", lambda *kinds: {"PINNED": {"chunks": tmp_path / "c.jsonl", "extracted": extracted}})
    fake_chunks = {"PINNED": [{"chunk_id": 1, "raw_text": "a"}], "CATALOG": [{"chunk_id": 7, "raw_text": "b"}]}
    monkeypatch.setattr(CS, "load_document_chunks", lambda *docs: {d: fake_chunks[d] for d in docs})
    monkeypatch.setattr(CS.H, "CATALOG_DOCUMENTS", ("CATALOG",))
    docs = RR.load_documents(["PINNED", "CATALOG"])
    chunks, step = docs["PINNED"]
    assert set(chunks) == {1} and set(step) == {1}  # a pinned document has chunks and production Step C records
    cchunks, cstep = docs["CATALOG"]
    assert set(cchunks) == {7} and cstep == {}  # the catalog has its pinned chunks and no Step C records
    with pytest.raises(SystemExit):
        RR.load_documents(["not-a-document"])


def test_the_resolver_loader_serves_the_real_corpus_when_it_is_present(mods):
    RR = mods["run_resolver"]
    import _inputs

    try:
        _inputs.corpus_inputs("chunks", "extracted")
    except SystemExit:
        pytest.skip("the pinned corpus files are not on this machine")
    docs = RR.load_documents(["DODI 5200.44", "CNSSI_No1253"])
    assert docs["DODI 5200.44"][0] and docs["DODI 5200.44"][1] and docs["CNSSI_No1253"][0] and docs["CNSSI_No1253"][1] == {}


def test_a_smaller_context_window_shrinks_the_prompt_cap_for_both_runners(mods, tmp_path, monkeypatch):
    RD, RR, OR, B = mods["run_discovery"], mods["run_resolver"], mods["ollama_run"], mods["bundle"]
    assert B.prompt_cap(8192) == 6500 and B.prompt_cap(4096) == 4096 - B.ANSWER_RESERVE_TOKENS
    gen = _fake_generate(json.dumps({"requirements": []}))
    monkeypatch.setattr(OR, "generate", gen)
    ledger = OR.Ledger(tmp_path / "ctx.jsonl")
    # a chunk whose discovery prompt is about 5,400 estimated tokens: fine at 8192, untreatable at 4096
    chunk = [("DOC", {"chunk_id": 1, "text": "word " * 2000})]
    RD.run_chunks(chunk, arm="D0", model="m", digest="dg", run_label="small", ledger=ledger, ollama_url="http://x", num_ctx=4096, log=lambda *a: None)
    assert gen.calls == [] and next(iter(ledger.records.values()))["status"] == "untreatable"
    ledger2 = OR.Ledger(tmp_path / "ctx2.jsonl")
    RD.run_chunks(chunk, arm="D0", model="m", digest="dg", run_label="big", ledger=ledger2, ollama_url="http://x", num_ctx=8192, log=lambda *a: None)
    assert len(gen.calls) == 1
    # the resolver: with a 3,500-token window the full prompt (fixed text alone is about 3,400) cannot fit
    gen2 = _fake_generate("{}")
    monkeypatch.setattr(OR, "generate", gen2)
    ledger3 = OR.Ledger(tmp_path / "ctx3.jsonl")
    RR.run_candidates(_cand(), _docs(), tier="R2", model="m", digest="dg", run_label="r", ledger=ledger3, ollama_url="http://x", num_ctx=3500, log=lambda *a: None)
    assert gen2.calls == [] and next(iter(ledger3.records.values()))["status"] == "untreatable"


def test_repeated_quotes_are_separate_candidates_with_separate_keys(mods, tmp_path, monkeypatch):
    RR, OR = mods["run_resolver"], mods["ollama_run"]
    gen = _fake_generate("{}")
    monkeypatch.setattr(OR, "generate", gen)
    ledger = OR.Ledger(tmp_path / "dup.jsonl")
    chunks = {i: {"chunk_id": i, "raw_text": "The DOT&E shall:", "parent_header_text": "", "section_ref_path": [], "section_title_path": []} for i in (15, 19, 21)}
    docs = {"DOC": (chunks, {})}
    cands = [{"candidate_id": f"DOC:{i}", "document": "DOC", "chunk_id": i, "quote": "The DOT&E shall:"} for i in (15, 19, 21)]
    calls = RR.run_candidates(cands, docs, tier="R0", model="m", digest="dg", run_label="dup", ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    assert calls == 3 and len(ledger.records) == 3  # R0 builds the same bundle for all three, yet none is skipped


def test_only_complete_resolver_answers_count_toward_quality_totals(mods, tmp_path, monkeypatch):
    RR, OR, R = mods["run_resolver"], mods["ollama_run"], mods["resolver"]
    good = json.dumps(R.EXAMPLES[5]["answer"])
    for name, meta, expected_valid in (("ok", {}, 1), ("overrun", {"prompt_eval_count": 8000, "eval_count": 300}, 0), ("cut", {"done_reason": "length"}, 0)):
        monkeypatch.setattr(OR, "generate", _fake_generate(good, **meta))
        ledger = OR.Ledger(tmp_path / f"{name}.jsonl")
        RR.run_candidates(_cand(), _docs(), tier="R1", model="m", digest="dg", run_label=name, ledger=ledger, ollama_url="http://x", log=lambda *a: None)
        s = RR.summarize(ledger)
        assert s["valid_answers"] == expected_valid and s["shape_conformant"] == expected_valid and s["parsed"] == expected_valid, name
        assert sum(s["status"].values()) == 1  # the invalid call is still counted by status


def test_the_dry_run_report_uses_the_selected_context_cap(mods):
    RD = mods["run_discovery"]
    chunk = [("DOC", {"chunk_id": 1, "text": "word " * 2000})]
    assert RD.prompt_sizes(chunk, "D0", 8192)["over_prompt_cap"] == 0
    s = RD.prompt_sizes(chunk, "D0", 4096)
    assert s["cap"] == 3496 and s["over_prompt_cap"] == 1 and s["num_ctx"] == 4096
