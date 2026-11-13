"""Choosing a document style automatically (core/style_detection.py, doc_styles/detection.json) and how a run records it.

The title blocks below are shaped like the first page of the real documents. The tricky cases are the ones that fooled the first attempt: a body that mentions another family's
publication, a cover that has only a title, a series number written 171r3, a file name that disagrees with the page."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import doc_styles, style_detection
from core.style_detection import Detection, detect_style, resolve, title_block_from_items
from pipeline.run_pipeline import _saved_style_record, _style_record_for_run

DODI = "DoDI 8410.03, August 29, 2012\nNetwork Management (NM)\nSUBJECT: Network Management (NM)\nReferences: See Enclosure 1\n1. PURPOSE. This Instruction, issued under the authorities of DoD Directive 5144.02"
DODI_5200 = "NUMBER 5200.01 April 21, 2016 Incorporating Change 2, Effective October 1, 2020 USD(I&S) SUBJECT: DoD Information Security Program and Protection of Sensitive Compartmented Information"
DODI_5200_48 = "Department of Defense INSTRUCTION\nNUMBER 5200.48 March 6, 2020\nSUBJECT: Controlled Unclassified Information (CUI)"
CJCSI = "CJCSI 6510.02G\n20 March 2025\nCRYPTOGRAPHIC MODERNIZATION PLANNING\nReferences: See Enclosure E"
AFI = "BY ORDER OF THE SECRETARY OF THE AIR FORCE\nAIR FORCE INSTRUCTION 17-203\n6 MARCH 2014\nCyberspace\nCYBER INCIDENT HANDLING"
DAFMAN = "DEPARTMENT OF THE AIR FORCE MANUAL 17-1203\n13 SEPTEMBER 2022\nCommunications and Information\nINFORMATION TECHNOLOGY (IT) ASSET MANAGEMENT"
AFMAN_MENTIONS = "BY ORDER OF THE SECRETARY OF THE AIR FORCE\nAIR FORCE MANUAL 17-2101\n22 MAY 2018\nThe Chairman of the Joint Chiefs of Staff and DoD Instruction 8500.01 apply."
CNSSI = "CNSSI No. 1253\n27 March 2014\nSecurity Categorization and Control Selection for National Security Systems"
NIST_53 = "Security and Privacy Controls for Information Systems and Organizations\nJoint Task Force\nThis publication is available free of charge from: https://doi.org/10.6028/NIST.SP.800-53r5"
NIST_53_NUMBERED = "NIST Special Publication 800-53\nRevision 5\nSecurity and Privacy Controls for Information Systems and Organizations"
NIST_171R3 = "NIST Special Publication 800-171r3\nProtecting Controlled Unclassified Information in Nonfederal Systems and Organizations"
NIST_53A = "NIST Special Publication 800-53A\nRevision 5\nAssessing Security and Privacy Controls in Information Systems and Organizations"
NIST_125 = "Karen Scarfone Murugiah Souppaya Paul Hoffman\nNIST Special Publication 800-125\nGuide to Security for Full Virtualization Technologies"
NIST_30 = "NIST Special Publication 800-30 Revision 1\nGuide for Conducting Risk Assessments\nThis guide supports 800-53 and 800-37."


def style_of(block, filename=""):
    return detect_style(block, filename).style


# --- the data --------------------------------------------------------------------------------------------------------------

def test_every_shipped_style_except_general_has_a_family():
    mapped = {f["style"] for f in style_detection.families()}
    assert set(doc_styles.list_styles()) - {"general"} <= mapped
    assert mapped <= set(doc_styles.list_styles())


def test_family_names_are_unique_and_the_file_validates():
    names = [f["family"] for f in style_detection.families()]
    assert len(names) == len(set(names)) and len(names) >= 5


@pytest.mark.parametrize("bad", [
    {}, {"families": []}, {"families": ["x"]},
    {"families": [{"family": "a", "style": "no-such-style", "title_patterns": ["x"]}]},
    {"families": [{"family": "a", "style": "general", "title_patterns": ["(unclosed"]}]},
    {"families": [{"family": "a", "style": "general"}]},
    {"families": [{"family": "a", "style": "general", "title_patterns": "x"}]},
    {"families": [{"family": "a", "style": "general", "title_patterns": ["x"]}, {"family": "a", "style": "general", "title_patterns": ["y"]}]},
    {"families": [{"family": "", "style": "general", "title_patterns": ["x"]}]},
])
def test_a_malformed_detection_file_is_refused(bad):
    with pytest.raises(ValueError):
        style_detection._validate(bad)


# --- recognizing the document types ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("block,expected", [
    (DODI, "outline-dod"), (DODI_5200, "outline-dod"), (DODI_5200_48, "outline-dod"), (CJCSI, "outline-dod"),
    (AFI, "general"), (DAFMAN, "general"), (CNSSI, "control-tables"),
    (NIST_53, "nist-controls"), (NIST_53_NUMBERED, "nist-controls"), (NIST_171R3, "nist-controls"), (NIST_53A, "nist-controls"),
    (NIST_125, "general"), (NIST_30, "general"),
])
def test_title_block_alone_picks_the_style(block, expected):
    assert style_of(block, "document.pdf") == expected


def test_a_body_that_mentions_another_family_does_not_fool_it():
    d = detect_style(AFMAN_MENTIONS, "document.pdf")
    assert d.style == "general" and d.family == "air-force"       # not the CJCS or DoD it merely mentions


def test_an_air_force_cover_that_cites_a_dod_instruction_stays_general():
    block = "AIR FORCE INSTRUCTION 17-203\nCompliance with DoD Instruction 8500.01 and DoDI 8510.01 is mandatory."
    assert style_of(block) == "general"


def test_a_dod_instruction_that_mentions_air_force_and_cjcs_is_still_a_dod_instruction():
    block = "DoD Instruction 8410.03\nNetwork Management\nThe Chairman of the Joint Chiefs of Staff and AFI 17-101 apply."
    assert style_of(block) == "outline-dod"


def test_a_nist_publication_that_mentions_800_53_in_its_body_stays_general():
    assert style_of(NIST_30) == "general"


def test_a_series_number_written_171r3_is_recognized():
    assert style_of("NIST SP 800-171r3 Requirements") == "nist-controls"
    assert style_of("NIST SP 800-171A Assessing Security Requirements") == "general"   # the assessment companion is not covered yet: the safe default
    assert style_of("NIST SP 800-1710") == "general"


@pytest.mark.parametrize("block", ["", "   ", "Acme Corp Acceptable Use Policy v3. Effective 2026.", "ISO/IEC 27001:2022 Information security management systems", None])
def test_unknown_or_empty_text_is_general(block):
    d = detect_style(block, "policy.pdf")
    assert d.style == "general" and d.confidence == "none" and d.family is None


# --- the file name -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected", [("DODI 8410.03.pdf", "outline-dod"), ("dodi_5200.01.pdf", "outline-dod"), ("CJCSI 6510.02G.pdf", "outline-dod"),
                                                ("CNSSI_No1253.pdf", "control-tables"), ("NIST.SP.800-53r5.pdf", "nist-controls"),
                                                ("NIST.SP.800-171r3.pdf", "nist-controls"), ("NIST.SP.800-125.pdf", "general"),
                                                ("afi17-203.pdf", "general"), ("scan_0001.pdf", "general"), ("", "general")])
def test_file_name_alone_when_the_page_has_no_text(filename, expected):
    d = detect_style("", filename)
    assert d.style == expected
    assert d.confidence in ("medium", "none")


def test_a_file_name_that_agrees_with_the_page_gives_high_confidence():
    d = detect_style(DODI, "DODI 8410.03.pdf")
    assert (d.style, d.family, d.confidence) == ("outline-dod", "dodi", "high")


def test_a_file_name_that_contradicts_the_page_gives_general_and_says_why():
    d = detect_style("AIR FORCE INSTRUCTION 17-203", "DODI 8410.03.pdf")
    assert d.style == "general" and d.confidence == "low" and "dodi" in d.reason and "air-force" in d.reason


def test_a_renamed_file_is_found_by_its_page():
    assert detect_style(CJCSI, "scan_0001.pdf").style == "outline-dod"


def test_the_more_specific_style_wins_when_two_families_start_together():
    assert detect_style("NIST Special Publication 800-53", "").family == "nist-controls"


def test_the_result_explains_itself():
    d = detect_style(DODI, "document.pdf")
    assert d.reason and d.as_record() == {"family": "dodi", "confidence": "high", "reason": d.reason}


# --- the first page of a reader's items ---------------------------------------------------------------------------------------

def item(text, page):
    return SimpleNamespace(text=text, prov=[SimpleNamespace(page_no=page)])


def test_the_title_block_is_the_first_page_only_and_stops_at_page_two():
    items = [item("Department of Defense INSTRUCTION", 1), item("NUMBER 5200.48", 1), item("Page two text", 2), item("late page-one-looking text", 1)]
    assert title_block_from_items(items) == "Department of Defense INSTRUCTION\nNUMBER 5200.48"


def test_items_without_text_or_pages_are_skipped_not_fatal():
    items = [SimpleNamespace(prov=[]), SimpleNamespace(text="", prov=[SimpleNamespace(page_no=1)]), SimpleNamespace(text="x", prov=None),
             SimpleNamespace(text=5, prov=[SimpleNamespace(page_no=1)]), item("CJCSI 6510.02G", 1)]
    assert title_block_from_items(items) == "CJCSI 6510.02G"


def test_the_title_block_is_bounded():
    many = [item(f"line {i} " + "x" * 100, 1) for i in range(100)]
    block = title_block_from_items(many)
    assert len(block.split("\n")) <= style_detection.TITLE_BLOCK_ITEMS and len(block) <= style_detection.TITLE_BLOCK_CHARS + 120


# --- the user's choice always wins -----------------------------------------------------------------------------------------------

def test_a_named_style_is_never_overridden_by_detection():
    style, detection = resolve("general", [item(DODI, 1)], "DODI 8410.03.pdf")
    assert style["name"] == "general" and detection is None
    style, detection = resolve("nist-controls", [item(AFI, 1)], "afi17-203.pdf")
    assert style["name"] == "nist-controls" and detection is None


def test_auto_reads_the_first_page_and_the_file_name():
    style, detection = resolve("auto", [item(CJCSI, 1)], "scan.pdf")
    assert style["name"] == "outline-dod" and isinstance(detection, Detection) and detection.family == "cjcsi"


def test_auto_on_an_unrecognized_document_is_general():
    style, detection = resolve("auto", [item("Acme policy", 1)], "policy.pdf")
    assert style["name"] == "general" and detection.confidence == "none"


def test_an_unknown_named_style_is_an_error_not_a_silent_fallback():
    with pytest.raises(FileNotFoundError):
        resolve("no-such-style", [], "x.pdf")


# --- what the run records ------------------------------------------------------------------------------------------------------

GENERAL = doc_styles.load_style("general")
OUTLINE = doc_styles.load_style("outline-dod")


def test_a_run_that_chunked_records_what_was_asked_chosen_and_why():
    det = detect_style(DODI, "DODI 8410.03.pdf")
    rec = _style_record_for_run(OUTLINE, "auto", det, saved=None, chunked_now=True)
    assert rec["name"] == "outline-dod" and rec["requested"] == "auto" and rec["family"] == "dodi" and rec["confidence"] == "high" and rec["reason"]


def test_a_named_style_records_that_it_was_named():
    rec = _style_record_for_run(OUTLINE, "outline-dod", None, saved=None, chunked_now=True)
    assert rec == {"name": "outline-dod", "version": "1", "requested": "outline-dod"}


def test_a_resumed_run_keeps_what_the_earlier_run_recorded():
    saved = {"name": "outline-dod", "version": "1", "requested": "auto", "family": "dodi", "confidence": "high", "reason": "r"}
    assert _style_record_for_run(GENERAL, "auto", None, saved, chunked_now=False) == saved
    assert _style_record_for_run(OUTLINE, "outline-dod", None, saved, chunked_now=False) == saved


def test_resuming_with_a_different_named_style_is_refused():
    saved = {"name": "outline-dod", "version": "1"}
    with pytest.raises(RuntimeError, match="start again from PDF reading"):
        _style_record_for_run(GENERAL, "general", None, saved, chunked_now=False)


def test_a_resumed_run_with_nothing_saved_says_no_style_could_be_chosen():
    rec = _style_record_for_run(GENERAL, "auto", None, saved=None, chunked_now=False)
    assert rec["name"] == "general" and rec["confidence"] == "none" and "not read" in rec["reason"]
    assert _style_record_for_run(OUTLINE, "outline-dod", None, saved=None, chunked_now=False) == {"name": "outline-dod", "version": "1", "requested": "outline-dod"}


def test_the_saved_style_is_read_from_beside_the_chunks_first_then_from_stats(tmp_path):
    from pipeline.run_pipeline import _persist_style_record
    stats = {"pipeline": {"doc_style": {"name": "general", "version": "1"}}}
    (tmp_path / "doc_stats.json").write_text(json.dumps(stats), encoding="utf-8")
    assert _saved_style_record(tmp_path, "doc") == {"name": "general", "version": "1"}          # an older finished run: stats only
    (tmp_path / "doc_ancestry.json").write_text(json.dumps({"sections": [], "item_ancestry": {}}), encoding="utf-8")
    assert _saved_style_record(tmp_path, "doc") == {"name": "general", "version": "1"}          # ancestry has no record yet: stats still answer
    assert _persist_style_record(tmp_path / "doc_ancestry.json", {"name": "outline-dod", "version": "1", "requested": "auto"})
    assert _saved_style_record(tmp_path, "doc")["name"] == "outline-dod"                         # the record beside the chunks outranks stale stats
    assert json.loads((tmp_path / "doc_ancestry.json").read_text(encoding="utf-8"))["sections"] == []   # and nothing else in the file changed
    assert _saved_style_record(tmp_path, "other") is None


def test_a_failure_after_chunking_leaves_the_style_for_the_resume(tmp_path):
    """Codex, PR 396: the record was only in memory until the stats were written at the end, so a resume lost it or read an older ingest's."""
    from pipeline.run_pipeline import _persist_style_record
    (tmp_path / "doc_stats.json").write_text(json.dumps({"pipeline": {"doc_style": {"name": "general", "version": "1"}}}), encoding="utf-8")   # an OLDER ingest of this folder
    (tmp_path / "doc_ancestry.json").write_text("{}", encoding="utf-8")
    det = detect_style(DODI, "DODI 8410.03.pdf")
    _persist_style_record(tmp_path / "doc_ancestry.json", _style_record_for_run(OUTLINE, "auto", det, saved=None, chunked_now=True))
    saved = _saved_style_record(tmp_path, "doc")                      # the run died during requirement finding; now resume with --skip-to C
    assert saved["name"] == "outline-dod" and saved["family"] == "dodi"
    assert _style_record_for_run(GENERAL, "auto", None, saved, chunked_now=False) == saved
    assert _style_record_for_run(OUTLINE, "outline-dod", None, saved, chunked_now=False) == saved   # the style actually used is accepted, not the old stats'


def test_saving_the_style_never_stops_a_run(tmp_path):
    from pipeline.run_pipeline import _persist_style_record
    assert _persist_style_record(tmp_path / "missing_ancestry.json", {"name": "general"}) is False
    (tmp_path / "bad_ancestry.json").write_text("{broken", encoding="utf-8")
    assert _persist_style_record(tmp_path / "bad_ancestry.json", {"name": "general"}) is False
    for bad in ("{broken", json.dumps({}), json.dumps({"pipeline": {"doc_style": None}}), json.dumps({"pipeline": {"doc_style": {"version": "1"}}})):
        (tmp_path / "bad_stats.json").write_text(bad, encoding="utf-8")
        assert _saved_style_record(tmp_path, "bad") is None


def test_the_pipeline_and_the_command_default_to_auto():
    import inspect

    import pipeline.run_pipeline as rp
    assert inspect.signature(rp.run).parameters["doc_style_name"].default == "auto"
    assert Path(doc_styles.__file__).exists()


def test_detection_never_stops_an_ingest_when_the_reader_document_cannot_be_read():
    """A reader document that cannot be iterated (or a stand-in object) leaves the file name to decide; it does not raise."""
    class Broken:
        def iterate_items(self):
            raise RuntimeError("no items")

    for doc in (object(), Broken()):
        try:
            items = [item for item, _level in doc.iterate_items()]
        except Exception:
            items = []
        style, detection = resolve("auto", items, "DODI 8410.03.pdf")
        assert style["name"] == "outline-dod" and detection.confidence == "medium"
