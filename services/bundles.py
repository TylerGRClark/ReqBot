"""Bundles: named lists of publications that make up one checklist workbook (for example "a cyberspace unit").

Two sources are merged by bundle name, the user's winning: the starters below and the user's own file `~/.config/reqbot/bundles.json`. A bundle is only a list, so anyone can add or remove a publication. Nothing here decides which programs
apply to a unit; the starters are a place to begin.

Shape:  {"bundles": {"<name>": {"label": str, "note": str, "documents": [{"doc": "<document key>", "title": str}]}}}
"""
import json
import os
import re
from pathlib import Path

STARTERS = {
    "cyberspace_unit": {
        "label": "Cyberspace / communications unit (starter)",
        "note": "A starting point only. Edit it: add or remove publications to match the unit's real programs.",
        "documents": [
            {
                "doc": "afpd_17-1",
                "title": "AFPD 17-1, Information Dominance Governance and Management"
            },
            {
                "doc": "afi17-101",
                "title": "AFI 17-101, Risk Management Framework (RMF) for Air Force IT"
            },
            {
                "doc": "afi17-130",
                "title": "AFI 17-130, Cybersecurity Program Management"
            },
            {
                "doc": "afi17-203",
                "title": "AFI 17-203, Cyber Incident Handling"
            },
            {
                "doc": "afman17-204",
                "title": "AFMAN 17-204, Air Force On-the-Job Training Products for Cyber Support Enlisted Specialty Training"
            },
            {
                "doc": "afman17-2101",
                "title": "AFMAN 17-2101, Long-Haul Communications Management"
            },
            {
                "doc": "dafman17-1203",
                "title": "DAFMAN 17-1203, Information Technology Asset Management (ITAM) and Accountability"
            },
            {
                "doc": "dafman17-1301",
                "title": "DAFMAN 17-1301, Computer Security"
            },
            {
                "doc": "dafman17-1304",
                "title": "DAFMAN 17-1304, Identity, Credential and Access Management (ICAM)"
            },
            {
                "doc": "dafman17-1305",
                "title": "DAFMAN 17-1305, DAF Cyberspace Workforce Management Program"
            }
        ]
    }
}
USER_PATH = Path(os.environ.get("REQBOT_BUNDLES", "~/.config/reqbot/bundles.json")).expanduser()
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    bundles = data.get("bundles") if isinstance(data, dict) else None
    return bundles if isinstance(bundles, dict) else {}


def _clean(bundle: dict) -> dict:
    docs = []
    for entry in bundle.get("documents") or []:
        if isinstance(entry, str):
            entry = {"doc": entry}
        if isinstance(entry, dict) and str(entry.get("doc") or "").strip():
            docs.append({"doc": str(entry["doc"]).strip(), "title": str(entry.get("title") or "").strip()})
    return {"label": str(bundle.get("label") or "").strip(), "note": str(bundle.get("note") or "").strip(), "documents": docs}


def load_bundles(user_path: Path | None = None, starters: dict | None = None) -> dict[str, dict]:
    merged = {name: _clean(b) for name, b in (STARTERS if starters is None else starters).items()}
    for name, bundle in _read(user_path or USER_PATH).items():
        if isinstance(bundle, dict):
            merged[name] = _clean(bundle)
    return merged


def resolve(name: str, *, add: list[str] | None = None, remove: list[str] | None = None, bundles: dict[str, dict] | None = None) -> dict:
    """The named bundle with documents added (by key) and removed (by key); raises KeyError for an unknown name."""
    table = bundles if bundles is not None else load_bundles()
    bundle = table[name]
    docs = [dict(d) for d in bundle["documents"]]
    gone = {k.lower() for k in remove or []}
    docs = [d for d in docs if d["doc"].lower() not in gone]
    have = {d["doc"].lower() for d in docs}
    for key in add or []:
        if key.lower() not in have:
            docs.append({"doc": key, "title": ""})
            have.add(key.lower())
    return {**bundle, "documents": docs}


def save_user_bundle(name: str, label: str, documents: list[str], *, path: Path | None = None, note: str = "") -> Path:
    """Write (or replace) one bundle in the user's file, leaving the user's other bundles as they are."""
    if not _NAME.match(name):
        raise ValueError("a bundle name is lowercase letters, digits, - and _ (at most 48 characters)")
    path = path or USER_PATH
    existing = _read(path)
    existing[name] = {"label": label or name, "note": note, "documents": [{"doc": d, "title": ""} for d in documents]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"bundles": existing}, indent=2) + "\n", encoding="utf-8")
    return path
