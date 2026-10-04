"""WP-45.1(b): score the attachment audit (read-only; no LLM, no Qdrant).

Inputs: the answer key written by audit_pack.py, both labelers' pass A / pass B files, and (optionally) Tyler's
adjudication and spot-check answers. Writes nothing into the pack.

  python3 score_audit.py --key KEY --labels-dir DIR --sheet-out PATH          # agreement + adjudication sheet
  python3 score_audit.py --key KEY --labels-dir DIR --answers PATH            # final tables

Label files are DIR/labels_{claude,codex}_{a,b}.jsonl. The analysis below was written before any label existed.

Definitions
  disagreement, pass A: the (standalone, lead_in_location) pair differs between the labelers
  disagreement, pass B: stem_verdict differs
  resolved label: the agreed value; Tyler's answer where they disagreed; Tyler's value where he changed a
  spot-checked agreement
  estimates: per stratum x/n (Wilson 95%, no finite-population correction, so slightly wide) and pooled estimates
  weighted by stratum population / sample size, with a finite-population-corrected normal interval
"""

import argparse
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

LABELERS = ("claude", "codex")
ATTACHED = ("same-chunk", "cross-chunk", "heading")
NO_STEM = ("none+signal", "none+nosignal", "not-a-candidate+signal", "not-a-candidate+nosignal")
STANDALONE = {"complete", "needs_lead_in", "not_a_requirement"}
LOCATIONS = {"same_chunk", "previous_chunk", "section_heading", "not_shown"}
VERDICTS = {"right", "wrong_sibling", "fragment_chain", "not_needed", "wrong_other"}
SPOT_CHECKS = 10
SPOT_SEED = "wp45.1b/spot"


def read_jsonl(path):
    records = (
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return {rec["id"]: rec for rec in records}


def a_key(rec):
    return (rec["standalone"], rec.get("lead_in_location"))


def b_key(rec):
    return rec["stem_verdict"]


def wilson(x, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def kappa(pairs):
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def weighted(strata, sample_counts, hits, population):
    """Pooled proportion over `strata`: sum(N_h * x_h / n_h) / sum(N_h), with an FPC normal interval.

    Raises ValueError for a design that cannot be estimated: a stratum with no population, fewer than 2 sampled
    records, more sampled than exist, or more hits than sampled. Returning a number for those would hide a broken key.
    """
    for s in strata:
        n, x, pop = sample_counts.get(s, 0), hits.get(s, 0), population[s]
        if pop <= 0 or n < 2 or n > pop or x > n:
            raise ValueError(
                f"stratum {s!r} cannot be estimated: population {pop}, sampled {n}, hits {x}"
            )
    big_n = sum(population[s] for s in strata)
    total, var = 0.0, 0.0
    for s in strata:
        n, x, pop = sample_counts[s], hits.get(s, 0), population[s]
        p = x / n
        total += pop * p
        var += pop * pop * (1 - n / pop) * p * (1 - p) / (n - 1)
    est = total / big_n
    se = math.sqrt(var) / big_n
    return est, max(0.0, est - 1.96 * se), min(1.0, est + 1.96 * se), total


def tokens(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def texts_overlap(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    return inter / len(ta | tb) >= 0.5 or inter / min(len(ta), len(tb)) >= 0.8


def load(args):
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    labels = {}
    for who in LABELERS:
        for p in "ab":
            path = Path(args.labels_dir) / f"labels_{who}_{p}.jsonl"
            if not path.exists():
                sys.exit(f"missing {path}")
            labels[(who, p)] = read_jsonl(path)
    return key, labels


def disagreements(key, labels):
    ids = sorted(key["items"])
    a_pairs = {i: (labels[("claude", "a")][i], labels[("codex", "a")][i]) for i in ids}
    attached = [i for i in ids if key["items"][i]["stem"]]
    b_pairs = {i: (labels[("claude", "b")][i], labels[("codex", "b")][i]) for i in attached}
    dis_a = [i for i, (x, y) in a_pairs.items() if a_key(x) != a_key(y)]
    dis_b = [i for i, (x, y) in b_pairs.items() if b_key(x) != b_key(y)]
    return a_pairs, b_pairs, dis_a, dis_b


def spot_check_items(a_pairs, b_pairs, dis_a, dis_b):
    agreed = [(i, "a") for i in sorted(a_pairs) if i not in dis_a] + [
        (i, "b") for i in sorted(b_pairs) if i not in dis_b
    ]
    return sorted(random.Random(SPOT_SEED).sample(agreed, min(SPOT_CHECKS, len(agreed))))


def agreement_text(a_pairs, b_pairs, dis_a, dis_b):
    out = ["## Agreement between the two labelers", ""]
    sa = [(x["standalone"], y["standalone"]) for x, y in a_pairs.values()]
    out.append(
        f"- pass A `standalone`: {sum(p == q for p, q in sa)}/{len(sa)} agree, kappa {kappa(sa):.2f}"
    )
    both = [
        (x["lead_in_location"], y["lead_in_location"])
        for x, y in a_pairs.values()
        if x["standalone"] == y["standalone"] == "needs_lead_in"
    ]
    out.append(
        f"- pass A `lead_in_location` where both said needs_lead_in: {sum(p == q for p, q in both)}/{len(both)} agree, "
        f"kappa {kappa(both):.2f}"
    )
    out.append(f"- pass A disagreements on (standalone, location): {len(dis_a)} of {len(a_pairs)}")
    vb = [(x["stem_verdict"], y["stem_verdict"]) for x, y in b_pairs.values()]
    out.append(
        f"- pass B `stem_verdict`: {sum(p == q for p, q in vb)}/{len(vb)} agree, kappa {kappa(vb):.2f}"
    )
    out.append(f"- pass B disagreements: {len(dis_b)} of {len(b_pairs)}")
    return out


def card_from(pack_dir, path_name, rid):
    text = (Path(pack_dir) / path_name).read_text(encoding="utf-8")
    m = re.search(rf"^## {rid}\s*$.*?(?=^## R\d{{3}}\s*$|\Z)", text, flags=re.M | re.S)
    return m.group(0).strip() if m else f"(card {rid} not found)"


def sheet(args, key, labels, a_pairs, b_pairs, dis_a, dis_b, spot):
    out = ["# Adjudication sheet (WP-45.1b)", ""]
    out.append(
        f"{len(dis_a)} pass A and {len(dis_b)} pass B disagreements, then {len(spot)} agreements to spot-check. "
        "Answer each with a short line, for example `R012 a: codex`, `R019 a: claude`, `R031 a: other needs_lead_in same_chunk`, "
        "`R044 a: other complete`, `R050 b: other wrong_sibling`; for spot-checks `R007 a: ok` or `R007 a: other complete`.\n"
    )

    def show(rid, p, pair):
        x, y = pair
        out.append(f"### {rid}, pass {p.upper()}")
        if p == "b":  # a stem cannot be judged without the text around the quote
            out.append(card_from(args.pack_dir, "pack_a.md", rid))
        out.append(card_from(args.pack_dir, f"pack_{p}.md", rid))
        if p == "a":
            for who, rec in zip(LABELERS, (x, y)):
                out.append(
                    f"- **{who}**: {rec['standalone']}, {rec.get('lead_in_location')}; lead-in: "
                    f"{rec.get('lead_in_text')!r}; note: {rec.get('note') or ''}"
                )
        else:
            for who, rec in zip(LABELERS, (x, y)):
                out.append(f"- **{who}**: {rec['stem_verdict']}; note: {rec.get('note') or ''}")
        out.append("")

    out.append("## Disagreements\n")
    for rid in dis_a:
        show(rid, "a", a_pairs[rid])
    for rid in dis_b:
        show(rid, "b", b_pairs[rid])
    out.append("## Spot-check of agreements (both labelers gave the same label)\n")
    for rid, p in spot:
        pair = a_pairs[rid] if p == "a" else b_pairs[rid]
        show(rid, p, pair)
    Path(args.sheet_out).write_text("\n".join(out) + "\n", encoding="utf-8")


def parse_answers(path):
    """`R012 a: codex` | `R012 b: other wrong_sibling` | `R007 a: ok` | `R107 a: other needs_lead_in same_chunk :: <text>`.

    The pass letter is required (some ids are open in both passes). Everything after ' :: ' is the verbatim lead-in
    text to the end of the line, so it may contain '#'; a ' # comment' is only recognized before it. Returns
    {(id, pass): 'claude'|'codex'|'ok'|('other', words, text)}.
    """
    ans = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        head, sep, text = line.partition(" :: ")
        head = re.sub(r"\s+#.*$", "", head).strip()
        m = re.match(r"(R\d{3})\s+([ab])\s*:\s*(\w+)(?:\s+(.*))?$", head)
        if not m:
            sys.exit(f"{path} line {n}: cannot read {line!r} (expected `R012 a: codex`)")
        rid, p, kind, rest = m.groups()
        if kind == "other":
            words, text = (rest or "").split(), text.strip() or None
            problem = other_problem(p, words, text)
            if problem:
                sys.exit(f"{path} line {n}: {problem} in {line.strip()!r}")
            ans[(rid, p)] = ("other", words, text)
        elif kind in ("claude", "codex", "ok"):
            if rest or sep:
                sys.exit(f"{path} line {n}: '{kind}' takes nothing after it, got {line.strip()!r}")
            ans[(rid, p)] = kind
        else:
            sys.exit(f"{path} line {n}: expected claude, codex, ok or other, got {kind!r}")
    return ans


def other_problem(p, words, text):
    """Why an `other ...` answer cannot be used, or None.

    Pass A: `<standalone> [<location> [:: <lead-in text>]]`; the text is required for same_chunk, previous_chunk and
    section_heading (so the consistency check covers the correction) and not allowed otherwise. Pass B: `<verdict>`.
    """
    if p == "b":
        if text or len(words) != 1 or words[0] not in VERDICTS:
            return f"pass B needs one verdict from {sorted(VERDICTS)} and no text"
        return None
    if not words or words[0] not in STANDALONE:
        return f"pass A needs a standalone value from {sorted(STANDALONE)}"
    if words[0] != "needs_lead_in":
        return None if len(words) == 1 and not text else f"{words[0]} takes no location or text"
    if len(words) != 2 or words[1] not in LOCATIONS:
        return f"needs_lead_in needs a location from {sorted(LOCATIONS)}"
    if words[1] == "not_shown":
        return "not_shown takes no text" if text else None
    return None if text else f"{words[1]} needs the lead-in text after ' :: '"


def resolve(a_pairs, b_pairs, dis_a, dis_b, spot, answers, policy=None):
    """Resolved pass A (standalone, location, lead-in text) and pass B verdict per id.

    Disagreements take the answer (or, for a sensitivity run, `policy`: always one labeler). An agreed item changes only
    if Tyler's answer is not "ok"; that is a spot-check change if the item was sampled, otherwise a later correction.
    Returns ra, rb, unresolved, spot_changes, corrections.
    """
    unresolved, spot_changes, corrections = [], [], []
    spot_set = set(spot)

    # An answer must name an item that exists in that pass; anything else is a typo, not an adjudication.
    valid = {(rid, "a") for rid in a_pairs} | {(rid, "b") for rid in b_pairs}
    stray = sorted(k for k in answers if k not in valid)
    if stray:
        sys.exit(f"answers for items that do not exist in that pass: {stray}")

    def pick_for(rid, p, disputed):
        a = answers.get((rid, p))
        if disputed:
            if policy:
                return policy
            if a == "ok":
                sys.exit(
                    f"{rid} pass {p} is disputed but the answer is 'ok'; name claude, codex or other"
                )
            return a
        if a is None or a == "ok":
            return None
        if a in ("claude", "codex"):
            sys.exit(
                f"{rid} pass {p} was agreed by both labelers; '{a}' is not an answer for it (use ok or other)"
            )
        (spot_changes if (rid, p) in spot_set else corrections).append((rid, p))
        return a

    ra, rb = {}, {}
    for rid, (x, y) in a_pairs.items():
        disputed = rid in dis_a
        pick = pick_for(rid, "a", disputed)
        if disputed and pick is None:
            unresolved.append((rid, "a"))
            continue
        text = x.get("lead_in_text") or y.get("lead_in_text")
        if pick in ("claude", "codex"):
            rec = x if pick == "claude" else y
            ra[rid] = (rec["standalone"], rec.get("lead_in_location"), rec.get("lead_in_text"))
        elif isinstance(pick, tuple):
            words = pick[1]
            ra[rid] = (words[0], words[1] if len(words) > 1 else None, pick[2])
        else:
            ra[rid] = (x["standalone"], x.get("lead_in_location"), text)
    for rid, (x, y) in b_pairs.items():
        disputed = rid in dis_b
        pick = pick_for(rid, "b", disputed)
        if disputed and pick is None:
            unresolved.append((rid, "b"))
            continue
        if pick in ("claude", "codex"):
            rb[rid] = (x if pick == "claude" else y)["stem_verdict"]
        elif isinstance(pick, tuple):
            rb[rid] = pick[1][0]
        else:
            rb[rid] = x["stem_verdict"]
    return ra, rb, unresolved, spot_changes, corrections


def table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def pct(x):
    return f"{100 * x:5.1f}%"


def estimates(key, ra, rb):
    pop, samp = key["population"], key["sample"]
    items = key["items"]
    by_stratum = defaultdict(list)
    for rid, it in items.items():
        by_stratum[it["stratum"]].append(rid)
    out = []

    # Pass B: attachment precision
    out += ["## Attachment precision (pass B, resolved)", ""]
    verdicts = ["right", "wrong_sibling", "fragment_chain", "not_needed", "wrong_other"]
    rows, hits_right, hits_mis, hits_inc = [], {}, {}, {}
    for s in ATTACHED:
        ids = [r for r in by_stratum[s] if r in rb]
        c = Counter(rb[r] for r in ids)
        n = len(ids)
        lo, hi = wilson(c["right"], n)
        hits_right[s] = c["right"]
        hits_mis[s] = c["wrong_sibling"] + c["wrong_other"]
        hits_inc[s] = c["fragment_chain"]
        rows.append(
            [s, n]
            + [c[v] for v in verdicts]
            + [f"{pct(c['right'] / n) if n else 'n/a'} ({pct(lo)} to {pct(hi)})"]
        )
    out += table(rows, ["stratum", "n"] + verdicts + ["right (Wilson 95%)"])
    counts = {s: sum(1 for r in by_stratum[s] if r in rb) for s in ATTACHED}
    for label, hits in (
        ("right", hits_right),
        ("misleading (wrong_sibling or wrong_other)", hits_mis),
        ("incomplete (fragment_chain)", hits_inc),
    ):
        e, lo, hi, tot = weighted(ATTACHED, counts, hits, pop)
        out.append(
            f"\nPooled over the {sum(pop[s] for s in ATTACHED)} attachments, {label}: {pct(e)} "
            f"(95% {pct(lo)} to {pct(hi)}), about {tot:.0f} records"
        )

    # Pass A: need rate per stratum
    out += ["", "## Records that need a lead-in (pass A, resolved)", ""]
    rows, need_hits = [], {}
    for s in pop:
        ids = by_stratum[s]
        n = len(ids)
        x = sum(1 for r in ids if ra[r][0] == "needs_lead_in")
        nr = sum(1 for r in ids if ra[r][0] == "not_a_requirement")
        need_hits[s] = x
        lo, hi = wilson(x, n)
        rows.append(
            [s, pop[s], n, x, nr, f"{pct(x / n)} ({pct(lo)} to {pct(hi)})", f"{pop[s] * x / n:.0f}"]
        )
    out += table(
        rows,
        [
            "stratum",
            "population",
            "n",
            "needs_lead_in",
            "not_a_requirement",
            "need rate (Wilson)",
            "est. records",
        ],
    )
    cnt_all = {s: len(by_stratum[s]) for s in pop}
    e, lo, hi, tot = weighted(list(pop), cnt_all, need_hits, pop)
    out.append(
        f"\nAll {sum(pop.values())} records: {pct(e)} need a lead-in (95% {pct(lo)} to {pct(hi)}), about {tot:.0f}"
    )
    e, lo, hi, tot = weighted(list(NO_STEM), cnt_all, {s: need_hits[s] for s in NO_STEM}, pop)
    out.append(
        f"Records with no stem that need one: {pct(e)} of {sum(pop[s] for s in NO_STEM)} "
        f"(95% {pct(lo)} to {pct(hi)}), about {tot:.0f} (the misses)"
    )

    # Where the missing context lives, for sizing the context-supply fixes
    out += [
        "",
        "## Where the missing lead-in lives (records that need one, weighted to the population)",
        "",
    ]
    locs = ["same_chunk", "previous_chunk", "section_heading", "not_shown"]
    est_att = Counter()
    est_none = Counter()
    n_loc = Counter()
    for rid, it in items.items():
        if ra[rid][0] != "needs_lead_in":
            continue
        st = it["stratum"]
        w = pop[st] / len(by_stratum[st])
        n_loc[ra[rid][1]] += 1
        (est_att if st in ATTACHED else est_none)[ra[rid][1]] += w
    rows = [
        [
            loc,
            n_loc[loc],
            f"{est_att[loc]:.0f}",
            f"{est_none[loc]:.0f}",
            f"{est_att[loc] + est_none[loc]:.0f}",
        ]
        for loc in locs
    ]
    out += table(
        rows,
        [
            "location",
            "in sample",
            "est. among the 203 with a stem",
            "est. among the 1,644 without",
            "est. total",
        ],
    )

    # Root-cause table over records that need a lead-in
    out += [
        "",
        "## Root-cause classes among records that need a lead-in (weighted to the population)",
        "",
    ]
    classes = Counter()
    per_stratum = defaultdict(Counter)
    for rid, it in items.items():
        if ra[rid][0] != "needs_lead_in":
            continue
        loc = ra[rid][1]
        if it["stem"]:
            v = rb[rid]
            cls = {
                "right": "stem is right",
                "wrong_sibling": "(4) sibling bullet accepted as the stem",
                "fragment_chain": "stem is itself a fragment (chain)",
                "wrong_other": "stem unrelated to the quote",
                "not_needed": "stem judged not needed although lead-in is needed",
            }[v]
            if v != "right":
                cls += f"; true lead-in: {loc}"
        else:
            cls = {
                "same_chunk": "(3) no stem, lead-in is earlier in the same chunk",
                "previous_chunk": "(1) no stem, lead-in is in the previous chunk",
                "section_heading": "no stem, only the section heading governs",
                "not_shown": "no stem, lead-in not recoverable from the text shown",
            }[loc]
        per_stratum[it["stratum"]][cls] += 1
        classes[cls] += 1
    rows = []
    for cls in sorted(classes):
        est = sum(pop[s] * per_stratum[s][cls] / len(by_stratum[s]) for s in pop)
        rows.append([cls, classes[cls], f"{est:.0f}"])
    out += table(rows, ["class", "in sample", "est. records in 1,847"])
    out.append(
        "\nRoot cause (2), Docling hierarchy missing or wrong, cannot be established from text labels."
    )

    # Stems attached to quotes that are complete
    out += ["", "## Stems on quotes that are already complete", ""]
    comp = [r for r, it in items.items() if it["stem"] and ra[r][0] == "complete"]
    c = Counter(rb[r] for r in comp)
    out.append(
        f"{len(comp)} of the {sum(1 for it in items.values() if it['stem'])} sampled attachments are on complete quotes: "
        + ", ".join(f"{v} {c[v]}" for v in verdicts)
    )
    return out, ra, rb


def cross_check(key, ra, rb):
    out = ["", "## Consistency check: pass A lead-in text against the attached stem", ""]
    odd = []
    for rid, it in key["items"].items():
        if not it["stem"] or ra[rid][0] != "needs_lead_in" or ra[rid][2] is None:
            continue
        ov = texts_overlap(ra[rid][2], it["stem"])
        v = rb[rid]
        # a chain stem overlaps the lead-in by design; only these combinations contradict each other
        if (v == "right" and not ov) or (v in ("wrong_sibling", "wrong_other") and ov):
            odd.append((rid, v, "overlap" if ov else "no overlap"))
    out.append(
        f"{len(odd)} records where the verdict and the text overlap contradict each other (right without overlap, or "
        "wrong_sibling/wrong_other with overlap); read these before trusting the table: "
        + (", ".join(f"{r} ({v}, {o})" for r, v, o in odd) or "none")
    )
    return out


def provenance(args):
    """Fail fast if the key or the pack do not match the manifest written when the pack was built; list label hashes."""
    manifest_path = Path(__file__).parent / "outputs/audit_pack_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["audit_pack"]
    key_hash = hashlib.sha256(Path(args.key).read_bytes()).hexdigest()
    if key_hash != manifest["answers_sha256"]:
        sys.exit(
            f"answer key {args.key} does not match the manifest ({key_hash} != {manifest['answers_sha256']})"
        )
    out = [
        "## Provenance",
        "",
        f"- answer key sha256 {key_hash[:16]} matches outputs/audit_pack_manifest.json",
    ]
    if args.pack_dir:
        for name, want in manifest["file_sha256"].items():
            got = hashlib.sha256((Path(args.pack_dir) / name).read_bytes()).hexdigest()
            if got != want:
                sys.exit(f"{name} in {args.pack_dir} does not match the manifest")
        out.append(f"- pack, rubric and checker in {args.pack_dir} match the manifest")
    for who in LABELERS:
        for p in "ab":
            path = Path(args.labels_dir) / f"labels_{who}_{p}.jsonl"
            out.append(f"- {path.name} sha256 {hashlib.sha256(path.read_bytes()).hexdigest()[:16]}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--labels-dir", required=True)
    ap.add_argument("--pack-dir", help="needed with --sheet-out")
    ap.add_argument("--sheet-out")
    ap.add_argument("--answers", help="Tyler's adjudication and spot-check answers")
    ap.add_argument(
        "--policy",
        choices=LABELERS,
        help="sensitivity run: resolve every disagreement to one labeler and ignore --answers on disagreements",
    )
    args = ap.parse_args()
    key, labels = load(args)
    print("\n".join(provenance(args)) + "\n")
    a_pairs, b_pairs, dis_a, dis_b = disagreements(key, labels)
    spot = spot_check_items(a_pairs, b_pairs, dis_a, dis_b)
    print("\n".join(agreement_text(a_pairs, b_pairs, dis_a, dis_b)))
    if args.sheet_out:
        if not args.pack_dir:
            sys.exit("--sheet-out needs --pack-dir")
        sheet(args, key, labels, a_pairs, b_pairs, dis_a, dis_b, spot)
        print(
            f"\nadjudication sheet: {args.sheet_out} ({len(dis_a) + len(dis_b)} disagreements, {len(spot)} spot-checks)"
        )
    if args.answers or args.policy:
        answers = parse_answers(args.answers) if args.answers else {}
        ra, rb, unresolved, spot_changes, corrections = resolve(
            a_pairs, b_pairs, dis_a, dis_b, spot, answers, args.policy
        )
        if unresolved:
            sys.exit(f"unresolved disagreements, no tables: {unresolved}")
        out = []
        if args.policy:
            out.append(
                f"SENSITIVITY RUN: every disagreement resolved to {args.policy}; adjudication answers on disagreements ignored\n"
            )
        body, ra, rb = estimates(key, ra, rb)
        out += body + cross_check(key, ra, rb)
        out.append(
            f"\nSpot-checks: {len(spot) - len(spot_changes)} of {len(spot)} confirmed, {len(spot_changes)} changed {spot_changes}"
        )
        out.append(
            f"Corrections to agreed items outside the spot-check: {len(corrections)} {corrections}"
        )
        print("\n" + "\n".join(out))


if __name__ == "__main__":
    main()
