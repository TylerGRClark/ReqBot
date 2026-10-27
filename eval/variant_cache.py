"""Eval-only: freeze the model-written query variants so two retrieval setups see the same ones.

retrieve() asks a model to rewrite the question and (HyDE) to write a hypothetical answer.
HyDE samples at temperature 0.3 with no seed, so two runs of the SAME index can score
differently. For an A/B test of a ranking change that noise is not the thing being measured.
install() wraps those two calls in core.ask with a JSON file keyed by (call, model, question):
the first run writes each variant, every later run reads it back. Production code is untouched;
only eval scripts that call install() are affected. Delete the file to draw fresh variants.
"""
import json
from pathlib import Path

from core import ask


def install(path) -> None:
    path = Path(path)
    cache = json.loads(path.read_text()) if path.exists() else {}

    def save() -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, indent=1, sort_keys=True))
        tmp.replace(path)

    def freeze(name: str, original):
        def wrapped(question, model, *args, **kwargs):
            key = json.dumps([name, model, question])
            if key not in cache:
                cache[key] = original(question, model, *args, **kwargs)
                save()
            return cache[key]
        return wrapped

    ask.rewrite_query = freeze("rewrite", ask.rewrite_query)
    ask.generate_hyde_hypothesis = freeze("hyde", ask.generate_hyde_hypothesis)
