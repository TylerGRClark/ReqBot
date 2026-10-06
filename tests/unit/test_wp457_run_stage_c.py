"""WP-45.7d Stage C: the one-shot runner checks everything before any model call (offline; Ollama is faked, nothing is read from the corpus)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parents[2] / "eval/spike_results/wp_45_7"
_ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    for p in (str(_DIR), str(_ROOT), str(_ROOT / "eval/spike_results/wp_45_audit")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(f"wp457c_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp457c_{name}"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def SC():
    return _load("run_stage_c")


def _frozen_world(tmp_path, SC, passes=True, name="r2_14b", digest="digest-frozen"):
    """A synthetic outputs directory (choice report, chosen run, code manifest) and a code root, as the real ones are laid out."""
    S = SC.SR
    out = tmp_path / "outputs"
    run = out / "selection_v5_runs" / f"v5_sel_{name}"
    run.mkdir(parents=True)
    (out / S.CHOICE_REPORTS["v5"]).write_text(json.dumps({"chosen": {"name": name, "passes_every_gate": passes}}))
    tier, size = S.parse_config(name)
    (run / "run_summary.json").write_text(json.dumps({"tier": tier, "model": S.MODELS[size], "digest": digest}))
    (run / "resolver.jsonl").write_text(json.dumps({"candidate_id": "x", "temperature": 0.1, "num_ctx": 8192, "num_predict": 200}) + "\n")
    root = tmp_path / "code"
    root.mkdir()
    (root / "menu.py").write_text("menu v1")
    (out / S.FROZEN_CODE["v5"]).write_text(json.dumps({"files": {"menu.py": S.hashlib.sha256(b"menu v1").hexdigest()}}))
    return out, root


def test_preflight_passes_only_when_everything_is_the_frozen_configuration(SC, tmp_path):
    out, root = _frozen_world(tmp_path, SC)
    asked = []

    def digest(url, model):
        asked.append((url, model))
        return "digest-frozen"

    frozen, label, out_dir = SC.preflight("v5", "http://x", digest_fn=digest, outputs=out, root=root, scratch=tmp_path / "scratch")
    assert frozen["name"] == "r2_14b" and frozen["tier"] == "R2" and label == "v5_eval_r2_14b" and out_dir == tmp_path / "scratch" / label
    assert asked == [("http://x", SC.SR.MODELS[14])]  # the model that is looked up is the frozen one, not a caller's choice


def test_preflight_refuses_each_way_the_one_shot_could_be_wasted(SC, tmp_path):
    out, root = _frozen_world(tmp_path, SC)
    ok = lambda url, model: "digest-frozen"  # noqa: E731
    with pytest.raises(SystemExit) as e:
        SC.preflight("v4", "http://x", digest_fn=ok, outputs=out, root=root, scratch=tmp_path / "s")
    assert "only for" in str(e.value)
    with pytest.raises(SystemExit) as e:  # the model file on the server is not the frozen one
        SC.preflight("v5", "http://x", digest_fn=lambda u, m: "digest-other", outputs=out, root=root, scratch=tmp_path / "s")
    assert "model file differs" in str(e.value)
    (root / "menu.py").write_text("menu v2")  # frozen code changed
    with pytest.raises(SystemExit) as e:
        SC.preflight("v5", "http://x", digest_fn=ok, outputs=out, root=root, scratch=tmp_path / "s")
    assert "menu.py" in str(e.value)
    (root / "menu.py").write_text("menu v1")
    SC.preflight("v5", "http://x", digest_fn=ok, outputs=out, root=root, scratch=tmp_path / "s")  # restored: passes again
    stopped, root2 = _frozen_world(tmp_path / "stopped", SC, passes=False)
    with pytest.raises(SystemExit) as e:  # a stopped Stage B has no Stage C
        SC.preflight("v5", "http://x", digest_fn=ok, outputs=stopped, root=root2, scratch=tmp_path / "s")
    assert "stopped at Stage B" in str(e.value)
    done = tmp_path / "s" / "v5_eval_r2_14b"
    done.mkdir(parents=True)
    (done / "run_summary.json").write_text("{}")  # the half has been run: no second try
    with pytest.raises(SystemExit) as e:
        SC.preflight("v5", "http://x", digest_fn=ok, outputs=out, root=root, scratch=tmp_path / "s")
    assert "one-shot" in str(e.value)


def test_an_unfinished_ledger_resumes_only_if_every_record_is_the_frozen_configuration(SC, tmp_path):
    """Review finding: the resume key ignores temperature and answer limit, so a ledger left by another configuration would be silently continued."""
    out, root = _frozen_world(tmp_path, SC)
    ok = lambda url, model: "digest-frozen"  # noqa: E731
    scratch = tmp_path / "s"
    ledger = scratch / "v5_eval_r2_14b" / "resolver.jsonl"
    ledger.parent.mkdir(parents=True)
    good = {"candidate_id": "audit:A1", "run_label": "v5_eval_r2_14b", "kind": "selection", "tier": "R2", "model": SC.SR.MODELS[14],
            "digest": "digest-frozen", "prompt_hash": SC.K.prompt_hash(), "temperature": 0.1, "num_ctx": 8192, "num_predict": 200}
    ledger.write_text(json.dumps(good) + "\n\n" + json.dumps({**good, "candidate_id": "audit:A2"}) + "\n")
    SC.preflight("v5", "http://x", digest_fn=ok, outputs=out, root=root, scratch=scratch)  # a crashed Stage C run resumes
    for field, value in (("temperature", 0.7), ("num_predict", 900), ("num_ctx", 4096), ("tier", "R1"), ("model", SC.SR.MODELS[8]),
                         ("digest", "other"), ("prompt_hash", SC.SR.SEL.prompt_hash()), ("run_label", "v5_sel_r2_14b"), ("kind", "resolver")):
        ledger.write_text(json.dumps(good) + "\n" + json.dumps({**good, "candidate_id": "audit:A9", field: value}) + "\n")
        with pytest.raises(SystemExit) as e:
            SC.preflight("v5", "http://x", digest_fn=ok, outputs=out, root=root, scratch=scratch)
        assert "audit:A9" in str(e.value) and field in str(e.value), field
    ledger.write_text(json.dumps(good) + "\nnot json\n")
    with pytest.raises(SystemExit) as e:
        SC.preflight("v5", "http://x", digest_fn=ok, outputs=out, root=root, scratch=scratch)
    assert "not JSON" in str(e.value)


def test_the_frozen_run_uses_the_frozen_parameters_and_cannot_be_rerun(SC, tmp_path, monkeypatch):
    out, root = _frozen_world(tmp_path, SC)
    frozen, label, out_dir = SC.preflight("v5", "http://x", digest_fn=lambda u, m: "digest-frozen", outputs=out, root=root, scratch=tmp_path / "s")
    seen = []

    def gen(prompt, model, url, **kw):
        seen.append({"model": model, "temperature": kw["temperature"], "num_ctx": kw["num_ctx"], "num_predict": kw["num_predict"],
                     "schema_keys": sorted(kw["schema"]["properties"])})
        return json.dumps({"kind": "requirement", "actor": "none", "parent": "none"}), {
            "done_reason": "stop", "prompt_eval_count": 900, "eval_count": 20, "total_duration": 1, "load_duration": 0, "wall_seconds": 0.3}

    monkeypatch.setattr(SC.RS.OR, "generate", gen)
    chunks = {2: {"chunk_id": 2, "raw_text": "The Records Officer will: (1) Review logs monthly.", "parent_header_text": "2.3. RECORDS OFFICER",
                  "section_title_path": ["PART 1", "2.3. RECORDS OFFICER"]}}
    cands = [{"candidate_id": "audit:A1", "document": "DOC", "chunk_id": 2, "quote": "(1) Review logs monthly."}]
    summary = SC.run_frozen("v5", frozen, cands, {"DOC": (chunks, {})}, label, out_dir, "http://x", log=lambda *a: None)
    assert seen == [{"model": SC.SR.MODELS[14], "temperature": 0.1, "num_ctx": 8192, "num_predict": 200, "schema_keys": ["actor", "kind", "parent"]}]
    assert summary["run_label"] == "v5_eval_r2_14b" and summary["half"] == "evaluation" and summary["design"] == "kind"
    assert summary["tier"] == "R2" and summary["digest"] == "digest-frozen" and summary["prompt_hash"] == SC.K.prompt_hash()
    rec = next(json.loads(x) for x in (out_dir / "resolver.jsonl").read_text().splitlines())
    assert rec["tier"] == "R2" and rec["model"] == SC.SR.MODELS[14] and rec["temperature"] == 0.1 and rec["prompt_hash"] == SC.K.prompt_hash()
    with pytest.raises(SystemExit):  # a finished run cannot be run again
        SC.preflight("v5", "http://x", digest_fn=lambda u, m: "digest-frozen", outputs=out, root=root, scratch=tmp_path / "s")


def test_main_runs_every_check_before_it_loads_any_evaluation_candidate(SC, tmp_path, monkeypatch, capsys):
    order = []
    frozen = {"name": "r2_14b", "tier": "R2", "model": SC.SR.MODELS[14], "digest": "digest-frozen", "temperatures": ["0.1"], "num_ctxs": ["8192"],
              "num_predicts": ["200"]}

    def fake_preflight(registry, url, **kw):
        order.append("preflight")
        return frozen, "v5_eval_r2_14b", tmp_path / "out"

    monkeypatch.setattr(SC, "preflight", fake_preflight)
    monkeypatch.setattr(SC.RS, "gold_candidates", lambda half: order.append(f"candidates:{half}") or [])
    monkeypatch.setattr(SC.RR, "load_documents", lambda docs: order.append("documents") or {})
    monkeypatch.setattr(SC, "run_frozen", lambda *a, **k: order.append("run") or {"ok": True})
    monkeypatch.setattr(sys, "argv", ["run_stage_c.py", "--ollama-url", "http://x", "--preflight-only"])
    SC.main()
    assert order == ["preflight"]  # --preflight-only reads no candidate at all
    order.clear()
    monkeypatch.setattr(sys, "argv", ["run_stage_c.py", "--ollama-url", "http://x"])
    SC.main()
    assert order == ["preflight", "candidates:evaluation", "documents", "run"]
    assert "--verdict r2_14b=" in capsys.readouterr().out
    order.clear()

    def refusing(*a, **k):
        order.append("preflight")
        raise SystemExit("refused")

    monkeypatch.setattr(SC, "preflight", refusing)
    with pytest.raises(SystemExit):
        SC.main()
    assert order == ["preflight"]  # a refusal means no candidate was loaded and nothing was run


def test_the_runner_has_no_option_to_change_the_frozen_configuration(SC, monkeypatch):
    for flag in ("--tier", "--model", "--design", "--temperature", "--num-ctx", "--num-predict", "--half", "--final"):
        monkeypatch.setattr(sys, "argv", ["run_stage_c.py", flag, "x"])
        with pytest.raises(SystemExit) as e:
            SC.main()
        assert e.value.code == 2  # argparse: unrecognized arguments
