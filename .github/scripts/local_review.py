#!/usr/bin/env python3
"""Advisory pre-push review of this branch by a local Ollama model.

It sends the model the same instructions, answer format and inputs (architecture brief, the
diff and the full changed files) that the Gemini CI reviewer gets (gemini_review.py), so a local
pass and the pushed-candidate review look at the same material. In a backtest on 108 past
reviewed commits that prompt found about 7% of Codex's later-fixed findings with the default
model (and the previous, shorter prompt about 1%): a cheap smoke check, not a substitute.

Run it before pushing:  python3 .github/scripts/local_review.py [--base origin/main] [paths...]

It is never a gate: it exits 0 whatever it finds (2 only for bad usage), so it cannot block
a push, and a clean result is not approval. A small local model has false alarms and blind
spots; CI, Codex and Gemini still review the pushed candidate. Nothing leaves this machine
except to the Ollama server named in ReqBot's config (core/config.py).

Untracked files are never read. Large data files are excluded, and a diff over the size
budget is refused rather than truncated, because a silently cut-off diff reads as "no findings".
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemini_review as _gemini  # noqa: E402  (the CI reviewer's prompt and schema; its SDK imports are lazy)

BRIEF_PATH = _ROOT / ".github" / "review_context.md"
EXCLUDES = (":(exclude)*.jsonl", ":(exclude)*package-lock.json", ":(exclude)eval/spike_results")
MAX_DIFF_BYTES = 32_000  # ~11k tokens; with the context files below this fits NUM_CTX with room for the answer
MAX_CONTEXT_BYTES = 60_000  # full changed files sent beside the diff, as the CI reviewer does
NUM_CTX = 32_768
NUM_PREDICT = 4_096
TIMEOUT_SECONDS = 600
SEVERITIES = ("Critical", "High", "Medium", "Low")
SYSTEM = _gemini.SYSTEM_INSTRUCTION
REVIEW_SCHEMA = _gemini.REVIEW_SCHEMA
FALLBACK_MODEL = "llama3.1:8b-instruct-q4_K_M"


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, encoding="utf-8", errors="replace",
        check=True, cwd=_ROOT,
    ).stdout


def base_ref(requested):
    if requested:
        return requested
    try:
        git("rev-parse", "--verify", "-q", "origin/main")
        return "origin/main"
    except subprocess.CalledProcessError:
        return "main"


def collect_diff(base, paths):
    """Tracked changes (committed, staged and unstaged) since the merge base."""
    merge_base = git("merge-base", base, "HEAD").strip()
    flags = ["--no-ext-diff", "--no-textconv", "--no-renames"]
    spec = ["--", *(paths or ["."]), *EXCLUDES]
    names = git("diff", "--name-only", "-z", *flags, merge_base, *spec).split("\0")
    return git("diff", *flags, merge_base, *spec), {name for name in names if name}


def reqbot_defaults():
    """Ollama URL and model from ReqBot's own config layers (defaults, file, env).

    The model is default_model (the 8B), not synthesis_model: it was the fastest and no worse at
    finding what Codex later found (see the module docstring).
    """
    try:
        from core import config

        cfg = config.load()
        return cfg.ollama_url.rstrip("/"), cfg.default_model
    except Exception:
        return "http://localhost:11434", FALLBACK_MODEL


def collect_context(changed):
    """Full text of the changed files as they are on disk now, within MAX_CONTEXT_BYTES.

    Returns (files, omitted); a file that is deleted, binary or too large for what is left of
    the budget is left out and named in `omitted`.
    """
    files, omitted, remaining = [], [], MAX_CONTEXT_BYTES
    for path in sorted(changed):
        try:
            blob = (_ROOT / path).read_bytes()
        except OSError:
            continue  # deleted (its removed text is in the diff) or unreadable
        if b"\0" in blob or len(blob) > remaining:
            omitted.append(path)
            continue
        files.append({"path": path, "text": blob.decode("utf-8", errors="replace")})
        remaining -= len(blob)
    return files, omitted


def build_messages(diff, brief, context=()):
    user = json.dumps({"approved_architecture": brief, "diff": diff, "surrounding_files": list(context)})
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def chat(url, model, messages):
    body = json.dumps({
        "model": model, "messages": messages, "stream": False, "format": REVIEW_SCHEMA,
        "options": {"num_ctx": NUM_CTX, "temperature": 0, "num_predict": NUM_PREDICT},
    }).encode()
    request = urllib.request.Request(
        f"{url}/api/chat", data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def parse_review(content, changed):
    """(summary, findings, dropped) or None. Findings that do not cite a changed file are dropped."""
    try:
        data = json.loads(content)
        summary, raw = data["summary"], data["findings"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(summary, str) or not isinstance(raw, list):
        return None
    kept, dropped = [], 0
    for finding in raw:
        ok = (
            isinstance(finding, dict)
            and finding.get("severity") in SEVERITIES
            and isinstance(finding.get("path"), str) and finding["path"] in changed
            and type(finding.get("line")) is int and finding["line"] >= 1
            and all(isinstance(finding.get(k), str) and finding[k].strip()
                    for k in ("title", "explanation"))
        )
        if ok:
            kept.append(finding)
        else:
            dropped += 1
    kept.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    return summary, kept, dropped


def show(status, reason="", summary="", findings=(), dropped=0):
    print(f"Local review: {status}" + (f" - {reason}" if reason else ""))
    if summary:
        print(f"\n{summary}")
    if findings:
        print(f"\nFindings ({len(findings)}):")
        for f in findings:
            print(f"- [{f['severity']}] {f['path']}:{f['line']} - {f['title']}\n    {f['explanation']}")
    elif status == "complete":
        print("\nNo findings. That is not approval.")
    if dropped:
        print(f"\n{dropped} finding(s) dropped: they did not cite a changed file.")
    print("\nAdvisory only: a local model has false alarms and blind spots; CI and the "
          "pushed-candidate reviewers still apply.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Advisory local pre-push review (Ollama).")
    parser.add_argument("paths", nargs="*", help="limit the review to these paths")
    parser.add_argument("--base", help="branch to compare against (default: origin/main, else main)")
    parser.add_argument("--model", help="Ollama model (default: default_model from ReqBot config)")
    parser.add_argument("--ollama-url", help="Ollama server (default: ollama_url from ReqBot config)")
    args = parser.parse_args(argv)
    url, model = reqbot_defaults()
    url = args.ollama_url.rstrip("/") if args.ollama_url else url
    model = args.model or model

    try:
        base = base_ref(args.base)
        diff, changed = collect_diff(base, args.paths)
    except subprocess.CalledProcessError as err:
        return show("unavailable", f"git could not compute the diff: {(err.stderr or '').strip()[:200]}")
    if not diff.strip():
        print(f"Nothing to review against {base}. (New files are only seen once git knows "
              "about them: git add -N <file>.)")
        return 0
    size = len(diff.encode("utf-8"))
    if size > MAX_DIFF_BYTES:
        return show("incomplete", f"diff is {size // 1000} KB, over the {MAX_DIFF_BYTES // 1000} KB budget "
                    "for a reliable local review; pass paths to review a smaller part")

    brief = BRIEF_PATH.read_text() if BRIEF_PATH.exists() else ""
    context, omitted = collect_context(changed)
    print(f"Reviewing {len(changed)} changed file(s), {size // 1000 or 1} KB, against {base} with {model}...")
    try:
        reply = chat(url, model, build_messages(diff, brief, context))
    except urllib.error.HTTPError as err:
        hint = " - is the model pulled?" if err.code == 404 else ""
        return show("unavailable", f"Ollama answered HTTP {err.code}{hint}")
    except (urllib.error.URLError, OSError, ValueError) as err:
        return show("unavailable", f"could not get a reply from Ollama ({type(err).__name__})")

    # Never trust the reply's shape: an advisory tool that must not block a push cannot crash.
    reply = reply if isinstance(reply, dict) else {}
    message = reply.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    parsed = parse_review(content if isinstance(content, str) else "", changed)
    if parsed is None:
        return show("incomplete", f"the model did not return a valid review (finish: {reply.get('done_reason')})")
    summary, findings, dropped = parsed
    problems = []
    if reply.get("done_reason") != "stop":
        problems.append(f"the answer was cut off (finish: {reply.get('done_reason')})")
    # Ollama shifts the window and keeps generating (still "stop") when prompt plus answer
    # overflow it, silently dropping the start of the prompt; count generated tokens too.
    counts = [reply.get(k) for k in ("prompt_eval_count", "eval_count")]
    if not all(type(c) is int and c >= 0 for c in counts):
        problems.append("Ollama did not report token counts, so context use could not be checked")
    elif sum(counts) >= NUM_CTX - 64:
        problems.append("the prompt and answer filled the context window, so part of the diff may have been dropped")
    if omitted:
        problems.append("surrounding source omitted (binary or over budget): " + ", ".join(omitted))
    status = "incomplete" if problems else "complete"
    return show(status, "; ".join(problems), summary, findings, dropped)


if __name__ == "__main__":
    sys.exit(main())
