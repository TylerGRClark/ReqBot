"""WP-45.7e: the fresh draw and its blind pack (offline; synthetic frames for the logic, the committed files for integrity; no corpus, no labels)."""

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_7"


def _load(name):
    for p in (_DIR, _ROOT, _ROOT / "eval/spike_results/wp_45_1", _ROOT / "eval/spike_results/wp_45_audit"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location(f"wp457e_{name}", _DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"wp457e_{name}"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def FP():
    return _load("fresh_pack")


@pytest.fixture(scope="module")
def FG():
    return _load("fresh_gold")


def _rows(FP, dup_quote=None):
    """Synthetic census rows with exactly the audit's stratum populations."""
    rows, i = [], 0
    for stratum, n in FP.AP.POPULATION.items():
        for k in range(n):
            rows.append({"stratum": stratum, "index": i, "document": f"D{i % 3}", "quote": f"quote {stratum} {k}", "method": "m", "stem": "",
                         "requirement_id": f"REQ-{i}", "chunk_id": 1})
            i += 1
    return rows


def _audit_first_n(FP, rows, excluded):
    taken = set()
    for stratum in FP.AP.POPULATION:
        frame = sorted((r for r in rows if r["stratum"] == stratum and r["index"] not in excluded), key=lambda r: r["index"])
        random.Random(f"{FP.AP.SEED}/{stratum}").shuffle(frame)
        taken |= {r["index"] for r in frame[: FP.AP.SAMPLE[stratum]]}
    return taken


def test_the_draw_takes_the_records_after_the_audits_own_slice_of_each_shuffle(FP):
    rows = _rows(FP)
    chosen, skipped = FP.draw(rows, set(), set())
    by = {}
    for r in chosen:
        by[r["stratum"]] = by.get(r["stratum"], 0) + 1
    assert by == {s: n for s, n in FP.EXTRA.items() if n} and len(chosen) == sum(FP.EXTRA.values()) == 114
    assert not {r["index"] for r in chosen} & _audit_first_n(FP, rows, set())  # none was in the audit
    assert [r["id"] for r in chosen] == [f"R{n}" for n in range(201, 201 + len(chosen))] and sum(skipped.values()) == 0
    again, _ = FP.draw(_rows(FP), set(), set())
    assert [r["index"] for r in again] == [r["index"] for r in chosen]  # deterministic
    # the extension is the NEXT slice of the same shuffle: the audit's n plus ours are distinct and contiguous
    frame = sorted((r for r in rows if r["stratum"] == "same-chunk"), key=lambda r: r["index"])
    random.Random(f"{FP.AP.SEED}/same-chunk").shuffle(frame)
    expected = {r["index"] for r in frame[FP.AP.SAMPLE["same-chunk"]: FP.AP.SAMPLE["same-chunk"] + FP.EXTRA["same-chunk"]]}
    assert {r["index"] for r in chosen if r["stratum"] == "same-chunk"} == expected


def test_records_that_duplicate_a_spent_quote_are_skipped_and_the_next_one_takes_their_place(FP):
    rows = _rows(FP)
    base, _ = FP.draw(rows, set(), set())
    victim = next(r for r in base if r["stratum"] == "cross-chunk")
    spent = {(victim["document"], FP.B.normalize(victim["quote"]).lower())}
    chosen, skipped = FP.draw(_rows(FP), set(), spent)
    assert victim["index"] not in {r["index"] for r in chosen} and skipped["cross-chunk"] == 1
    assert len([r for r in chosen if r["stratum"] == "cross-chunk"]) == FP.EXTRA["cross-chunk"]  # replaced from further down the shuffle
    assert not {(r["document"], FP.B.normalize(r["quote"]).lower()) for r in chosen} & spent


def test_the_draw_stops_when_a_stratum_cannot_supply_or_the_frame_changed(FP):
    rows = _rows(FP)
    every_quote = {(r["document"], FP.B.normalize(r["quote"]).lower()) for r in rows if r["stratum"] == "cross-chunk"}
    with pytest.raises(SystemExit) as e:
        FP.draw(rows, set(), every_quote)
    assert "cross-chunk" in str(e.value)
    with pytest.raises(SystemExit) as e:
        FP.draw(rows[:-1], set(), set())
    assert "populations changed" in str(e.value)


def test_the_committed_pack_is_the_unlabeled_draw_it_says_it_is(FP, FG):
    manifest = json.loads((_DIR / "outputs/fresh_pack_manifest.json").read_text())
    pack = _DIR / "fresh_pack"
    for name, digest in manifest["file_sha256"].items():
        path = _DIR / "outputs" / name if name == "fresh_draw_map.json" else pack / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
    key = json.loads((_DIR / "outputs/fresh_draw_map.json").read_text())["items"]
    cards = FG.parse_pack_a((pack / "pack_a.md").read_text(encoding="utf-8"))
    assert set(cards) == set(key) and len(key) == manifest["drawn"] == 114 and min(key) == "R201" and max(key) == "R314"
    with_stem = {k for k, v in key.items() if v["stem"]}
    b_ids = set(FG.re.findall(r"^## (R\d{3})\s*$", (pack / "pack_b.md").read_text(encoding="utf-8"), flags=FG.re.M))
    assert b_ids == with_stem and len(with_stem) == manifest["pass_b_cards"]
    assert manifest["by_stratum"] == {s: n for s, n in FP.EXTRA.items() if n}
    # the labelers' instructions and checker are the audit's own, byte for byte
    audit = _ROOT / "eval/spike_results/wp_45_1/audit_pack"
    for name in ("RUBRIC.md", "check_labels.py"):
        assert (pack / name).read_bytes() == (audit / name).read_bytes(), name


def test_no_fresh_candidate_is_a_spent_or_audit_record(FG):
    key = json.loads((_DIR / "outputs/fresh_draw_map.json").read_text())["items"]
    cards = FG.parse_pack_a((_DIR / "fresh_pack/pack_a.md").read_text(encoding="utf-8"))
    spent = json.loads((_DIR / "outputs/resolver_gold.json").read_text())["gold"]
    spent_quotes = {(g["document"], FG.norm(g["quote"]).lower()) for g in spent}
    spent_ids = {(g["document"], g["requirement_id"]) for g in spent}
    audit_key = json.loads((_ROOT / "eval/spike_results/wp_45_1/audit_results/answer_key.json").read_text())["items"]
    audit_ids = {(v["document"], v["requirement_id"]) for v in audit_key.values()}
    for rid, item in key.items():
        assert (item["document"], FG.norm(cards[rid]["quote"]).lower()) not in spent_quotes, rid
        assert (item["document"], item["requirement_id"]) not in spent_ids | audit_ids, rid


def test_the_pack_parser_reads_multi_line_quotes_and_the_card_text(FG):
    text = "# t\n\n## R201\nDocument: D | chunk 1\n\nQuote (the requirement text to judge):\n> first line\n> second line\n\nChunk 1:\n~~~~text\nbody\n~~~~\n\n## R202\nQuote (the requirement text to judge):\n> only\n\nx\n"
    cards = FG.parse_pack_a(text)
    assert cards["R201"]["quote"] == "first line\nsecond line" and "body" in cards["R201"]["card"] and cards["R202"]["quote"] == "only"


# ---- the gold builder, on synthetic inputs (the real labels are sealed until stage C2) ------------------------------------------------------------


def _mini(tmp_path, lead_in="Officers will:", extra_b=False, drop_b=False, spent_quote="nothing like it", lead_in_card="Officers will:"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    pack = tmp_path / "pack"
    pack.mkdir()
    cards = [("R201", "Complete sentence one.", "Chunk text one."), ("R202", "(1) Report it.", f"{lead_in_card} (1) Report it."),
             ("R203", "Defines a term.", "Definition text."), ("R204", "(2) Archive it.", "Unrelated chunk.")]
    (pack / "pack_a.md").write_text("# t\n\n" + "\n".join(f"## {i}\nDocument: D | chunk 1\n\nQuote (the requirement text to judge):\n> {q}\n\nChunk 1:\n~~~~text\n{c}\n~~~~\n" for i, q, c in cards))
    (pack / "check_labels.py").write_bytes((_DIR / "fresh_pack" / "check_labels.py").read_bytes())  # the audit's checker, as in the real pack folder
    (pack / "pack_b.md").write_text("# t\n\n## R201\nQuote:\n> Complete sentence one.\n\nStem the pipeline attached:\n> A stem.\n")
    key = {"items": {i: {"document": "D", "requirement_id": f"REQ-{i}", "chunk_id": 1, "stratum": "same-chunk", "stem": "A stem." if i == "R201" else ""}
                     for i, _, _ in cards}}
    (tmp_path / "key.json").write_text(json.dumps(key))
    labels = tmp_path / "labels"
    labels.mkdir()
    a = [{"id": "R201", "standalone": "complete", "lead_in_location": None, "lead_in_text": None},
         {"id": "R202", "standalone": "needs_lead_in", "lead_in_location": "same_chunk", "lead_in_text": lead_in},
         {"id": "R203", "standalone": "not_a_requirement", "lead_in_location": None, "lead_in_text": None},
         {"id": "R204", "standalone": "needs_lead_in", "lead_in_location": "not_shown", "lead_in_text": None}]
    b = [] if drop_b else [{"id": "R201", "stem_verdict": "not_needed"}]
    if extra_b:
        b.append({"id": "R202", "stem_verdict": "right"})
    (labels / "labels_claude_a.jsonl").write_text("\n".join(json.dumps(x) for x in a) + "\n")
    (labels / "labels_claude_b.jsonl").write_text("\n".join(json.dumps(x) for x in b) + "\n")
    (tmp_path / "spent.json").write_text(json.dumps({"gold": [{"document": "D", "quote": spent_quote}]}))
    return dict(pack=pack, labels=labels, key_path=tmp_path / "key.json", spent_path=tmp_path / "spent.json")


def test_the_gold_builder_validates_labels_against_the_cards_and_the_sufficiency_rule(FG, tmp_path, monkeypatch):
    data = FG.build(**_mini(tmp_path))
    c = data["counts"]
    assert (c["candidates"], c["real"], c["non_requirements"], c["attachment_scored"], c["needs_lead_in_not_shown"]) == (4, 3, 1, 2, 1)
    assert data["sufficiency"]["met"] is False  # the real thresholds (80 real, 8 non-requirements, 60 scored) are not met by four cards
    monkeypatch.setattr(FG, "MIN_REAL", 3)
    monkeypatch.setattr(FG, "MIN_NON_REQUIREMENTS", 1)
    monkeypatch.setattr(FG, "MIN_ATTACHMENT_SCORED", 2)
    ok = FG.build(**_mini(tmp_path / "again"))
    assert ok["sufficiency"]["met"] and [g["candidate_id"] for g in ok["gold"]] == ["fresh:R201", "fresh:R202", "fresh:R203", "fresh:R204"]
    assert ok["gold"][0]["stem_verdict"] == "not_needed" and ok["gold"][1]["stem_verdict"] is None and all(g["half"] == "evaluation" for g in ok["gold"])
    assert ok["gold"][1]["quote"] == "(1) Report it." and set(ok["inputs_sha256"]) >= {"pack_a.md", "labels_claude_a.jsonl"}
    # the pipe separator tolerates any spacing, and every passage must be in the card
    assert FG.build(**_mini(tmp_path / "pipe", lead_in="Officers will:|(1) Report it.", lead_in_card="Officers will:"))["counts"]["candidates"] == 4


def test_the_gold_builder_refuses_what_would_corrupt_the_gold(FG, tmp_path):
    with pytest.raises(SystemExit) as e:
        FG.build(**_mini(tmp_path / "a", lead_in="Not in the card at all."))
    assert "not in the card" in str(e.value)
    with pytest.raises(SystemExit) as e:  # a production stem needs its pass B verdict
        FG.build(**_mini(tmp_path / "b", drop_b=True))
    assert "pass B" in str(e.value)
    with pytest.raises(SystemExit) as e:  # and a verdict without a stem is wrong
        FG.build(**_mini(tmp_path / "c", extra_b=True))
    assert "pass B" in str(e.value)
    with pytest.raises(SystemExit) as e:
        FG.build(**_mini(tmp_path / "d", spent_quote="Complete sentence one."))
    assert "spent gold" in str(e.value)
    parts = _mini(tmp_path / "e")
    (parts["labels"] / "labels_claude_a.jsonl").write_text(json.dumps({"id": "R201", "standalone": "complete"}) + "\n")
    with pytest.raises(SystemExit) as e:
        FG.build(**parts)
    assert "do not follow the rubric" in str(e.value) and "no label for R202" in str(e.value)  # the rubric checker sees a missing card first
    (parts["labels"] / "labels_claude_a.jsonl").unlink()
    with pytest.raises(SystemExit) as e:
        FG.build(**parts)
    assert "sealed outside the repository" in str(e.value)


def test_the_sealed_hashes_in_the_plan_are_enforced_before_anything_is_frozen(FG, tmp_path):
    """Review finding: an edited or replaced label file must stop the protocol, not be recorded under its new digest."""
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "labels_claude_a.jsonl").write_text("a\n")
    (labels / "labels_claude_b.jsonl").write_text("b\n")
    sha = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
    plan = tmp_path / "plan.md"
    plan.write_text(f"`labels_claude_a.jsonl` `{sha('a' + chr(10))}`; `labels_claude_b.jsonl` `{sha('b' + chr(10))}`; `fresh_gold.json` `{sha('gold')}`.")
    FG.verify_sealed(labels, "gold", plan)  # exactly the sealed files
    for name, content, gold in (("labels_claude_a.jsonl", "edited\n", "gold"), ("labels_claude_b.jsonl", "edited\n", "gold"), (None, None, "other gold")):
        if name:
            (labels / name).write_text(content)
        with pytest.raises(SystemExit) as e:
            FG.verify_sealed(labels, gold, plan)
        assert "one-shot protocol stops" in str(e.value) and (name or "fresh_gold.json") in str(e.value)
        (labels / "labels_claude_a.jsonl").write_text("a\n")
        (labels / "labels_claude_b.jsonl").write_text("b\n")
    plan.write_text("no hashes here")
    with pytest.raises(SystemExit) as e:
        FG.verify_sealed(labels, "gold", plan)
    assert "does not fix a hash" in str(e.value)
    real = FG.expected_hashes()  # the real plan fixes three 64-hex hashes
    assert set(real) == {"labels_claude_a.jsonl", "labels_claude_b.jsonl", "fresh_gold.json"} and all(len(v) == 64 for v in real.values())


def test_labels_that_break_the_rubric_stop_the_builder(FG, tmp_path):
    """Review finding: valid JSON is not enough; the audit's own checker runs before any gold is built."""
    def with_a(tmp, change):
        parts = _mini(tmp)
        path = parts["labels"] / "labels_claude_a.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        change(rows)
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        return parts

    cases = {
        "a complete label with a lead-in text": lambda rows: rows[0].update(lead_in_text="Officers will:"),
        "a needs_lead_in label with no location": lambda rows: rows[1].update(lead_in_location=None),
        "a not_shown label with a text": lambda rows: rows[3].update(lead_in_text="Officers will:"),
        "a same_chunk label with no text": lambda rows: rows[1].update(lead_in_text=None),
        "an unknown standalone value": lambda rows: rows[2].update(standalone="maybe"),
    }
    for label, change in cases.items():
        with pytest.raises(SystemExit) as e:
            FG.build(**with_a(tmp_path / label.replace(" ", "_"), change))
        assert "do not follow the rubric" in str(e.value) or "bad standalone" in str(e.value), label
    parts = _mini(tmp_path / "verdict")
    (parts["labels"] / "labels_claude_b.jsonl").write_text(json.dumps({"id": "R201", "stem_verdict": "maybe"}) + "\n")
    with pytest.raises(SystemExit) as e:
        FG.build(**parts)
    assert "do not follow the rubric" in str(e.value)
    assert FG.rubric_problems(*(lambda m: (m["pack"], m["labels"]))(_mini(tmp_path / "clean"))) == []


# ---- stage C2: the committed labels and gold are the sealed ones (real files) ----------------------------------------------------------------


def test_the_committed_labels_and_gold_are_exactly_the_sealed_ones(FG):
    """The plan fixed three sha256 before the code was frozen; the committed files must be those files, byte for byte, and follow the rubric."""
    want = FG.expected_hashes()
    labels = FG.LABELS
    assert FG._sha(labels / "labels_claude_a.jsonl") == want["labels_claude_a.jsonl"]
    assert FG._sha(labels / "labels_claude_b.jsonl") == want["labels_claude_b.jsonl"]
    assert FG._sha(FG.FROZEN) == want["fresh_gold.json"]
    FG.verify_sealed(labels, FG.FROZEN.read_text(encoding="utf-8"))
    assert FG.rubric_problems(FG.PACK, labels) == []


def test_the_committed_gold_equals_the_recomputed_one_and_meets_the_plans_minimums(FG):
    frozen = json.loads(FG.FROZEN.read_text(encoding="utf-8"))
    assert FG.FROZEN.read_text(encoding="utf-8") == json.dumps(FG.build(), indent=1, ensure_ascii=False) + "\n"  # byte for byte
    c = frozen["counts"]
    assert (c["candidates"], c["real"], c["non_requirements"], c["attachment_scored"]) == (114, 105, 9, 104)
    assert frozen["sufficiency"]["met"] is True and c["with_production_stem"] == 58 and c["needs_lead_in_not_shown"] == 1
    gold = frozen["gold"]
    assert [g["candidate_id"] for g in gold] == [f"fresh:R{n}" for n in range(201, 315)]
    assert {g["half"] for g in gold} == {"evaluation"} and {g["set"] for g in gold} == {"audit"}
    # every record of a stem has its verdict and no record without a stem has one
    assert all(bool(g["production_stem"]) == bool(g["stem_verdict"]) for g in gold)


def test_the_fresh_gold_works_with_the_scorers_and_the_v6_guards(FG, tree_at_commit):
    S = _load("score_resolver")
    gold = json.loads(FG.FROZEN.read_text(encoding="utf-8"))["gold"]
    assert sum(1 for g in gold if S.attachment_scored(g)) == 104 and sum(1 for g in gold if S.is_real(g)) == 105
    base = {}
    for g in gold:
        if S.attachment_scored(g):
            base[S.baseline_attachment(g)] = base.get(S.baseline_attachment(g), 0) + 1
    assert base == {"right": 41, "misleading": 36, "incomplete": 27}  # production on the fresh set, from pass B: the verdict's anchors
    S.check_sufficiency("v6", gold)
    manifest = json.loads((S.OUTPUTS / S.FROZEN_CODE["v6"]).read_text())
    # the manifest pins and every sealed file match the tree of the stage D protocol commit (224e5a8, #241), the tree the one-shot ran from
    S.check_frozen_code("v6", root=tree_at_commit("224e5a8", {**manifest["files"], **manifest["sealed_until_c2"]}))


def test_the_gold_differs_from_the_first_serialization_only_in_the_disclosed_amendments(FG):
    """The plan's stage C2 amendments, pinned: the gold was re-serialized once (a secret-scanner trap on one key name), then five pass A lead-in texts were
    completed with their party passage. The first serialization is kept outside the repository; its per-record digests are in
    `outputs/fresh_gold_first_serialization_digests.json`. Every record must equal it, except these five, whose only difference is the lead-in text."""
    digest = lambda o: hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()  # noqa: E731
    first = json.loads((_DIR / "outputs/fresh_gold_first_serialization_digests.json").read_text())
    gold = json.loads(FG.FROZEN.read_text(encoding="utf-8"))
    amended = {
        "fresh:R212": "Blocks all externally visible PPS ... When required:",
        "fresh:R218": "In coordination with the USD(A&S), ensures:",
        "fresh:R265": "Establish TSN processes to assess vulnerabilities and manage risk to the assurance in the applicable system by:",
        "fresh:R281": "Appoints a DoD military officer ... as the PPSM CCB chairperson to:",
        "fresh:R285": "In coordination with the USD(A&S), ensures:",
    }
    verdict_before = {"fresh:R265": "right"}  # the second amendment: R265's pass B verdict was right, now fragment_chain
    records = gold["gold"]
    assert set(first) == {g["candidate_id"] for g in records} and len(first) == 114
    for g in records:
        cid = g["candidate_id"]
        if cid in amended:
            assert g["lead_in_text"].startswith(amended[cid] + " | ") and digest(g) != first[cid], cid  # the party passage was added
            restored = {**g, "lead_in_text": amended[cid], **({"stem_verdict": verdict_before[cid]} if cid in verdict_before else {})}
            assert digest(restored) == first[cid], cid  # and nothing else changed (R265's pass B verdict aside, restored here)
        else:
            assert digest(g) == first[cid], cid  # every other record is exactly as first serialized
    counts = json.loads(json.dumps(gold["counts"]))
    counts["stem_verdicts"]["right"] += 1
    counts["stem_verdicts"]["fragment_chain"] -= 1  # R265 moved from right to fragment_chain; everything else in the counts is as first serialized
    assert digest(counts) == "696746fd879ae8527190cd35a2b1b57ade588c94df8b624f76843791bc67a537"
    assert digest(gold["sufficiency"]) == "ee0538dba14ab608bfcf299109496aa9f1dd9ce1388079c5ee996c13d8890a93"
    assert "outputs/fresh_draw_map.json" in gold["inputs_sha256"] and "outputs/fresh_key.json" not in gold["inputs_sha256"]
