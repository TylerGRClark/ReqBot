"""Machine-readable progress lines for long commands (docs/WEB_UI_PARITY_PLAN.md, stage 3).

Off unless `enable()` is called, which `reqbot ingest --progress-json` does. When on, `emit()` prints one JSON object per line on stdout, for example
`{"step":"finding","done":120,"total":427}`; the job runner reads those lines instead of scraping the prose log (which goes to stderr). When off it prints nothing, so the
output of a command is byte-for-byte what it was before this module existed.

Steps used by ingest, in order: reading, chunking, finding (done/total chunks), checking, totals, indexing (done/total requirements), indexing-context, done.
"""
import json
import sys

_enabled = False


def enable() -> None:
    global _enabled
    _enabled = True


def disable() -> None:
    global _enabled
    _enabled = False


def enabled() -> bool:
    return _enabled


def emit(step: str, done: int | None = None, total: int | None = None) -> None:
    """Print one progress line when progress output is on; do nothing otherwise."""
    if not _enabled:
        return
    line: dict = {"step": step}
    if done is not None:
        line["done"] = int(done)
    if total is not None:
        line["total"] = int(total)
    sys.stdout.write(json.dumps(line, separators=(",", ":")) + "\n")
    sys.stdout.flush()
