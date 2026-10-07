#!/usr/bin/env python3
"""WP-45.10 exploratory: find where between two Docling releases a document's default conversion starts to show code items and lost list items.

  python3 bisect_release.py --good 2.94.0 --bad 2.135.0 --document "DODI 5200.01"

Each tested release gets its own virtual environment (~/wp45_10_bis/<version>, system site-packages shared, so the repository's install is untouched) and
`probe_release.py` runs in it. A release is *bad* when its default conversion has any `code` item or fewer than half the good release's list items. The search
assumes the change is monotonic in release order; the result names the first bad release found and the last good one, nothing more.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / "wp45_10_bis"


def releases(lo, hi):
    out = subprocess.run([sys.executable, "-m", "pip", "index", "versions", "docling"], capture_output=True, text=True, timeout=120).stdout
    versions = [v.strip() for v in out.split("Available versions:")[1].splitlines()[0].split(",")]
    key = lambda v: tuple(int(x) for x in v.split("."))  # noqa: E731
    return sorted((v for v in versions if key(lo) <= key(v) <= key(hi) and v.count(".") == 2), key=key)


def profile(version, document):
    venv = ROOT / version
    if not (venv / "bin" / "python").exists():
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True)
        subprocess.run([str(venv / "bin" / "pip"), "install", "-q", f"docling=={version}"], check=True, timeout=1800)
    # TORCHDYNAMO_DISABLE: some releases try to compile a torch kernel, which needs Python.h (python3-dev); this sandbox has none. It affects speed, not output.
    env = {**os.environ, "TORCHDYNAMO_DISABLE": "1"}
    out = subprocess.run([str(venv / "bin" / "python"), str(HERE / "probe_release.py"), document], capture_output=True, text=True, timeout=1800, cwd=HERE, env=env).stdout
    line = next(ln for ln in out.splitlines() if ln.startswith("PROFILE "))
    return json.loads(line[len("PROFILE "):])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--good", required=True)
    ap.add_argument("--bad", required=True)
    ap.add_argument("--document", default="DODI 5200.01")
    args = ap.parse_args()
    ROOT.mkdir(exist_ok=True)
    versions = releases(args.good, args.bad)
    good = profile(args.good, args.document)
    print("good", args.good, good, flush=True)

    def is_bad(p):
        return p["code"] > 0 or p["list_item"] < good["list_item"] / 2

    lo, hi = 0, len(versions) - 1
    results = {args.good: good}
    while hi - lo > 1:
        mid = (lo + hi) // 2
        p = profile(versions[mid], args.document)
        results[versions[mid]] = p
        print(versions[mid], {k: p[k] for k in ("code", "list_item", "text", "tables")}, "BAD" if is_bad(p) else "good", flush=True)
        if is_bad(p):
            hi = mid
        else:
            lo = mid
    print(f"RESULT last good {versions[lo]}, first bad {versions[hi]} (assuming monotonic change)", flush=True)
    (HERE / "bisect_result.json").write_text(json.dumps({"document": args.document, "last_good": versions[lo], "first_bad": versions[hi], "profiles": results}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
