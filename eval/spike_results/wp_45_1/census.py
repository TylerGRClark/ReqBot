"""WP-45.1(a): fragment census over the 13 pinned documents (read-only; no LLM, no Qdrant).

Applies documented text signals to every record in the normalized tier and cross-tabulates them with the
parent-stem attachment method the production cascade uses, per signal, per document and per method.

The signals are SAMPLING AIDS, not classifiers: WP-38.1 found that lowercase-first, modal-first and
trailing-comma each also flag genuine, correctly kept requirements in this corpus (see
pipeline/parse_and_normalize.py::_is_dangling_clause). Nothing here estimates an error rate; the attachment
audit (WP-45.1b) does that with labelers.

Run from the repo root:  python3 eval/spike_results/wp_45_1/census.py [--records-out PATH] [--manifest-out PATH]
"""

import argparse
import collections
import hashlib
import importlib.metadata
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _p in (_ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
logging.disable(logging.CRITICAL)

from _inputs import corpus_inputs  # noqa: E402  (shared pinned-input check from the WP-45 audit scripts)
from core.profiles import default_profile  # noqa: E402
from pipeline import enrich_requirements as E  # noqa: E402
from pipeline import llm_extract_requirements as L  # noqa: E402
from pipeline.parse_and_normalize import _is_dangling_clause, normalize_text  # noqa: E402

BULLET_RE = re.compile(r"^[•·●▪*\-–—]\s*\S")
OPEN_END_RE = re.compile(r"(?:[;,]|\b(?:and|or))\s*$", re.IGNORECASE)
WORD_BUCKETS = [
    (0, 5, "<=5"),
    (6, 8, "6-8"),
    (9, 12, "9-12"),
    (13, 20, "13-20"),
    (21, 10**6, ">20"),
]
SIGNALS = [
    "lowercase_start",  # first alphabetic character is lowercase
    "list_marker",  # "(a) ", "1. ", "iv) " (production regex) or a bullet character
    "open_ending",  # ends with ; , or a trailing "and"/"or": a list item that continues
    "introduces_list",  # ends with ":": a governing stem, not a fragment (kept separate on purpose)
    "no_obligation_verb",  # none of the profile's obligation verbs appears
    "dangling_clause",  # production predicate: starts with a bare copula (WP-38.2)
    "not_contiguous",  # normalized quote is not a substring of its chunk text (audit F07)
]
# no_obligation_verb is reported but kept OUT of the composite: it fires on 56% of all records, including half
# of the >20-word full sentences, so it does not separate fragments from requirements in this corpus.
FRAGMENT_SIGNALS = ["lowercase_start", "list_marker", "open_ending", "dangling_clause"]
METHODS = ["same-chunk", "cross-chunk", "heading", "none", "not-a-candidate"]


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _first_alpha(text):
    return next((c for c in text if c.isalpha()), "")


def _bucket(n_words):
    return next(label for lo, hi, label in WORD_BUCKETS if lo <= n_words <= hi)


def attachment_method(quote, chunk_id, step_c_by_chunk, chunks_by_id):
    """Which step of the production cascade (enrich_requirements.reconstruct_parent_stem) supplies a stem."""
    if not E._is_reconstruction_candidate(quote):
        return "not-a-candidate", None
    stem = E._find_same_chunk_stem(quote, chunk_id, step_c_by_chunk)
    if stem:
        return "same-chunk", stem
    stem = E._find_cross_chunk_stem(chunk_id, step_c_by_chunk, chunks_by_id)
    if stem:
        return "cross-chunk", stem
    stem = E._find_heading_stem(quote, chunk_id, chunks_by_id)
    if stem:
        return "heading", stem
    return "none", None


def record_signals(quote, chunk_text, verb_re):
    q = quote.strip()
    return {
        "lowercase_start": _first_alpha(q).islower(),
        "list_marker": bool(E._LIST_MARKER_RE.match(q) or BULLET_RE.match(q)),
        "open_ending": bool(OPEN_END_RE.search(q)),
        "introduces_list": q.endswith(":"),
        "no_obligation_verb": not verb_re.search(q),
        "dangling_clause": bool(_is_dangling_clause(q)),
        "not_contiguous": bool(
            chunk_text is not None and normalize_text(q) not in normalize_text(chunk_text)
        ),
    }


def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def collect(inputs, verb_re):
    rows = []
    for doc, files in inputs.items():
        norm = files["normalized"]
        step_c, chunks_by_id = E._load_reconstruction_sources(norm)
        chunk_text = {c["chunk_id"]: c.get("text", "") for c in _read_jsonl(files["chunks"])}
        for r in _read_jsonl(norm):
            quote = (r.get("source_quote") or "").strip()
            cid = r.get("chunk_id")
            method, stem = ("not-a-candidate", None)
            if quote and cid is not None:
                method, stem = attachment_method(quote, cid, step_c, chunks_by_id)
            signals = (
                record_signals(quote, chunk_text.get(cid), verb_re)
                if quote
                else {s: False for s in SIGNALS}
            )
            rows.append(
                {
                    "document": doc,
                    "requirement_id": r.get("requirement_id"),
                    "chunk_id": cid,
                    "words": len(quote.split()),
                    "method": method,
                    "stem": stem,
                    "stored_stem": r.get("parent_stem") or None,
                    "signals": signals,
                }
            )
    return rows


def pct(n, d):
    return f"{n / d:6.1%}" if d else "   n/a"


def report(rows):
    n = len(rows)
    out = []
    emit = out.append

    emit(f"records in the normalized tier: {n}")
    cands = [r for r in rows if r["method"] != "not-a-candidate"]
    emit(
        f"reconstruction candidates (production predicate, <= {E._MAX_CANDIDATE_WORDS} words / list marker / "
        f"dangling clause): {len(cands)} ({pct(len(cands), n)})"
    )
    by_method = collections.Counter(r["method"] for r in rows)
    emit("\nA. Attachment method (the production cascade, recomputed):")
    for m in METHODS:
        emit(f"   {m:16s} {by_method[m]:5d}  {pct(by_method[m], n)} of records")
    stored = sum(1 for r in rows if r["stored_stem"])
    recomputed = sum(1 for r in rows if r["stem"])
    mismatch = [r for r in rows if (r["stored_stem"] or None) != (r["stem"] or None)]
    emit(
        f"   stems stored in the data: {stored}; recomputed now: {recomputed}; records where they differ: {len(mismatch)}"
    )

    emit(
        "\nB. Signals, over all records (sampling aids, not classifiers; no_obligation_verb is context only):"
    )
    for s in SIGNALS:
        c = sum(1 for r in rows if r["signals"][s])
        emit(f"   {s:20s} {c:5d}  {pct(c, n)}")
    emit(
        "   word count: "
        + ", ".join(
            f"{label}={sum(1 for r in rows if _bucket(r['words']) == label)}"
            for _, _, label in WORD_BUCKETS
        )
    )

    emit(
        f"\nC. How many fragment signals fire per record (of {', '.join(FRAGMENT_SIGNALS)}; "
        "no_obligation_verb excluded):"
    )
    dist = collections.Counter(sum(r["signals"][s] for s in FRAGMENT_SIGNALS) for r in rows)
    for k in sorted(dist):
        emit(f"   {k} signal(s): {dist[k]:5d}  {pct(dist[k], n)}")

    emit(
        "\nD. Signals by attachment method (count of records with the signal / records with that method):"
    )
    head = "   " + f"{'signal':20s}" + "".join(f"{m:>17s}" for m in METHODS)
    emit(head)
    for s in SIGNALS:
        cells = []
        for m in METHODS:
            pool = [r for r in rows if r["method"] == m]
            cells.append(f"{sum(1 for r in pool if r['signals'][s])}/{len(pool)}")
        emit("   " + f"{s:20s}" + "".join(f"{c:>17s}" for c in cells))
    emit(
        "   word count by method: "
        + "; ".join(
            f"{m}: "
            + ",".join(
                f"{lbl}={sum(1 for r in rows if r['method'] == m and _bucket(r['words']) == lbl)}"
                for _, _, lbl in WORD_BUCKETS
            )
            for m in METHODS
        )
    )

    emit(
        "\nE. Candidates that got NO stem, by how fragment-shaped they look (fragment signals fired):"
    )
    none_ = [r for r in rows if r["method"] == "none"]
    d2 = collections.Counter(sum(r["signals"][s] for s in FRAGMENT_SIGNALS) for r in none_)
    for k in sorted(d2):
        emit(
            f"   {k} signal(s): {d2[k]:5d}  {pct(d2[k], len(none_))} of the {len(none_)} no-stem candidates"
        )

    emit("\nF. Attached stems, by whether the quote looks like a fragment (>= 1 fragment signal):")
    for m in ("same-chunk", "cross-chunk", "heading"):
        pool = [r for r in rows if r["method"] == m]
        looks = sum(1 for r in pool if any(r["signals"][s] for s in FRAGMENT_SIGNALS))
        emit(
            f"   {m:12s} {len(pool):4d} attached | {looks:4d} look like fragments | {len(pool) - looks:4d} do not"
        )
    any_sig = sum(1 for r in rows if any(r["signals"][s] for s in FRAGMENT_SIGNALS))
    two_sig = sum(1 for r in rows if sum(r["signals"][s] for s in FRAGMENT_SIGNALS) >= 2)
    emit(
        f"   records with >= 1 fragment signal, any method: {any_sig} ({pct(any_sig, n)}); >= 2: {two_sig}"
    )
    emit(
        "   LIMIT: the signals are lexical. A fragment written as a capitalised imperative sentence (a sibling bullet such\n"
        '   as "Retain visitor logs.") fires none of them, so these counts are a floor on fragment-shaped records, not a\n'
        "   prevalence. Prevalence and attachment correctness come from the labeled audit (WP-45.1b/e)."
    )

    emit(
        "\nG. Per document (records | candidates | stems same/cross/heading | none | signals: "
        + " ".join(s[:6] for s in FRAGMENT_SIGNALS)
        + " | intro noncon noverb):"
    )
    docs = list(dict.fromkeys(r["document"] for r in rows))
    for doc in docs:
        rs = [r for r in rows if r["document"] == doc]
        m = collections.Counter(r["method"] for r in rs)
        cnt = {s: sum(1 for r in rs if r["signals"][s]) for s in SIGNALS}
        emit(
            f"   {doc:18s} {len(rs):4d} | {len(rs) - m['not-a-candidate']:4d} | "
            f"{m['same-chunk']:3d}/{m['cross-chunk']:3d}/{m['heading']:2d} | {m['none']:4d} | "
            + " ".join(f"{cnt[s]:5d}" for s in FRAGMENT_SIGNALS)
            + f" | {cnt['introduces_list']:5d} {cnt['not_contiguous']:6d} {cnt['no_obligation_verb']:6d}"
        )
    return "\n".join(out), mismatch


def build_manifest(inputs):
    def version(name):
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None

    try:
        rev = (
            subprocess.run(
                ["git", "-C", str(_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
            ).stdout.strip()
            or "unavailable"
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        rev = "unavailable"  # no git on PATH: say so, rather than crash or guess
    profile = default_profile()
    template = L.PASS1_PROMPT_TEMPLATE.replace(
        "{obligation_verbs}", ", ".join(profile["obligation_verbs"])
    )
    return {
        "script": "eval/spike_results/wp_45_1/census.py",
        "git_revision": rev,
        "python": sys.version.split()[0],
        "docling": version("docling"),
        "docling_core": version("docling-core"),
        "profile": profile["name"],
        "step_c_prompt_template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest()[:16],
        "inputs_sha256": {
            doc: {kind: _sha256(path) for kind, path in files.items()}
            for doc, files in inputs.items()
        },
        "note": "No LLM or Qdrant access. The extraction model that produced the inputs is recorded per raw "
        "response (llama3.1:8b-instruct-q4_K_M for the pinned runs).",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--records-out", help="write one JSON line per record (signals, method, stem) here"
    )
    ap.add_argument("--manifest-out", help="write the input/version manifest here")
    args = ap.parse_args()

    inputs = corpus_inputs("chunks", "extracted", "normalized")
    verbs = default_profile()["obligation_verbs"]
    verb_re = re.compile(r"\b(?:" + "|".join(re.escape(v) for v in verbs) + r")\b", re.IGNORECASE)
    rows = collect(inputs, verb_re)
    text, mismatch = report(rows)
    print(text)
    if mismatch:
        print(
            f"\nrecords whose stored stem differs from the recomputed one ({len(mismatch)}), first 5:"
        )
        for r in mismatch[:5]:
            print(
                "  ",
                r["document"],
                r["chunk_id"],
                repr((r["stored_stem"] or "")[:50]),
                "->",
                repr((r["stem"] or "")[:50]),
            )
    if args.records_out:
        with open(args.records_out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if args.manifest_out:
        Path(args.manifest_out).write_text(
            json.dumps(build_manifest(inputs), indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
