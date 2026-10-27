"""eval/variant_cache.py freezes model-written query variants so A/B retrieval runs see identical ones."""
from core import ask
from eval import variant_cache


def test_variants_are_drawn_once_then_reused_across_runs(tmp_path, monkeypatch):
    calls = []

    def fake_rewrite(question, model, client):
        calls.append(("rewrite", question))
        return {"expanded_query": f"{question} #{len(calls)}", "control_ids": [], "domain_tags": []}

    def fake_hyde(question, model, client, **kwargs):
        calls.append(("hyde", question))
        return f"hypothesis {len(calls)}"

    monkeypatch.setattr(ask, "rewrite_query", fake_rewrite)
    monkeypatch.setattr(ask, "generate_hyde_hypothesis", fake_hyde)
    path = tmp_path / "variants.json"

    variant_cache.install(path)
    first = (ask.rewrite_query("q1", "m", None), ask.generate_hyde_hypothesis("q1", "m", None))
    assert ask.rewrite_query("q1", "m", None) == first[0]  # same run: reused
    assert len(calls) == 2

    monkeypatch.setattr(ask, "rewrite_query", fake_rewrite)
    monkeypatch.setattr(ask, "generate_hyde_hypothesis", fake_hyde)
    variant_cache.install(path)  # a later run reads the file
    assert (ask.rewrite_query("q1", "m", None), ask.generate_hyde_hypothesis("q1", "m", None)) == first
    assert len(calls) == 2  # no new model calls
    assert ask.rewrite_query("q2", "m", None) != first[0]  # a new question still draws once
    assert len(calls) == 3
