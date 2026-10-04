"""WP-45.1(c)/(d): check the written queries against the writing rules and measure their wording overlap (offline).

Reads `queries.jsonl` and `query_packet.md` only (no group labels, no retrieval). For every query it reports
  - the longest run of consecutive words shared with the card (rule 2: no run of four or more; the quote for both styles,
    plus the lead-in for the topic style, since only a party question has to repeat a party's name),
  - the share of the query's content words that also occur in the card's quote or lead-in (reported with the results),
  - rule 3: 8 to 30 words, ending in a question mark.

Run from the repo root:  python3 eval/spike_results/wp_45_1c/query_check.py [--json-out PATH]
Exit status 1 if any rule is broken, so a flaw is fixed before the file is frozen and never after a retrieval.
"""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

MAX_RUN = 3  # a run of four or more consecutive words from the card is copying
# Proper names and terms of art that cannot be paraphrased. Fixed with the queries; a run inside one of these is not copying.
NAMED_ENTITIES = (
    "joint federated assurance center",
    "title 10 u s c",
    "tier 1 and tier 2 tcas",
    "carm training and outreach program",
    "defense and national leadership command capability",
    "education and training command",
    "authorized funding official",
    "joint staff j-6",
    "services and defense agencies",
)
MIN_WORDS, MAX_WORDS = 8, 30
STOP = set(
    "a an the of and or to for in on by with at from as is are be it its this that these those which what who how when "
    "where why must should shall will may can do does did their there than then into under over about also any each all "
    "have has had not no if so such per via".split()
)


def words(text):
    return re.findall(r"[a-z0-9][a-z0-9&/\-']*", text.lower())


def mask_entities(tokens):
    """Replace each allowlisted named entity by one placeholder token that never matches across texts."""
    text = " " + " ".join(tokens) + " "
    for i, name in enumerate(NAMED_ENTITIES):
        text = text.replace(f" {name} ", f" @entity{i} ")
    return text.split()


def longest_common_run(a, b):
    """Length of the longest run of consecutive tokens that appears in both lists (named entities count as one token)."""
    a, b = mask_entities(a), mask_entities(b)
    best = 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def content_overlap(query, source):
    """Share of the query's content words (stop words removed) that also occur in the source text."""
    q = [w for w in words(query) if w not in STOP]
    if not q:
        return 0.0
    s = set(words(source))
    return sum(1 for w in q if w in s) / len(q)


def parse_packet(text):
    """{pid: {"quote": str, "lead_in": str}} from query_packet.md."""
    cards = {}
    parts = re.split(r"^## (P\d{3})\s*$", text, flags=re.M)
    for pid, body in zip(parts[1::2], parts[2::2]):
        quote = re.search(r"Quote \(verbatim\):\n> (.*)", body)
        lead = re.search(r"adjudication\):\n> (.*)", body)
        cards[pid] = {"quote": quote.group(1) if quote else "", "lead_in": lead.group(1) if lead else ""}
    return cards


def check(queries, cards):
    rows, problems = [], []
    for q in queries:
        card = cards.get(q["pid"])
        if card is None:
            problems.append(f"{q['pid']}: no card in the packet")
            continue
        for style in ("topic", "party"):
            text = q[style]
            n = len(text.split())
            # Rule 2: the party question must name the party, so a party's own name may be copied from the lead-in;
            # the copying limit then applies to the quote alone. The topic question names no party, so it also may
            # not copy the lead-in.
            source = card["quote"] if style == "party" else f"{card['quote']} {card['lead_in']}"
            run = longest_common_run(words(text), words(source))
            overlap = content_overlap(text, f"{card['quote']} {card['lead_in']}")
            rows.append(
                {"pid": q["pid"], "style": style, "words": n, "longest_run": run, "overlap": round(overlap, 3)}
            )
            if not (MIN_WORDS <= n <= MAX_WORDS):
                problems.append(f"{q['pid']} {style}: {n} words (rule 3: {MIN_WORDS} to {MAX_WORDS})")
            if not text.strip().endswith("?"):
                problems.append(f"{q['pid']} {style}: does not end in a question mark")
            if run > MAX_RUN:
                problems.append(f"{q['pid']} {style}: shares a run of {run} consecutive words with the card")
    return rows, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queries", default=str(_HERE / "queries.jsonl"))
    ap.add_argument("--packet", default=str(_HERE / "query_packet.md"))
    ap.add_argument("--json-out")
    args = ap.parse_args()
    queries = [json.loads(line) for line in Path(args.queries).read_text(encoding="utf-8").splitlines() if line.strip()]
    cards = parse_packet(Path(args.packet).read_text(encoding="utf-8"))
    pids = [q["pid"] for q in queries]
    problems = []
    if len(set(pids)) != len(pids):
        problems.append("duplicate pids in queries.jsonl")
    if set(pids) != set(cards):
        problems.append(f"queries and packet disagree: missing {sorted(set(cards) - set(pids))}, extra {sorted(set(pids) - set(cards))}")
    rows, more = check(queries, cards)
    problems += more
    for style in ("topic", "party"):
        ov = [r["overlap"] for r in rows if r["style"] == style]
        print(
            f"{style:5s}: n={len(ov)}  content-word overlap with the card: median {statistics.median(ov):.2f}, "
            f"mean {statistics.mean(ov):.2f}, max {max(ov):.2f}; longest shared run <= {max(r['longest_run'] for r in rows if r['style'] == style)}"
        )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    if problems:
        print("\nPROBLEMS:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("all rules satisfied")


if __name__ == "__main__":
    main()
