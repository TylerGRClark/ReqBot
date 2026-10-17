"""No model: gate decisions and decide5() on the stored round-4 answers for the seven documents. Usage: dryrun_round5.py <scratch_held_out>"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import held_out  # noqa: E402
import kind_questions as kq  # noqa: E402
import round5_checks as r5  # noqa: E402

rows = held_out.load_rows(Path(sys.argv[1]), held_out.HELD_OUT)
b = {e["checklist_item_id"]: e for e in json.loads((HERE / "outputs" / "round4_partB_rows.json").read_text())}
for r in rows:
    if kq.classify_wrapper(r)["kind"] != "permission":
        continue
    ok, why = r5.main_verb_gate(r)
    prev = b[r["checklist_item_id"]]
    live = r.get("audit_question") or None
    line = f"{r['_doc'][:10]} {r.get('citation') or '-'} | GATE {'PASS' if ok else 'stop'}: {why[:60]} | {r['source_quote'][:90]!r}"
    if ok:
        ans = {"question": prev.get("model_question_raw"), "limit": prev.get("limit"), "why_null": prev.get("why_null")}
        d = r5.decide5(r, ans, live)
        line += f"\n      -> {d['action']}: {d['rule'][:90]} | live={live and live[:70]!r} | final={d['question'] and d['question'][:90]!r}"
    print(line)
