#!/usr/bin/env python3
"""PREREG12 probe: what would a longer context-index cut change IF the chunk vectors were searched?

Production never searches grc_context (core/ask.py only fetches a chunk by id), so this is NOT the search path;
it only measures the cut itself. Every chunk of the newest run folders is embedded (dense, nomic-embed-text) at
three cuts (1500 chars, 3000 chars, full text) and each gold question (raw text, no rewrite, no HyDE) is ranked
against all chunks. Gold chunk = chunk holding a remapped gold row. In memory only; writes nothing to Qdrant.
"""
import argparse
import glob
import json
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT))
from idx_cut_gold import newest_normalized  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=str(Path(__file__).with_name("PREREG12_gold_remapped.jsonl")))
    ap.add_argument("--processed", default=str(Path.home() / "documents" / "processed"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import numpy as np
    import ollama
    from core import config
    cfg = config.load()
    cl = ollama.Client(host=cfg.ollama_url)
    gold = [json.loads(l) for l in open(a.gold) if l.strip()]
    gold_ids = {i for g in gold for i in g["relevant_requirement_ids"]}
    chunks, goldrows = [], {}
    for key, (d, f) in sorted(newest_normalized(a.processed).items()):
        cf = glob.glob(d + "/*_chunks.jsonl")[0]
        base = len(chunks)
        idx = {}
        for l in open(cf, encoding="utf-8"):
            c = json.loads(l)
            idx[c["chunk_id"]] = len(chunks)
            chunks.append({"doc": key, "chunk_id": c["chunk_id"], "text": c["text"]})
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            if r["requirement_id"] in gold_ids and r.get("chunk_id") in idx:
                goldrows[r["requirement_id"]] = (idx[r["chunk_id"]], r["source_quote"])
    lens = [len(c["text"]) for c in chunks]
    print("chunks", len(chunks), "over1500", sum(1 for x in lens if x > 1500), "over3000", sum(1 for x in lens if x > 3000))

    def embed_all(cut):
        t0 = time.time()
        out = []
        texts = [c["text"][:cut] if cut else c["text"] for c in chunks]
        for i in range(0, len(texts), 16):
            out += cl.embed(model="nomic-embed-text", input=texts[i:i + 16]).embeddings
        return np.array(out, dtype="float32"), time.time() - t0

    res = {"n_chunks": len(chunks), "over1500": sum(1 for x in lens if x > 1500), "over3000": sum(1 for x in lens if x > 3000), "arms": {}}
    scored = [g for g in gold if g["shape"] != "zero" and g["relevant_requirement_ids"]]
    gchunks = {g["query_id"]: {goldrows[i][0] for i in g["relevant_requirement_ids"] if i in goldrows} for g in scored}
    # share of scored queries whose gold chunk is longer than 1500 chars / whose quote ends past the 1500 cut
    def quote_past(i):
        ci, q = goldrows[i]
        t = chunks[ci]["text"]
        m = re.search(r"\s+".join(re.escape(w) for w in q.split()), t)
        return bool(m and m.end() > 1500)
    res["queries_scored"] = len(scored)
    res["queries_any_gold_chunk_over1500"] = sum(1 for g in scored if any(lens[c] > 1500 for c in gchunks[g["query_id"]]))
    res["queries_all_gold_chunks_over1500"] = sum(1 for g in scored if gchunks[g["query_id"]] and all(lens[c] > 1500 for c in gchunks[g["query_id"]]))
    res["queries_any_gold_quote_past_1500"] = sum(1 for g in scored if any(quote_past(i) for i in g["relevant_requirement_ids"] if i in goldrows))
    res["gold_rows_quote_past_1500"] = sum(1 for i in goldrows if quote_past(i))
    res["gold_rows"] = len(goldrows)
    qv = {g["query_id"]: cl.embed(model="nomic-embed-text", input=g["query"]).embeddings[0] for g in scored}
    for name, cut in (("cut1500", 1500), ("cut3000", 3000), ("full", 0)):
        M, secs = embed_all(cut)
        Mn = M / np.linalg.norm(M, axis=1, keepdims=True)
        per = {}
        for g in scored:
            q = np.array(qv[g["query_id"]], dtype="float32")
            q /= np.linalg.norm(q)
            order = np.argsort(-(Mn @ q))
            rank = {int(c): r + 1 for r, c in enumerate(order)}
            best = min((rank[c] for c in gchunks[g["query_id"]]), default=None)
            per[g["query_id"]] = {"shape": g["shape"], "first_gold_chunk_rank": best}
        ranks = [v["first_gold_chunk_rank"] for v in per.values() if v["first_gold_chunk_rank"]]
        res["arms"][name] = {"embed_seconds": round(secs, 1), "mrr": round(sum(1 / r for r in ranks) / len(scored), 4),
                             "hit@5": round(sum(1 for r in ranks if r <= 5) / len(scored), 4),
                             "hit@10": round(sum(1 for r in ranks if r <= 10) / len(scored), 4), "per_query": per}
        print(name, {k: v for k, v in res["arms"][name].items() if k != "per_query"})
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
