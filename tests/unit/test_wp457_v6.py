"""WP-45.7e stage B: the menu fixes, the declared v6 configuration, the sealed-file rule and the v6 runner path (offline; no LLM, no corpus, no labels)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_7"


def _load(name):
    for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location(f"wp457e2_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp457e2_{name}"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def SC():
    return _load("run_stage_c")


@pytest.fixture(scope="module")
def M1(SC):
    return SC.M1  # the very module objects the runner uses, so identity checks mean something


@pytest.fixture(scope="module")
def M2(SC):
    return SC.M2


def _chunk(cid, text, heading="", path=()):
    return {"chunk_id": cid, "raw_text": text, "parent_header_text": heading, "section_title_path": list(path)}


CHUNKS = {
    1: _chunk(1, "Intro words. The Officer will:", path=["PART 1"]),
    2: _chunk(2, "Text here. - 7.3.4.3. Establish and maintain a data report. ( T-2 ) - 2.22.5. Report changes in status.",
              heading="2.17. MAJCOM/DRUs.", path=["ROLES AND RESPONSIBILITIES", "2.17. MAJCOM/DRUs."]),
    3: _chunk(3, "The Records Officer will: (1) Review logs monthly. (2) Report findings to the Director.", heading="2.3. RECORDS OFFICER",
              path=["SECTION 2", "2.3. RECORDS OFFICER"]),
}


def test_an_entry_needs_at_least_two_letters(M2):
    assert M2.letters("- 7.3.4.3.") == 0 and M2.letters("( T-2 ) - 2.22.5.") == 1 and M2.letters("AF") == 2 and M2.MIN_LETTERS == 2
    menu = M2.build_menu("Establish and maintain a data report.", 2, CHUNKS, "R2")
    texts = [e["text"] for e in menu]
    assert not any(M2.letters(t) < 2 for t in texts), texts  # the list-number "preceding" entry is gone


def test_a_heading_is_offered_only_without_its_section_number(M1, M2):
    old = [e["text"] for e in M1.build_menu("Establish and maintain a data report.", 2, CHUNKS, "R1")]
    new = [e["text"] for e in M2.build_menu("Establish and maintain a data report.", 2, CHUNKS, "R1")]
    assert "2.17. MAJCOM/DRUs." in old and "MAJCOM/DRUs." in old  # the old menu offered both, and the model picked the numbered one
    assert "MAJCOM/DRUs." in new and "2.17. MAJCOM/DRUs." not in new and "ROLES AND RESPONSIBILITIES" in new
    assert "- 7.3.4.3." in old and "- 7.3.4.3." not in new  # the junk entry, offered before and dropped now
    third = [e["text"] for e in M2.build_menu("(2) Report findings to the Director.", 3, CHUNKS, "R1")]
    assert "RECORDS OFFICER" in third and "SECTION 2" in third and not any(t[:1].isdigit() for t in third if t.endswith("OFFICER"))


def test_the_new_menu_only_ever_removes_entries_and_every_one_is_verbatim(M1, M2):
    """The change is subtractive: no text appears that the old menu did not offer, and each entry is a substring of its sources."""
    quotes = {1: "The Officer will:", 2: "Establish and maintain a data report.", 3: "(2) Report findings to the Director."}
    for cid, quote in quotes.items():
        for tier in ("R0", "R1", "R2"):
            old = {e["text"] for e in M1.build_menu(quote, cid, CHUNKS, tier)}
            new = M2.build_menu(quote, cid, CHUNKS, tier)
            assert {e["text"] for e in new} <= old, (cid, tier)
            assert [e["id"] for e in new] == [f"M{i}" for i in range(1, len(new) + 1)] and len(new) <= M2.MAX_MENU
            sources = [M1.B.normalize(quote)] + [M1.B.normalize(c["raw_text"]) for c in CHUNKS.values()]
            sources += [M1.B.normalize(h) for c in CHUNKS.values() for h in c["section_title_path"] + [c["parent_header_text"]]]
            sources += [M2.M1._SECTION_NUMBER.sub("", s, count=1) for s in sources]
            assert all(any(e["text"] in s for s in sources) for e in new), (cid, tier)
    assert M2.build_menu("x", 1, CHUNKS, "R0") == [] or all(e["kind"] == "subject" for e in M2.build_menu("The Officer shall act.", 1, CHUNKS, "R0"))
    with pytest.raises(ValueError):
        M2.build_menu("x", 1, CHUNKS, "R9")


def test_the_new_menu_stays_subtractive_when_the_old_menu_hit_its_cap(M1, M2):
    """Review finding: removing an early entry must not let a later candidate in that the old menu never offered."""
    path = [f"{n}.1 Heading number {n}" for n in range(1, 9)]  # 8 numbered headings: 16 old entries (numbered and plain) before anything else
    chunks = {
        1: _chunk(1, "Earlier text. The Officer will:", path=["PART 1"]),
        2: _chunk(2, "Text here. - 7.3.4.3. Establish a report.", heading="9.1 Leaf heading", path=path),
    }
    old = M1.build_menu("Establish a report.", 2, chunks, "R2")
    new = M2.build_menu("Establish a report.", 2, chunks, "R2")
    assert len(old) == M1.MAX_MENU  # the cap bound
    def numbered(e):
        return e["kind"] == "heading" and M1._SECTION_NUMBER.sub("", e["text"], count=1) != e["text"]

    assert [e["text"] for e in new] == [e["text"] for e in old if M2.letters(e["text"]) >= 2 and not numbered(e)]
    assert len(new) < len(old)  # slots were freed ...
    assert {e["text"] for e in new} <= {e["text"] for e in old}  # ... and nothing the old menu never offered came in
    assert not any(e["source"].endswith("(previous)") for e in new)  # the previous-chunk lead-in was beyond the old cap, so it stays out
    assert [e["id"] for e in new] == [f"M{i}" for i in range(1, len(new) + 1)]


def test_no_numbered_heading_survives_even_when_its_plain_form_was_cut_by_the_cap(M1, M2):
    """Review finding: with one subject and seven numbered headings the old menu's last entry is a numbered heading whose plain form fell beyond the cap."""
    path = [f"{n}.1 Heading number {n}" for n in range(1, 8)]
    chunks = {2: _chunk(2, "Text here. The Officer shall act on it.", heading="", path=path)}
    old = M1.build_menu("The Officer shall act on it.", 2, chunks, "R1")
    assert len(old) == M1.MAX_MENU and old[-1]["kind"] == "heading" and old[-1]["text"][0].isdigit()  # the cap cut the plain form of that heading
    new = M2.build_menu("The Officer shall act on it.", 2, chunks, "R1")
    assert not any(e["kind"] == "heading" and e["text"][0].isdigit() for e in new)
    assert {e["text"] for e in new} <= {e["text"] for e in old}
    assert [e["text"] for e in new if e["kind"] == "heading"] == [f"Heading number {n}" for n in range(7, 0, -1)][:6]  # six plain headings; the seventh went


def test_the_frozen_menu_module_is_reused_not_copied(M1, M2):
    assert M2.first_modal is M1.first_modal and M2.subject_of is M1.subject_of and M2.menu_modal is M1.menu_modal
    assert M2.MAX_MENU == M1.MAX_MENU and M2.MAX_SPAN_CHARS == M1.MAX_SPAN_CHARS


# ---- the declared configuration, the sealed files, the v6 rule ------------------------------------------------------------------------------


def test_the_declared_v6_configuration_is_the_one_the_v5_runs_used(SC):
    S = SC.SR
    declared = S.frozen_choice("v6")
    assert declared["name"] == "r2_14b" and declared["tier"] == "R2" and declared["model"] == S.MODELS[14]
    v5 = S.frozen_choice("v5")
    assert {k: declared[k] for k in ("tier", "model", "digest", "temperatures", "num_ctxs", "num_predicts")} == \
        {k: v5[k] for k in ("tier", "model", "digest", "temperatures", "num_ctxs", "num_predicts")}
    assert json.loads((S.OUTPUTS / "declared_v6.json").read_text())["prompt_hash"] == S.K.prompt_hash() == "6200fa25a374eb35"
    assert S.GOLDS["v6"].name == "fresh_gold.json" and S.GOLDS["v5"].name == "resolver_gold.json"


def test_a_declaration_must_name_the_registrys_own_prompt_and_be_complete(SC, tmp_path):
    S = SC.SR
    good = json.loads((S.OUTPUTS / "declared_v6.json").read_text())
    (tmp_path / "declared_v6.json").write_text(json.dumps({**good, "prompt_hash": "0" * 16}))
    with pytest.raises(SystemExit) as e:
        S.frozen_choice("v6", tmp_path)
    assert "prompt" in str(e.value)
    (tmp_path / "declared_v6.json").write_text(json.dumps({k: v for k, v in good.items() if k != "digest"}))
    with pytest.raises(SystemExit) as e:
        S.frozen_choice("v6", tmp_path)
    assert "digest" in str(e.value)
    with pytest.raises(SystemExit) as e:
        S.frozen_choice("v6", tmp_path / "nowhere")
    assert "no committed declaration" in str(e.value)


def test_sealed_files_must_match_when_present_and_are_required_for_a_verdict(SC, tmp_path):
    S = SC.SR
    root = tmp_path / "code"
    root.mkdir()
    (root / "a.py").write_text("a")
    out = tmp_path / "outputs"
    out.mkdir()
    sha = lambda b: S.hashlib.sha256(b).hexdigest()  # noqa: E731
    (out / S.FROZEN_CODE["v6"]).write_text(json.dumps({"files": {"a.py": sha(b"a")}, "sealed_until_c2": {"gold.json": sha(b"gold")}}))
    S.check_frozen_code("v6", out, root, include_sealed=False)  # before the labels are committed
    with pytest.raises(SystemExit) as e:
        S.check_frozen_code("v6", out, root)  # a verdict needs them
    assert "gold.json" in str(e.value)
    (root / "gold.json").write_text("gold")
    S.check_frozen_code("v6", out, root)  # present and equal
    (root / "gold.json").write_text("edited")
    with pytest.raises(SystemExit) as e:
        S.check_frozen_code("v6", out, root)
    assert "gold.json" in str(e.value)


def test_a_v6_verdict_scores_the_declared_configuration_only(SC, tmp_path):
    S = SC.SR
    out = tmp_path / "outputs"
    out.mkdir()
    (out / "declared_v6.json").write_text((S.OUTPUTS / "declared_v6.json").read_text())
    root = tmp_path / "code"
    root.mkdir()
    (root / "a.py").write_text("a")
    menu_hashes = {p: S.hashlib.sha256(p.encode()).hexdigest() for p in S.MENU_FILES["v6"]}  # the menu files the manifest pins
    for rel in S.MENU_FILES["v6"]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(rel.encode())
    (out / S.FROZEN_CODE["v6"]).write_text(json.dumps({"files": {"a.py": S.hashlib.sha256(b"a").hexdigest(), **menu_hashes}}))
    stamp = S.menu_identity("v6", menu_hashes)
    declared = S.frozen_choice("v6", out)
    base = {"right": 40, "misleading": 30, "incomplete": 30}  # production on 100 scored records
    half = {"all": {"candidates": 110, "valid": 110, "real": {"requirement": 100}, "non_requirement": {"not_a_requirement": 9, "scope_or_context": 1},
                    "attachment": {}, "status": {"complete": 110}, "invented_answers": 0, "modality_error_answers": 0},
            "audit": {"attachment": {"right": 60, "misleading": 35, "incomplete": 5}, "baseline_attachment": base}}
    meta = {"tiers": [declared["tier"]], "models": [declared["model"]], "digests": [declared["digest"]], "temperatures": declared["temperatures"],
            "num_ctxs": declared["num_ctxs"], "num_predicts": declared["num_predicts"], "menu_generators": [stamp]}
    result = {"prompt_hashes": [S.K.prompt_hash()], "run_meta": meta, "evaluation": half}
    report = S.verdict_report(result, "v6", "r2_14b", out, root)
    assert report["all_gates_pass"] and report["registry"] == "v6" and report["frozen_code"] == "frozen_wp457e_code.json"
    assert report["gates"]["attachment_gain_over_production"]["passed"]  # 60 of 100 = 40% + 20 points exactly
    half["audit"]["attachment"] = {"right": 59, "misleading": 35, "incomplete": 6}
    assert not S.verdict_report(result, "v6", "r2_14b", out, root)["gates"]["attachment_gain_over_production"]["passed"]
    old_menu = {**meta, "menu_generators": [S.menu_identity("v6", {p: "0" * 64 for p in S.MENU_FILES["v6"]})]}  # a ledger made with other menu files
    for bad in ({**result, "prompt_hashes": [S.SEL.prompt_hash()]}, {**result, "run_meta": {**meta, "digests": ["other"]}},
                {**result, "run_meta": old_menu}, {**result, "run_meta": {**meta, "menu_generators": ["None"]}},  # unstamped: the v5 path writes no stamp
                {**result, "run_meta": {k: v for k, v in meta.items() if k != "menu_generators"}}):
        with pytest.raises(SystemExit):
            S.verdict_report(bad, "v6", "r2_14b", out, root)
    with pytest.raises(SystemExit):
        S.verdict_report(result, "v6", "r1_8b", out, root)


def test_a_v6_verdict_always_reads_its_own_gold(SC, tmp_path, monkeypatch):
    S = SC.SR
    other = tmp_path / "other_gold.json"
    other.write_text(json.dumps({"gold": []}))
    monkeypatch.setattr(S, "GOLDS", {**S.GOLDS, "v6": tmp_path / "missing_fresh_gold.json"})
    monkeypatch.setattr(sys, "argv", ["score_resolver.py", "--verdict", "r2_14b=/nowhere", "--registry", "v6", "--gold", str(other)])
    with pytest.raises(SystemExit) as e:
        S.main()
    assert "missing_fresh_gold.json" in str(e.value)  # --gold did not redirect the verdict
    monkeypatch.setattr(sys, "argv", ["score_resolver.py", "--choose", "--registry", "v6", "--runs", "a=b"])
    with pytest.raises(SystemExit) as e:
        S.main()
    assert "declared, not chosen" in str(e.value)  # v6 has no choice rule


# ---- the v6 runner path -------------------------------------------------------------------------------------------------------------------


def test_the_runner_maps_each_registry_to_its_menu_and_gold(SC, M1, M2):
    assert SC.MENUS == {"v5": M1, "v6": M2} and set(SC.DESIGNS) == {"v5", "v6"}
    assert SC.SR.GOLDS["v6"] == SC.SR.OUTPUTS / "fresh_gold.json"


def test_the_v6_run_uses_the_new_menu_and_restores_the_frozen_one(SC, M1, M2, tmp_path, monkeypatch):
    S = SC.SR
    declared = {**json.loads((S.OUTPUTS / "declared_v6.json").read_text())}
    out = tmp_path / "outputs"
    out.mkdir()
    (out / "declared_v6.json").write_text(json.dumps(declared))
    (out / S.FROZEN_CODE["v6"]).write_text(json.dumps({"files": {}}))
    frozen, label, out_dir = SC.preflight("v6", "http://x", digest_fn=lambda u, m: declared["digest"], outputs=out, root=tmp_path, scratch=tmp_path / "s")
    assert label == "v6_eval_r2_14b" and frozen["name"] == "r2_14b"
    seen = []

    def gen(prompt, model, url, **kw):
        seen.append(prompt)
        return json.dumps({"kind": "requirement", "actor": "none", "parent": "none"}), {
            "done_reason": "stop", "prompt_eval_count": 900, "eval_count": 20, "total_duration": 1, "load_duration": 0, "wall_seconds": 0.3}

    monkeypatch.setattr(SC.RS.OR, "generate", gen)
    cands = [{"candidate_id": "fresh:R999", "document": "DOC", "chunk_id": 2, "quote": "Establish and maintain a data report."}]
    summary = SC.run_frozen("v6", frozen, cands, {"DOC": (CHUNKS, {})}, label, out_dir, "http://x", log=lambda *a: None)
    rec = json.loads((out_dir / "resolver.jsonl").read_text().splitlines()[0])
    texts = [e["text"] for e in rec["menu"]]
    assert "MAJCOM/DRUs." in texts and "2.17. MAJCOM/DRUs." not in texts and "- 7.3.4.3." not in texts  # the v2 menu was the one used
    assert summary["menu"].endswith("menu_v2") and summary["half"] == "evaluation" and rec["tier"] == "R2"
    assert SC.RS.M is M1  # the frozen menu module is back after the run, so the v5 path is unchanged
    # the same candidate through the v5 path gets the old, numbered and junk entries
    old = SC.RS.M.build_menu(cands[0]["quote"], 2, CHUNKS, "R2")
    assert "2.17. MAJCOM/DRUs." in [e["text"] for e in old]


def test_the_v6_run_stamps_every_record_with_the_menu_files_and_a_resume_must_match(SC, tmp_path, monkeypatch):
    """Review finding: v5 and v6 share every other validated value, so the ledger must say which menu generator wrote it."""
    S = SC.SR
    repo = tmp_path / "repo"
    for rel, text in zip(S.MENU_FILES["v6"], ("menu v2 source", "menu v1 source")):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    monkeypatch.setattr(S, "REPO", repo)
    stamp = SC.menu_identity("v6")
    assert stamp.startswith("menu_v2.py:") and "|menu.py:" in stamp and SC.menu_identity("v5") is None
    (repo / S.MENU_FILES["v6"][0]).write_text("menu v2 source, edited")
    assert SC.menu_identity("v6") != stamp  # the identity follows the file contents
    (repo / S.MENU_FILES["v6"][0]).write_text("menu v2 source")
    ledger = SC._StampedLedger(tmp_path / "l.jsonl", stamp)
    ledger.append({"entry_id": "k1", "candidate_id": "x", "status": "complete"})
    assert json.loads((tmp_path / "l.jsonl").read_text())["menu_generator"] == stamp and ledger.records["k1"]["menu_generator"] == stamp
    # a resume accepts only records stamped with the same menu files
    frozen = {"tier": "R2", "model": S.MODELS[14], "digest": "d", "temperatures": ["0.1"], "num_ctxs": ["8192"], "num_predicts": ["200"]}
    rec = {"candidate_id": "audit:A", "run_label": "v6_eval_r2_14b", "kind": "selection", "tier": "R2", "model": S.MODELS[14], "digest": "d",
           "prompt_hash": S.K.prompt_hash(), "temperature": 0.1, "num_ctx": 8192, "num_predict": 200, "menu_generator": stamp}
    path = tmp_path / "partial.jsonl"
    path.write_text(json.dumps(rec) + "\n")
    SC.check_partial_ledger(path, frozen, "v6_eval_r2_14b", stamp)
    for bad in ({**rec, "menu_generator": "menu_v2.py:0|menu.py:0"}, {k: v for k, v in rec.items() if k != "menu_generator"}):
        path.write_text(json.dumps(bad) + "\n")
        with pytest.raises(SystemExit) as e:
            SC.check_partial_ledger(path, frozen, "v6_eval_r2_14b", stamp)
        assert "menu_generator" in str(e.value)


def test_candidates_come_from_the_registrys_gold_evaluation_half(SC, tmp_path, monkeypatch):
    monkeypatch.setattr(SC.SR, "SUFFICIENCY", {})  # this test is about which half is read, not about the minimums
    gold = tmp_path / "g.json"
    gold.write_text(json.dumps({"gold": [
        {"candidate_id": "fresh:R201", "document": "D", "chunk_id": 1, "quote": "q1", "half": "evaluation", "set": "audit", "extra": 1},
        {"candidate_id": "fresh:R202", "document": "D", "chunk_id": 2, "quote": "q2", "half": "selection", "set": "audit"}]}))
    assert SC.candidates_for("v6", gold) == [{"candidate_id": "fresh:R201", "document": "D", "chunk_id": 1, "quote": "q1"}]


def _gold(real_complete, non_requirements, with_text=True):
    g = [{"candidate_id": f"fresh:R{n}", "set": "audit", "half": "evaluation", "document": "D", "chunk_id": 1, "quote": f"q{n}", "standalone": "complete",
          "lead_in_location": None, "lead_in_text": None} for n in range(real_complete)]
    g += [{"candidate_id": f"fresh:N{n}", "set": "audit", "half": "evaluation", "document": "D", "chunk_id": 1, "quote": f"n{n}",
           "standalone": "not_a_requirement", "lead_in_location": None, "lead_in_text": None} for n in range(non_requirements)]
    return g


def test_a_gold_below_the_pre_run_minimums_stops_the_run_and_the_verdict(SC, tmp_path, monkeypatch):
    """Review finding: an empty category would make a gate vanish, and a short set would be consumed for nothing."""
    S = SC.SR
    assert S.SUFFICIENCY["v6"] == {"real": 80, "non_requirements": 8, "attachment_scored": 60}
    S.check_sufficiency("v6", _gold(80, 8))  # exactly the minimums (all complete, so all attachment-scored)
    S.check_sufficiency("v5", [])  # a registry without minimums is not checked
    for real, non in ((79, 8), (80, 7), (80, 0)):
        with pytest.raises(SystemExit) as e:
            S.check_sufficiency("v6", _gold(real, non))
        assert "pre-run minimums" in str(e.value)
    with pytest.raises(SystemExit) as e:  # real requirements that are not attachment-scored do not count toward the 60
        S.check_sufficiency("v6", [{**g, "standalone": "needs_lead_in"} for g in _gold(90, 8)[:90]] + _gold(0, 8))
    assert "attachment_scored" in str(e.value)
    short = tmp_path / "gold.json"
    short.write_text(json.dumps({"gold": _gold(10, 2)}))
    with pytest.raises(SystemExit):
        SC.candidates_for("v6", short)  # the runner stops before any candidate is returned
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"gold": _gold(80, 8)}))
    assert len(SC.candidates_for("v6", ok)) == 88
    monkeypatch.setattr(S, "GOLDS", {**S.GOLDS, "v6": short})  # the verdict stops too, before it scores anything
    monkeypatch.setattr(sys, "argv", ["score_resolver.py", "--verdict", f"r2_14b={tmp_path}", "--registry", "v6"])
    with pytest.raises(SystemExit) as e:
        S.main()
    assert "pre-run minimums" in str(e.value)


def test_the_committed_v6_manifest_matches_the_repository_and_names_the_sealed_files(SC):
    S = SC.SR
    manifest = json.loads((S.OUTPUTS / S.FROZEN_CODE["v6"]).read_text())
    w = "eval/spike_results/wp_45_7/"
    assert {w + f for f in ("menu.py", "menu_v2.py", "kind_selection.py", "check_resolution.py", "run_selection.py", "run_stage_c.py", "score_resolver.py",
                            "outputs/declared_v6.json", "outputs/fresh_draw_map.json")} <= set(manifest["files"])
    S.check_frozen_code("v6", include_sealed=False)
    plan = (_ROOT / "docs/PHASE45_WP457E_PLAN.md").read_text()
    sealed = manifest["sealed_until_c2"]
    assert sealed[w + "outputs/fresh_gold.json"] in plan  # the hashes in the manifest are the ones fixed in the plan
    assert sealed[w + "fresh_labels/labels_claude_a.jsonl"] in plan and sealed[w + "fresh_labels/labels_claude_b.jsonl"] in plan
    for rel, digest in sealed.items():  # once the labels are committed they must match; before, they may be absent
        path = _ROOT / rel
        if path.exists():
            assert S.hashlib.sha256(path.read_bytes()).hexdigest() == digest, rel


def test_the_v6_manifest_itself_is_fixed_here(SC):
    """A tampered manifest could pin anything, so its own hash is fixed in this test (regenerate it only on purpose, with freeze_v6.py --force)."""
    S = SC.SR
    own = S.hashlib.sha256((S.OUTPUTS / S.FROZEN_CODE["v6"]).read_bytes()).hexdigest()
    assert own == "80d0f73639293cd456b88de5ff9bc071cc5a55a11ca669473fe35710e1a4d84b", own
