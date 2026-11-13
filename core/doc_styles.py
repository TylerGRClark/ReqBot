"""Document styles: how one kind of document is laid out and numbered.

A document style is a small data file in doc_styles/<name>.json. It is separate from a domain
profile (profiles/*.json, core/profiles.py): the profile says what the document is ABOUT (duty
wording, sections to skip); the style says how it is LAID OUT (how its paragraphs are numbered,
which page lines repeat). One document has both.

The shared code owns all logic. A style holds only data and named choices, never its own code, so
a fix made once reaches every style. The built-in "general" style is today's behavior: it changes
nothing, and it is what a document gets when no style is chosen.

Callers never read the files directly; use load_style().
"""

import copy
import json
from pathlib import Path

from core.reference_grammar import parse_grammar

_STYLES_DIR = Path(__file__).resolve().parent.parent / "doc_styles"

DEFAULT_STYLE = "general"

# Files in doc_styles/ that are data about styles, not styles: not listed, and not loadable by name.
_NOT_STYLES = frozenset({"detection"})

REQUIRED_FIELDS = frozenset({"name", "version", "reference_grammar"})
OPTIONAL_FIELDS = frozenset({"description"})
_ALL_KNOWN_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS

_OPTIONAL_DEFAULTS: dict = {"description": ""}


def _validate(data: dict) -> None:
    """Raise ValueError if any field has a wrong type or value."""
    for field in ("name", "version", "description"):
        if field in data and not isinstance(data[field], str):
            raise ValueError(f"Style field '{field}' must be a string, got {type(data[field]).__name__}")
    for field in ("name", "version"):
        if field in data and not data[field].strip():
            raise ValueError(f"Style field '{field}' must not be empty")
    grammar = data.get("reference_grammar")
    if grammar is not None:
        # null means "no document-type numbering rules" (today's behavior); an object is checked
        # by the shared grammar itself, so a typo is an error and cannot silently do nothing.
        parse_grammar(grammar)


def load_style(name: str = DEFAULT_STYLE) -> dict:
    """Load and validate a named style from doc_styles/<name>.json.

    Raises:
        FileNotFoundError: the style file does not exist
        ValueError:        path separators in the name, non-object JSON, unknown or missing
                           fields, type errors, or a name that does not match the file
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Style name must be a non-empty string")
    if "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Style name must not contain path separators: '{name}'")
    if name in _NOT_STYLES:
        raise FileNotFoundError(f"Document style not found: '{name}' (that file holds the rules for choosing a style, not a style)")

    path = _STYLES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Document style not found: '{name}' (looked for {path.name} in doc_styles/)")

    with open(path, encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Document style '{name}' is not valid JSON: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"Document style '{name}' must be a JSON object, got {type(raw).__name__}")

    unknown = set(raw) - _ALL_KNOWN_FIELDS
    if unknown:
        raise ValueError(f"Unknown document style fields: {sorted(unknown)}")
    missing = REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Missing required document style fields: {sorted(missing)}")

    _validate(raw)
    if raw["name"] != name:
        raise ValueError(f"Style name mismatch: file is '{name}.json' but name field is '{raw['name']}'")

    return {**copy.deepcopy(_OPTIONAL_DEFAULTS), **raw}


def default_style() -> dict:
    """The general style: today's behavior. Used when no style is chosen."""
    return load_style(DEFAULT_STYLE)


def list_styles() -> list[str]:
    """Sorted names of every style found in doc_styles/."""
    return sorted(p.stem for p in _STYLES_DIR.glob("*.json") if p.is_file() and p.stem not in _NOT_STYLES)


def style_record(style: dict, requested: str | None = None, detection=None) -> dict:
    """The description of a style written into a run's stats: which style and which version.

    When the style was chosen automatically, `requested` is "auto" and `detection` is the core.style_detection.Detection that chose it, so the run records what was asked for,
    what was chosen, and why. A style named by the user records requested = its name and no detection."""
    rec = {"name": style["name"], "version": style["version"]}
    if requested is not None:
        rec["requested"] = requested
    if detection is not None:
        rec.update(detection.as_record())
    return rec
