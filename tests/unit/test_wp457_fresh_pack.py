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
    assert "do not list the same cards" in str(e.value)
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
