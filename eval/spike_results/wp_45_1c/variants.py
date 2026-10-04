"""WP-45.1(c)/(d): the embedded-text variants compared in the retrieval test (pure functions; no I/O).

Every variant is built through the production `build_embedding_text`, so the `Ref:` line and the stem-then-quote layout
match what the index holds. The reconstruction cascade joins a stem and a quote as `stem + "\\n" + quote`; the oracle
variant uses the same layout with Tyler's adjudicated lead-in in the stem's place.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.embed_and_index import build_embedding_text  # noqa: E402


def production_text(payload):
    """What the live index embedded for this record."""
    return build_embedding_text(payload)


def has_stem(payload):
    """The live record carries a reconstructed stem (embedding_text is only set when reconstruction found one)."""
    return bool((payload.get("embedding_text") or "").strip())


def quote_alone_text(payload):
    """The same record without its stem: the verbatim quote plus the Ref line."""
    return build_embedding_text({**payload, "embedding_text": ""})


def clean_lead_in(lead_in):
    """Adjudicated lead-ins join several passages with ' | '; in running text they are simply consecutive."""
    return " ".join(part.strip() for part in lead_in.split("|") if part.strip())


def oracle_text(payload, lead_in):
    """Adjudicated lead-in in the stem's place: lead-in, newline, quote, then the Ref line."""
    quote = (payload.get("source_quote") or "").strip()
    return build_embedding_text({**payload, "embedding_text": f"{clean_lead_in(lead_in)}\n{quote}"})


def heading_text(payload, leaf):
    """The leaf heading in front of whatever the live index embedded (stem and quote, or the quote), then the Ref line."""
    body = (payload.get("embedding_text") or "").strip() or (payload.get("source_quote") or "").strip()
    return build_embedding_text({**payload, "embedding_text": f"{leaf}\n{body}"})
