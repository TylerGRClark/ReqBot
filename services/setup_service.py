"""First-run setup checks: can ReqBot reach what it needs, and is every model it will use installed?

Shared by `reqbot init`, `reqbot init --check` and the setup wizard (docs/WEB_UI_PARITY_PLAN.md, section 9a), so the command line and the web page never keep two copies
of "is this set up". Everything here only reads: it writes no setting, starts nothing and changes nothing on either service.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

import requests

TIMEOUT_SECONDS = 5.0
NOT_AN_ADDRESS = "That is not a web address. Use the form http://host:port"


def clean_url(url: str | None) -> str:
    """The address without a trailing slash. Raises ValueError unless it is a plain http(s) address with a host (no credentials in it)."""
    text = (url or "").strip().rstrip("/")
    parts = urlparse(text)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError(NOT_AN_ADDRESS)
    return text


def installed_names(names: Iterable[str]) -> set[str]:
    """The names Ollama lists, plus each `name:latest` without its tag: a configured `nomic-embed-text` is the installed `nomic-embed-text:latest`."""
    have = {str(n) for n in names if n}
    return have | {n[: -len(":latest")] for n in have if n.endswith(":latest")}


def has_model(name: str, installed: set[str]) -> bool:
    """The rule a queued job's pre-flight check uses, so "the wizard says it is there" and "the job will find it" are the same statement."""
    return bool(name) and (name in installed or f"{name}:latest" in installed)


def _unreachable(service: str, error: Exception) -> str:
    """One fixed sentence per kind of failure. The exception's own text is never passed on: it can carry internal host names or paths, and this reaches a browser."""
    if isinstance(error, requests.Timeout):
        why = f"it did not answer within {int(TIMEOUT_SECONDS)} seconds"
    elif isinstance(error, requests.ConnectionError):
        why = "the connection was refused or the address could not be found"
    else:
        why = "the request could not be made"
    return f"Could not reach {service} there: {why}."


def test_ollama(url: str) -> tuple[bool, str, list[str]]:
    """Returns (reachable, one plain sentence, the installed model names)."""
    try:
        base = clean_url(url)
    except ValueError:
        return False, NOT_AN_ADDRESS, []
    try:
        resp = requests.get(f"{base}/api/tags", timeout=TIMEOUT_SECONDS, allow_redirects=False)
        if resp.status_code >= 400:
            return False, f"Ollama answered with an error (HTTP {resp.status_code}) at that address.", []
        names = [str(m["name"]) for m in resp.json().get("models", []) if isinstance(m, dict) and "name" in m]
    except requests.RequestException as e:
        return False, _unreachable("Ollama", e), []
    except (ValueError, KeyError, AttributeError):
        return False, "Something answered there, but not like Ollama (the reply was not a list of models).", []
    count = len(names)
    return True, f"OK ({count} model{'s' if count != 1 else ''} found)", names


def test_qdrant(url: str) -> tuple[bool, str]:
    """Returns (reachable, one plain sentence)."""
    try:
        base = clean_url(url)
    except ValueError:
        return False, NOT_AN_ADDRESS
    try:
        resp = requests.get(f"{base}/collections", timeout=TIMEOUT_SECONDS, allow_redirects=False)
        if resp.status_code >= 400:
            return False, f"Qdrant answered with an error (HTTP {resp.status_code}) at that address."
        count = len(resp.json().get("result", {}).get("collections", []))
    except requests.RequestException as e:
        return False, _unreachable("Qdrant", e)
    except (ValueError, KeyError, AttributeError):
        return False, "Something answered there, but not like Qdrant (the reply was not a list of collections)."
    return True, f"OK ({count} collection{'s' if count != 1 else ''})"


def check_folder(path: str | Path) -> dict:
    """Does the documents folder exist and can ReqBot write in it? A folder that does not exist yet is fine when its parent is writable (ReqBot creates it)."""
    import os

    folder = Path(path).expanduser()
    if folder.is_dir():
        ok = os.access(folder, os.W_OK | os.X_OK)
        return {"path": str(folder), "exists": True, "writable": ok,
                "message": "OK" if ok else "The folder exists but ReqBot cannot write in it. Check its permissions."}
    parent = folder.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    ok = parent.is_dir() and os.access(parent, os.W_OK | os.X_OK)
    return {"path": str(folder), "exists": False, "writable": ok,
            "message": "It will be created when the first document is added." if ok else "The folder does not exist and cannot be created there. Check the path and permissions."}


def model_roles(values: dict, questions_model: str) -> list[dict]:
    """Every model ReqBot will ask Ollama for, with what it is for and whether setup is complete without it.

    `values` holds embedding_model, default_model, extraction_model, rewrite_model, synthesis_model and synthesis_backend (a role left unset follows default_model).
    """
    default = values.get("default_model") or ""
    roles = [
        {"role": "embedding", "name": values.get("embedding_model") or "", "needed_for": "searching and adding documents", "required": True},
        {"role": "extraction", "name": values.get("extraction_model") or default, "needed_for": "finding the requirements when a document is added", "required": True},
        {"role": "rewrite", "name": values.get("rewrite_model") or default, "needed_for": "understanding a question in Ask", "required": False},
        {"role": "questions", "name": questions_model, "needed_for": "writing draft audit questions", "required": False},
    ]
    if (values.get("synthesis_backend") or "local") == "local":
        roles.append({"role": "synthesis", "name": values.get("synthesis_model") or "", "needed_for": "written answers in Ask", "required": False})
    return roles


def run_check(values: dict, processed_dir: str | Path, questions_model: str) -> dict:
    """The whole picture for the values given (the config as it would be): both services, each model, the documents folder, and whether it is ready to use.

    `ready` means the two services answer, every required model is installed and the folder is writable; an optional model that is missing only costs its own feature.
    """
    ollama_url = values.get("ollama_url") or ""
    qdrant_url = values.get("qdrant_url") or ""
    ok_o, msg_o, names = test_ollama(ollama_url)
    ok_q, msg_q = test_qdrant(qdrant_url)
    installed = installed_names(names)
    models = []
    for role in model_roles(values, questions_model):
        present = has_model(role["name"], installed) if ok_o else None  # unknown while the model machine cannot be asked
        models.append({**role, "installed": present})
    folder = check_folder(processed_dir)
    required_ok = all(m["installed"] for m in models if m["required"])
    return {
        "ollama": {"url": ollama_url, "ok": ok_o, "message": msg_o, "models": names},
        "qdrant": {"url": qdrant_url, "ok": ok_q, "message": msg_q},
        "models": models,
        "folder": folder,
        "ready": bool(ok_o and ok_q and required_ok and folder["writable"]),
    }
