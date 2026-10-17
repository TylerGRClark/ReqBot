"""Round 2: score every `unknown` row of the library documents with the frozen S2 prompt and record the time per document. Rules are in README.md."""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_second_opinion as R  # noqa: E402
from services import checklist_service as cs  # noqa: E402
from services import requirement_kind as rk  # noqa: E402

PROC = Path.home() / "documents" / "processed"
DOCS = ["afpd_17-1", "afi10-2402", "afi13-550", "afi17-101", "afi17-130", "afi17-203", "afi90-802", "afman17-204", "afman17-2101", "dafman17-1203", "dafman17-1301", "dafman17-1304",
        "dafman17-1305", "dafpam90-803", "dafi36-2903", "CJCSI 6510.02G", "DODI 5200.01", "DODI 5200.44", "DODI 5200.48", "DODI 8410.03", "DODI 8551.01", "NIST.SP.800-125"]
THRESHOLD = 7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True, help="local rows json from round 1 (supplies the worked examples)")
    ap.add_argument("--ollama-url", required=True)
    args = ap.parse_args()
    rows = json.loads(Path(args.rows).expanduser().read_text(encoding="utf-8"))
    examples = R.pick_examples(rows)
    out_path = R.OUT / "scores_all.json"
    done = json.loads(out_path.read_text()) if out_path.exists() else {"scores": {}, "timing": {}}
    for doc in DOCS:
        if doc in done["timing"]:
            continue
        items = [i for i in cs.generate(PROC, doc, "cybersecurity")["items"] if (i.get("source_quote") or "").strip() and rk.classify(i)["kind"] == "unknown"]
        start = time.monotonic()
        errors = 0
        for it in items:
            row = {"quote": it["source_quote"], "applies": it.get("applies_to") or "", "parent": it.get("parent_text") or "", "passage": it.get("passage") or ""}
            score, err = R.ask(R.build(row, examples), args.ollama_url)
            done["scores"][it["checklist_item_id"]] = {"doc": doc, "score": score}
            errors += bool(err)
        done["timing"][doc] = {"unknown_rows": len(items), "seconds": round(time.monotonic() - start, 1), "errors": errors}
        out_path.write_text(json.dumps(done), encoding="utf-8")
        print(f"{doc}: {len(items)} rows, {done['timing'][doc]['seconds']}s, {errors} errors", flush=True)
    print("done; threshold", THRESHOLD)


if __name__ == "__main__":
    sys.exit(main())
