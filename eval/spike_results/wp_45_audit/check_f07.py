"""WP-45 audit verification (read-only). See eval/spike_results/wp_45_audit/README.md."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import sys
import json
import glob
import os
import re
import logging

pass
logging.disable(logging.CRITICAL)
from rapidfuzz import fuzz
from pipeline.parse_and_normalize import normalize_text, quote_word_coverage

# the report's polarity probe against the real WP-44.1 function
print(
    "probe: coverage('Users shall share passwords.' vs 'Users shall not share passwords.') =",
    quote_word_coverage("Users shall share passwords.", "Users shall not share passwords."),
)
# contractions ("isn't") need their own branch: a leading \b cannot match before the "n"
NEG = re.compile(r"\b(?:not|no|never|cannot|neither|nor|without|prohibited)\b|(?<=\w)n['’]t\b")
man = json.load(open(str(_ROOT / "eval/spike_results/wp_44/manifest.json")))["documents"]
P = os.path.expanduser("~/documents/processed")
tot = noncontig = neg_dropped = 0
ex = []
noncontig_ex = []
for doc, m in man.items():
    d = f"{P}/{m['run_dir']}"
    chunks = {
        c["chunk_id"]: c
        for c in (json.loads(l) for l in open(glob.glob(d + "/*_chunks.jsonl")[0]) if l.strip())
    }
    for l in open(glob.glob(d + "/*_requirements_normalized.jsonl")[0]):
        r = json.loads(l)
        c = chunks.get(r.get("chunk_id"))
        q = normalize_text(r.get("source_quote", ""))
        if not c or not q:
            continue
        tot += 1
        txt = normalize_text(c.get("text", ""))
        if q in txt:
            continue
        noncontig += 1
        if len(noncontig_ex) < 3:
            noncontig_ex.append((doc, r["source_quote"][:110]))
        al = fuzz.partial_ratio_alignment(q, txt)
        if al is None:
            continue
        span = txt[al.dest_start : al.dest_end]
        nq, ns = len(NEG.findall(q)), len(NEG.findall(span))
        if ns > nq:
            neg_dropped += 1
            if len(ex) < 5:
                ex.append((doc, r["source_quote"][:100], "| source span:", span[:100]))
print(
    f"survivors checked={tot}; quote NOT a contiguous substring of its chunk (after normalization)={noncontig} ({noncontig / tot:.1%})"
)
print(f"  of those, aligned source span has MORE negation words than the quote: {neg_dropped}")
for e in noncontig_ex:
    print("  non-contiguous e.g.", e)
for e in ex:
    print("  possible dropped negation:", e)
