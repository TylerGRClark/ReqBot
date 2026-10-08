import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "eval/spike_results/wp_45_11/analyze_t3.py"
    spec = importlib.util.spec_from_file_location("analyze_t3", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["analyze_t3"] = mod
    spec.loader.exec_module(mod)
    return mod


T3 = _load()
QUOTE = "The Director shall ensure all personnel complete annual training as required."


def test_extracted_requires_forty_characters_and_containment_either_way():
    rec = {"source_quote": "  The Director shall ensure   all personnel complete annual training as required. "}
    assert T3.extracted_record([rec], QUOTE) is rec
    assert T3.extracted_record([{"source_quote": QUOTE[:60]}], QUOTE) is not None  # survivor contained in the gold quote
    assert T3.extracted_record([{"source_quote": "short"}], QUOTE) is None
    assert T3.extracted_record([rec], "tiny") is None


def test_find_chunk_uses_whole_quote_then_sixty_character_prefix():
    chunks = [{"raw_text": "Something else entirely."}, {"raw_text": QUOTE + " Extra."}]
    assert T3.find_chunk(chunks, QUOTE) is chunks[1]
    assert T3.find_chunk(chunks, QUOTE[:60] + " but a different tail") is chunks[1]
    assert T3.find_chunk(chunks, "No such sentence anywhere in these chunks at all.") is None


def test_colocated_needs_every_lead_in_piece():
    chunk = {"text": "The Director shall: (a) do X. Components shall comply."}
    assert T3.colocated(chunk, "The Director shall: ... Components shall comply")
    assert not T3.colocated(chunk, "The Director shall: ... Services shall comply")
