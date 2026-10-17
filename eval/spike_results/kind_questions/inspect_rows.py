"""Print the full context of selected rows (doc, citation prefix, quote prefix) from the scratch checklist JSON. No model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_rows import load_rows  # noqa: E402

scratch = Path(sys.argv[1])
wants = [w.split("::") for w in sys.argv[2:]]
for r in load_rows(scratch):
    for doc, cit, start in wants:
        if r["_doc"] == doc and (r.get("citation") or "") == cit and r["source_quote"].startswith(start):
            print("=" * 100)
            print(doc, cit, "| applies:", r.get("applies_to"), "| flags:", r.get("item_flags"))
            print("PARENT:", r.get("parent_ref"), (r.get("parent_text") or "")[:700])
            print("HEADING:", r.get("section_heading"), r.get("section_title_path"))
            print("QUOTE:", r["source_quote"])
            print("LIVE:", r.get("audit_question"))
            print("PASSAGE:", (r.get("passage") or "")[:900])
