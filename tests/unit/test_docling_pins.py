"""The Docling family is pinned to the set every Phase 45 measurement ran on (WP-45.11).

docling's own requirements on docling-core / docling-parse / docling-ibm-models are open
ranges, so before this pin a fresh install resolved docling-core 2.96.0, docling-ibm-models
3.15.0 and docling-parse 5.11.0 -- not the 2.99.0 / 3.13.0 / 5.7.0 the audit measured.
"""
import re
import tomllib
from pathlib import Path

PINS = {
    "docling": "2.94.0",
    "docling-core": "2.99.0",
    "docling-parse": "5.7.0",
    "docling-ibm-models": "3.13.0",
    # docling-core 2.99.0 requires requests>=2.34.2; the old 2.33.0 pin made pip fall back
    # to docling-core 2.96.0 silently.
    "requests": "2.34.2",
}


def test_docling_family_is_pinned_exactly():
    deps = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text())["project"]["dependencies"]
    found = {m.group(1): m.group(2) for d in deps if (m := re.fullmatch(r"([A-Za-z0-9_.-]+)==([\w.]+)", d.strip()))}
    for name, version in PINS.items():
        assert found.get(name) == version, f"{name} must be pinned ==" + version
