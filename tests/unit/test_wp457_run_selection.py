"""WP-45.7b: the selection runner (offline; Ollama is faked, the documents are synthetic, the frozen gold is read as committed)."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"
_ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    for p in (str(_DIR), str(_ROOT), str(_ROOT / "eval/spike_results/wp_45_audit")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(f"wp457b_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp457b_{name}"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def RS():
    return _load("run_selection")


@pytest.fixture(scope="module")
def SC():
    return _load("score_resolver")


CHUNKS = {
    1: {"chunk_id": 1, "raw_text": "Preface text.", "parent_header_text": "", "section_title_path": ["PART 1"]},
    2: {"chunk_id": 2, "raw_text": "The Records Officer will: (1) Review logs monthly. (2) Report findings to the Director.",
        "parent_header_text": "2.3. RECORDS OFFICER", "section_title_path": ["PART 1", "2.3. RECORDS OFFICER"]},
}
DOCS = {"DOC": (CHUNKS, {})}
CANDS = [
    {"candidate_id": "audit:A1", "document": "DOC", "chunk_id": 2, "quote": "(2) Report findings to the Director."},
    {"candidate_id": "audit:A2", "document": "DOC", "chunk_id": 2, "quote": "(1) Review logs monthly."},
]


def _fake(reply, **meta):
    base = {"done_reason": "stop", "prompt_eval_count": 900, "eval_count": 30, "total_duration": 1, "load_duration": 0, "wall_seconds": 0.5}
    base.update(meta)
    calls = []

    def gen(prompt, model, url, **kw):
        calls.append({"prompt": prompt, "schema": kw.get("schema"), "num_predict": kw.get("num_predict")})
        return (reply(prompt) if callable(reply) else reply), dict(base)

    gen.calls = calls
    return gen


def _run(RS, tmp_path, monkeypatch, gen, name="t", cands=CANDS):
    monkeypatch.setattr(RS.OR, "generate", gen)
    ledger = RS.OR.Ledger(tmp_path / f"{name}.jsonl")
    n = RS.run_candidates(cands, DOCS, tier="R2", model="m", digest="dg", run_label=name, ledger=ledger, ollama_url="http://x", log=lambda *a: None)
    return n, ledger


def _pick(prompt_menu_texts):
    """A reply that picks the menu entry (by its text) as parent and the subject-of-lead-in as actor, found from the live prompt."""

    def reply(prompt):
        menu = prompt[prompt.rindex("Menu (choose by id):"):]
        ids = {line.split("] ", 1)[1]: line.split(" ", 1)[0] for line in menu.splitlines()[1:] if "] " in line}
        return json.dumps({"status": "obligation", "actor": ids.get("The Records Officer", "none"), "parent": ids.get("The Records Officer will:", "none")})

    return reply


def test_the_runner_writes_assembled_records_resumes_and_sends_the_enum_schema(RS, SC, tmp_path, monkeypatch):
    gen = _fake(_pick(None))
    n, ledger = _run(RS, tmp_path, monkeypatch, gen)
    assert n == 2 and len(ledger.records) == 2
    rec = next(r for r in ledger.records.values() if r["candidate_id"] == "audit:A1")
    assert rec["kind"] == "selection" and rec["status"] == "complete" and rec["tier"] == "R2" and rec["prompt_hash"] == RS.S.prompt_hash()
    assert rec["selection"] == {"status": "obligation", "actor": next(e["id"] for e in rec["menu"] if e["text"] == "The Records Officer"),
                                "parent": next(e["id"] for e in rec["menu"] if e["text"] == "The Records Officer will:")}
    assert rec["answer"]["actor"]["value"] == "The Records Officer" and rec["answer"]["parent"]["value"] == "The Records Officer will:"
    assert rec["answer"]["modality"]["verbatim"] == "will"  # read by code from the chosen parent
    assert not [i for i in rec["issues"] if i["severity"] == "error"]
    assert gen.calls[0]["schema"] == RS.S.json_schema(rec["menu"]) and gen.calls[0]["num_predict"] == 200
    assert "Menu (choose by id):" in gen.calls[0]["prompt"] and rec["menu"][0]["id"] == "M1"
    again = RS.OR.Ledger(tmp_path / "t.jsonl")
    assert RS.run_candidates(CANDS, DOCS, tier="R2", model="m", digest="dg", run_label="t", ledger=again, ollama_url="http://x", log=lambda *a: None) == 0
    # the ledger is readable by the unchanged scorer
    records = {r["candidate_id"]: r for r in ledger.records.values()}
    gold = {"candidate_id": "audit:A1", "set": "audit", "half": "selection", "standalone": "needs_lead_in", "lead_in_text": "The Records Officer will:",
            "production_stem": "", "stem_verdict": None, "real_requirement": True}
    scored = SC.score_half(records, [gold])
    assert scored["valid"] == 1 and scored["attachment"]["right"] == 1 and scored["invented_answers"] == 0 and scored["modality_error_answers"] == 0


def test_the_run_key_changes_with_the_menu_and_the_run_label(RS, tmp_path, monkeypatch):
    _, a = _run(RS, tmp_path, monkeypatch, _fake(_pick(None)), name="a")
    _, b = _run(RS, tmp_path, monkeypatch, _fake(_pick(None)), name="b")
    assert set(a.records).isdisjoint(set(b.records))


def test_bad_answers_and_failed_requests_are_recorded_as_failures_not_dropped(RS, tmp_path, monkeypatch):
    for name, reply in (("junk", "not json"), ("badid", json.dumps({"status": "obligation", "actor": "M99", "parent": "none"})),
                        ("badstatus", json.dumps({"status": "mandatory", "actor": "none", "parent": "none"})),
                        ("missing", json.dumps({"status": "obligation"}))):
        _, ledger = _run(RS, tmp_path, monkeypatch, _fake(reply), name=name, cands=CANDS[:1])
        rec = next(iter(ledger.records.values()))
        assert rec["status"] == "failed" and rec["answer"] is None and rec["raw_response"] == reply, name

    def boom(*a, **k):
        raise RuntimeError("connection refused")

    _, ledger = _run(RS, tmp_path, monkeypatch, boom, name="boom", cands=CANDS[:1])
    rec = next(iter(ledger.records.values()))
    assert rec["status"] == "failed" and "connection refused" in rec["raw_response"] and rec["answer"] is None


def test_an_overrun_is_kept_with_its_status_and_an_oversized_prompt_is_never_sent(RS, tmp_path, monkeypatch):
    _, ledger = _run(RS, tmp_path, monkeypatch, _fake(_pick(None), prompt_eval_count=8100, eval_count=300), name="ov", cands=CANDS[:1])
    assert next(iter(ledger.records.values()))["status"] == "window_overrun"
    gen = _fake(_pick(None))
    monkeypatch.setattr(RS.B, "prompt_cap", lambda num_ctx=8192: 10)
    n, ledger = _run(RS, tmp_path, monkeypatch, gen, name="big", cands=CANDS[:1])
    rec = next(iter(ledger.records.values()))
    assert n == 0 and gen.calls == [] and rec["status"] == "untreatable" and rec["answer"] is None


def test_summary_reports_menu_size_and_the_fixed_prompt(RS, tmp_path, monkeypatch):
    _, ledger = _run(RS, tmp_path, monkeypatch, _fake(_pick(None)))
    s = RS.summarize(ledger)
    assert s["candidates"] == 2 and s["valid_answers"] == 2 and s["answers_with_a_selection"] == 2
    assert s["mean_menu_size"] > 1 and s["fixed_prompt_estimated_tokens"] == RS.S.fixed_tokens()


def test_gold_candidates_are_the_frozen_halves(RS):
    sel, ev = RS.gold_candidates("selection"), RS.gold_candidates("evaluation")
    assert (len(sel), len(ev)) == (104, 116)
    assert not {c["candidate_id"] for c in sel} & {c["candidate_id"] for c in ev}
    assert set(sel[0]) == {"candidate_id", "document", "chunk_id", "quote"}


def test_r0_is_not_a_tier_here_and_the_evaluation_half_needs_final():
    for args in (["--tier", "R0", "--model", "m", "--run-label", "x"], ["--tier", "R1", "--model", "m", "--run-label", "x", "--half", "evaluation"]):
        done = subprocess.run([sys.executable, str(_DIR / "run_selection.py"), "--ollama-url", "http://x", *args], capture_output=True, text=True)
        assert done.returncode != 0
    assert "--final" in done.stderr + done.stdout
