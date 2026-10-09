"""The text a reader sees as a requirement: explained text first, then description, then the root quote."""
from core.display import requirement_text


def test_explained_text_comes_first_then_description_then_the_root_quote():
    assert requirement_text({"explained_text": "AFMC will: Identify funding.", "description": "d", "source_quote": "Identify funding."}) == "AFMC will: Identify funding."
    assert requirement_text({"explained_text": "", "description": "A description.", "source_quote": "q"}) == "A description."
    assert requirement_text({"source_quote": "  Only a root quote.  "}) == "Only a root quote."
    assert requirement_text({}) == "" and requirement_text(None) == ""


def test_tag_and_type_filters_are_off_and_say_so():
    from core import constants
    assert constants.TAG_TYPE_FILTERS_ENABLED is False and "ignored" in constants.TAG_TYPE_FILTERS_OFF_WARNING


def test_ask_service_does_not_report_ignored_tag_and_type_filters_as_active(monkeypatch):
    from core import ask as core_ask
    from services import ask_service

    monkeypatch.setattr(core_ask, "retrieve", lambda *a, **k: {"results": [], "total": 0, "retrieval_ms": 1, "synthesis_text": "", "warnings": ["Tag and type filters are off"]})
    out = ask_service.ask("q", qdrant_url="x", ollama_url="y", domain_tags=["access-control"], requirement_types=["policy"], document_ids=["doc"])
    assert out["filters"] == {"document_id": ["doc"], "domain_tag": None, "requirement_type": None}
    assert out["warnings"] == ["Tag and type filters are off"]
