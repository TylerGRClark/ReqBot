# Writing the retrieval-test queries (frozen before any retrieval)

Written once, by Claude, from `query_packet.md` only. Each card is one record. The writer does not see the stem the
pipeline attached to it, any stem verdict, any group, or any retrieval output, and does not open `query_ids.json`
(the id map) or `groups.json` until `queries.jsonl` is frozen and hashed.

For every card write two questions, as one JSON line `{"pid": "P001", "topic": "...", "party": "..."}`:

- **topic**: the question an analyst would ask about the obligation's subject. It does not name the responsible party
  unless the party is part of what the obligation is about.
- **party**: the same subject, asked about a named party (the role in the lead-in, the heading or the quote), as someone
  who knows who is responsible would ask it.

Rules:

1. Ask from the record's **full intended meaning**: the quote plus the lead-in shown on the card, if any.
2. Natural wording; no copying of a run of four or more consecutive words from the quote, in either style, or from the
   lead-in, in the topic style. A party's own name or role title may be copied from the lead-in or heading, however long,
   because the party question has to name it (refined before anything was frozen: the first check flagged party names
   as copying). Ordinary shared terminology is fine and is not leakage; overlap is measured and reported afterwards.
3. One question each, 8 to 30 words, ending in a question mark. No document names, requirement ids or section numbers of the
   source document (a statute citation that is part of the obligation's content is fine).
4. Do not add obligations, conditions or parties that the card does not support.
5. When the heading path and the adjudicated lead-in name different parties (docling mis-nested some headings), the
   lead-in is the truth and the party query follows it.
6. If the card supports no party at all (the lead-in is missing or the subject is a thing, not an actor), write the
   party question as a second, differently worded topic question and set `"no_party": true`. Those records are left out
   of every party-style analysis and still count in the topic-style ones.
7. Queries are never revised after any retrieval has been run. A flaw found later is reported, not fixed.
