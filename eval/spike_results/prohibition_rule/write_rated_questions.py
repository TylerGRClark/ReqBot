"""Write the questions the owner rated into the draft-question sidecars, so what he rated is what the checklist shows (no new model call, no new wording).

Run after the narrowed pattern in services/audit_questions.py is in the checkout:
    PYTHONPATH=. python3 eval/spike_results/prohibition_rule/write_rated_questions.py            # dry run: works on a temp copy, writes nothing real
    PYTHONPATH=. python3 eval/spike_results/prohibition_rule/write_rated_questions.py --write    # backs the sidecars up first, then writes

A row is written only when its prompt today is byte-identical to the prompt the experiment used (the rule off), so the stored input hash is the one `reqbot questions` computes and the
record is reused. Rows where the rule still fires keep their stored question.
"""
import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from services import audit_questions as aq
from services import checklist_service as cs

HERE = Path(__file__).resolve().parent
PROC = Path.home() / "documents" / "processed"
BACKUP = Path.home() / "reqbot-work" / "backups" / "audit_questions_before_prohibition_rule_2026-10-11"
SOURCE = "prohibition_rule experiment run 2026-10-11, rated by the owner"


def prompt_rule_off(item: dict) -> str:
    parent = f"{item.get('parent_ref') or ''} {item.get('parent_text') or ''}".strip()
    return aq.PROMPT.format(applies=item.get("applies_to") or "(none)", parent=parent or "(none)", quote=item.get("source_quote") or "", passage=(item.get("passage") or "")[:1500])


def no_model(prompt: str) -> str:
    raise AssertionError("a model call was needed: a stored question did not match its row's prompt")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write the real sidecars (after backing them up); default is a dry run on a temp copy")
    args = ap.parse_args()
    runs = [json.loads(line) for line in (HERE / "outputs" / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_doc: dict[str, list[dict]] = {}
    for r in runs:
        by_doc.setdefault(r["doc"], []).append(r)
    work = Path(tempfile.mkdtemp(prefix="prohibition_sidecars_"))
    totals = {"written": 0, "rule_still_fires": 0, "errored_in_run": 0, "skipped_by_code": 0, "missing_row": 0, "prompt_differs": 0, "docs": 0}
    to_write: list[tuple[Path, dict]] = []
    for key, recs in sorted(by_doc.items()):
        env = cs.generate(PROC, key, "cybersecurity")
        items = {it["checklist_item_id"]: it for it in env["items"]}
        req_path = cs.requirements_path(PROC, key)
        side = aq.sidecar_path(req_path)
        existing = aq.load(side)
        out = dict(existing)
        changed = 0
        for r in recs:
            it = items.get(r["id"])
            if it is None:
                totals["missing_row"] += 1
                continue
            if r["errors"]:
                totals["errored_in_run"] += 1
                continue
            if aq.skipped_because(it):
                totals["skipped_by_code"] += 1
                continue
            if aq.PROHIBITION.search(it.get("source_quote") or ""):
                totals["rule_still_fires"] += 1
                continue
            if prompt_rule_off(it) != aq.build_prompt(it):
                totals["prompt_differs"] += 1
                continue
            q = r["new"] if not aq.no_question(r["new"]) else None
            out[r["id"]] = {"checklist_item_id": r["id"], "question": q, "skipped_because": [], "unverified_terms": aq.unverified_terms(q, aq.row_material(it)) if q else [],
                            "model": aq.MODEL, "input_hash": aq.input_hash(aq.build_prompt(it), aq.MODEL), "generated_at": datetime.now(timezone.utc).isoformat(), "source": SOURCE}
            changed += 1
        totals["written"] += changed
        totals["docs"] += bool(changed)
        target = work / side.name
        aq.write(target, out)
        # every row of the document must now be answered from the sidecar: a model call would raise
        counts = aq.draft_questions(env["items"], target, call=no_model)
        assert counts["errors"] == 0, (key, counts)
        to_write.append((side, {"key": key, "changed": changed, "temp": target}))
    print(json.dumps(totals, indent=2))
    if not args.write:
        print(f"dry run: nothing written to the real sidecars (temp copies in {work})")
        return 0
    BACKUP.mkdir(parents=True, exist_ok=True)
    for side, info in to_write:
        if side.exists():
            shutil.copy2(side, BACKUP / f"{side.parent.name}__{side.name}")
        if info["changed"]:
            shutil.copy2(info["temp"], side)
    print(f"sidecars written; previous versions in {BACKUP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
