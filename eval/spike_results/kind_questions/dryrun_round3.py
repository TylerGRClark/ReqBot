"""No model: apply the round-3 deterministic checks to the round-2 questions (new boundary questions) and list every rejection."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import round3_checks as r3  # noqa: E402

rows = json.loads((HERE / "outputs" / "round2_rows.json").read_text())
for e in rows:
    if e["new_question"] and e["new_question"] != e["live_question"] and "boundary" in (e["rule"] or ""):
        why = r3.rejection(e["new_question"], e["source_quote"], e.get("limit"))
        print(("REJECT" if why else "ok    "), e["doc"][:8], e["citation"], "|", why or "", "|", e["new_question"][:80])
