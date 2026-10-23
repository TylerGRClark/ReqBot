"""Ask --context: the window is centred on the hit's quote even when the chunk text wraps the quote over lines (Codex P2 on #365)."""
import uuid
from types import SimpleNamespace

from core.ask import CONTEXT_UUID_NAMESPACE, _context_text_for_hit


def _hit(quote):
    return SimpleNamespace(payload={"document_id": "d", "chunk_id": 3, "source_quote": quote})


def _map(text):
    return {str(uuid.uuid5(CONTEXT_UUID_NAMESPACE, "d:3")): {"text": text}}


def test_the_window_is_centred_on_a_quote_the_chunk_wraps_over_lines():
    ctx = "Intro text. " * 80 + "The ISSO shall review\nthe access logs every week. " + "Tail text. " * 80
    window = _context_text_for_hit(_hit("The ISSO shall review the access logs every week."), _map(ctx), window=50)
    assert "review\nthe access logs every week." in window and window.startswith("...") and window.endswith("...")


def test_a_quote_that_is_not_in_the_chunk_falls_back_to_the_top():
    ctx = "Top of the chunk. " * 100
    window = _context_text_for_hit(_hit("Not there."), _map(ctx), window=50)
    assert window == ctx[:100] + "..."
