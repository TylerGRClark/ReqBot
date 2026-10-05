"""WP-45.7: the labeling packs and the standalone label checker (offline)."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "eval/spike_results/wp_45_7"
_DEV = _ROOT / "eval/spike_results/wp_45_1e"
_PACKS = _DIR / "label_pack"


def _load(name, path, extra_path=None):
    if extra_path:
        sys.path.insert(0, str(extra_path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if extra_path:
            sys.path.remove(str(extra_path))


@pytest.fixture(scope="module")
def pack():
    return _load("wp457_pack", _DIR / "pack.py", _DEV)


@pytest.fixture(scope="module")
def chk():
    return _load("wp457_check_labels", _PACKS / "check_labels.py")


PACK = (
    "# t\n\n## DOC, page 1\n"
    "[AAA-p001-001] The Director shall review the plan.\n"
    "[AAA-p001-002] Background text.\n"
    "    context line, not labeled\n"
    "[AAA-p001-003] Administrators should rotate keys.\n"
)


def _held(rows):
    return [json.dumps(r) for r in rows]


def test_pack_ids_are_the_bracketed_lines_only(chk):
    assert chk.pack_ids(PACK) == ["AAA-p001-001", "AAA-p001-002", "AAA-p001-003"]


def test_a_valid_heldout_file_passes(chk):
    rows = [
        {"id": "AAA-p001-001", "label": "obligation", "kind": "obligation", "segment_ok": True, "note": ""},
        {"id": "AAA-p001-002", "label": "not_obligation", "kind": "", "segment_ok": True, "note": ""},
        {"id": "AAA-p001-003", "label": "obligation", "kind": "recommendation", "segment_ok": False, "note": "cut"},
    ]
    ids, problems = chk.check(PACK, _held(rows), "heldout")
    assert problems == [] and len(ids) == 3


def test_heldout_kind_rules(chk):
    base = {"segment_ok": True, "note": ""}
    rows = [
        {"id": "AAA-p001-001", "label": "obligation", "kind": "", **base},  # obligation needs a kind
        {"id": "AAA-p001-002", "label": "not_obligation", "kind": "permission", **base},  # kind only for obligation
        {"id": "AAA-p001-003", "label": "obligation", "kind": "mandatory", **base},  # not a valid kind
    ]
    _, problems = chk.check(PACK, _held(rows), "heldout")
    assert len(problems) == 3
    assert any("needs a kind" in p for p in problems)
    assert any("must be empty" in p for p in problems)


def test_missing_extra_duplicate_and_bad_json_are_reported(chk):
    ok = {"label": "scope", "kind": "", "segment_ok": True, "note": ""}
    rows = _held([{"id": "AAA-p001-001", **ok}, {"id": "AAA-p001-001", **ok}, {"id": "ZZZ-p009-001", **ok}])
    rows.append("{not json")
    _, problems = chk.check(PACK, rows, "heldout")
    text = "\n".join(problems)
    assert "duplicate id" in text and "not valid JSON" in text
    assert "no label" in text and "not in the pack" in text


def test_devkind_mode_accepts_none_and_the_four_kinds_only(chk):
    pack = "[AAA-p001-001] x\n[AAA-p001-002] y\n"
    good = _held([{"id": "AAA-p001-001", "kind": "none", "note": ""}, {"id": "AAA-p001-002", "kind": "permission", "note": ""}])
    assert chk.check(pack, good, "devkind")[1] == []
    bad = _held([{"id": "AAA-p001-001", "kind": "maybe", "note": ""}, {"id": "AAA-p001-002", "kind": "prohibition", "note": ""}])
    assert len(chk.check(pack, bad, "devkind")[1]) == 1


def test_permission_wording_is_lowercase_so_a_date_is_not_caught(pack):
    assert not pack.PERMISSION.search("AIR FORCE MANUAL 17-2101 22 MAY 2018")
    assert pack.PERMISSION.search("The Authorizing Official may grant a waiver.")
    assert pack.PERMISSION.search("Hypervisors can permit interactions between guest OSs.")
    assert not pack.PERMISSION.search("The hypervisor provides a sandbox.")


def test_devkind_candidates_are_obligations_plus_permission_wording_in_page_order(pack):
    final = {
        "A-p001-001": {"label": "not_obligation"},
        "A-p001-002": {"label": "obligation"},
        "A-p001-003": {"label": "not_obligation"},
        "A-p001-004": {"label": "scope"},
    }
    index = {
        "A-p001-001": {"text": "Plain background."},
        "A-p001-002": {"text": "Do it."},
        "A-p001-003": {"text": "Users may request access."},
        "A-p001-004": {"text": "Applies to all staff."},
    }
    assert pack.devkind_candidates(final, index) == ["A-p001-002", "A-p001-003"]


def test_devkind_pack_marks_candidates_and_indents_context_without_earlier_labels(pack):
    frozen = {
        "documents": {
            "D": {
                "pieces": {
                    "1": [{"id": "A-p001-001", "text": "ctx one"}, {"id": "A-p001-002", "text": "target"}],
                    "2": [{"id": "A-p002-001", "text": "nothing marked on this page"}],
                }
            }
        }
    }
    text = pack.devkind_pack(frozen, ["A-p001-002"])
    assert "[A-p001-002] target" in text
    assert "    ctx one" in text and "[A-p001-001]" not in text
    assert "page 2" not in text  # pages with nothing marked are left out
    assert "obligation" not in text.split("\n", 3)[-1]  # no earlier label appears in the pack body


def test_committed_packs_match_the_frozen_pieces_and_the_manifest():
    held = json.loads((_DIR / "outputs" / "heldout_frozen.json").read_text(encoding="utf-8"))
    manifest = json.loads((_DIR / "outputs" / "pack_manifest.json").read_text(encoding="utf-8"))
    chk = _load("wp457_check_labels2", _PACKS / "check_labels.py")
    held_ids = [p["id"] for e in held["documents"].values() for pg in e["pieces"].values() for p in pg]
    assert sorted(chk.pack_ids((_PACKS / "pack_heldout.md").read_text(encoding="utf-8"))) == sorted(held_ids)
    assert manifest["heldout_pieces"] == len(held_ids) == held["pieces_total"]
    assert manifest["heldout_pieces_sha256"] == held["pieces_sha256"]
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((_PACKS / name).read_bytes()).hexdigest() == digest, name
    dev_ids = chk.pack_ids((_PACKS / "pack_devkind.md").read_text(encoding="utf-8"))
    assert len(dev_ids) == manifest["devkind_pieces"] == 105
    assert len(set(dev_ids)) == len(dev_ids)
