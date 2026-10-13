#!/usr/bin/env python3
"""WP-45.7e: write `outputs/frozen_wp457e_code.json`, the manifest the v6 preflight and verdict check (offline; no LLM).

It pins, by sha256 and with paths relative to the repository root, every project file the guarded runner imports (computed by importing
`run_stage_c` and loading one pinned document, so the lazily imported input loaders are included), the declaration, the draw and the pack, and the
two files that pin the input documents. The files that exist only after the labels are committed (the labels and the frozen fresh gold) go under
`sealed_until_c2` with the hashes fixed in docs/PHASE45_WP457E_PLAN.md; a verdict needs them present and equal.

  python3 eval/spike_results/wp_45_7/freeze_v6.py            # writes the manifest (refuses to overwrite without --force)
  python3 eval/spike_results/wp_45_7/freeze_v6.py --check    # recompute the closure and compare it with the committed manifest
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
for _p in (_HERE, _ROOT, _ROOT / "eval/spike_results/wp_45_audit"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import run_stage_c as SC  # noqa: E402

W = "eval/spike_results/wp_45_7/"
MANIFEST = _HERE / "outputs" / "frozen_wp457e_code.json"
PLAN = _ROOT / "docs/PHASE45_WP457E_PLAN.md"
DATA = [W + "outputs/declared_v6.json", W + "outputs/fresh_draw_map.json", W + "outputs/heldout_frozen.json", W + "fresh_pack/pack_a.md",
        W + "fresh_pack/pack_b.md", "eval/spike_results/wp_44/manifest.json"]
SEALED = [W + "outputs/fresh_gold.json", W + "fresh_labels/labels_claude_a.jsonl", W + "fresh_labels/labels_claude_b.jsonl"]


def _sha(path):
    return hashlib.sha256((_ROOT / path).read_bytes()).hexdigest()


def closure():
    """Every project file loaded by importing the runner and loading one pinned input document (the loaders import lazily)."""
    import _inputs

    pinned = _inputs.corpus_inputs("chunks", "extracted")
    SC.RR.load_documents([sorted(pinned)[0]])
    files = set()
    for module in list(sys.modules.values()):
        f = getattr(module, "__file__", None)
        if f and Path(f).resolve().is_relative_to(_ROOT) and "site-packages" not in f and ".venv" not in f and "/tests/" not in f:
            files.add(str(Path(f).resolve().relative_to(_ROOT)))
    return sorted(files)


def sealed_hashes():
    """{path: sha256} for the sealed files, read from the plan (the three hashes fixed there, by file name)."""
    plan = PLAN.read_text(encoding="utf-8")
    out = {}
    for path in SEALED:
        name = Path(path).name
        m = re.search(rf"`{re.escape(name)}`\s+`([0-9a-f]{{64}})`", plan)
        if not m:
            sys.exit(f"the plan does not fix a hash for {name}")
        out[path] = m.group(1)
    return out


def build():
    files = {p: _sha(p) for p in closure() + DATA}
    return {
        "note": ("sha256 (paths relative to the repository root) of everything that defines the WP-45.7e frozen configuration: the import closure of the guarded "
                 "runner, the declaration, the unlabeled draw and pack, and the files that pin the input documents. `sealed_until_c2` lists the files that exist only "
                 "after the labels are committed, with the hashes fixed in docs/PHASE45_WP457E_PLAN.md. The v6 preflight and verdict refuse to proceed if any differs."),
        "files": files, "sealed_until_c2": sealed_hashes(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    text = json.dumps(build(), indent=1, sort_keys=True) + "\n"
    if args.check:
        same = MANIFEST.exists() and MANIFEST.read_text(encoding="utf-8") == text
        print("the committed manifest equals the recomputed one" if same else "DIFFERENT from the committed manifest")
        sys.exit(0 if same else 1)
    if MANIFEST.exists() and not args.force:
        sys.exit("the manifest exists; use --check, or --force to regenerate it on purpose")
    MANIFEST.write_text(text, encoding="utf-8")
    print(f"wrote {MANIFEST.name}: {len(json.loads(text)['files'])} files, {len(json.loads(text)['sealed_until_c2'])} sealed")


if __name__ == "__main__":
    main()
