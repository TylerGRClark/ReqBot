"""The logic diagrams in docs/diagrams/ say what the code does today. This guards what a machine can check:
the owner's naming rule (no step letters), that every code-style name a diagram uses (a rejection label, an anchor
status, a hint flag) still exists in the source, and that the index lists exactly the diagram pages. It cannot
check meaning: a diagram still has to be read against the code when the code changes."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS = ROOT / "docs" / "diagrams"
SOURCE_DIRS = ("pipeline", "services", "core", "api", "cli", "mcp_server")

_MERMAID = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
_CODE_NAME = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")  # snake_case: how the code names a label, status or flag
_STEP_LETTER = re.compile(r"\bSteps? [A-F]\b|\bSteps? D\.\d\b")


def _pages() -> list[Path]:
    return sorted(p for p in DIAGRAMS.glob("*.md") if p.name != "README.md")


def _source_text() -> str:
    parts = []
    for name in SOURCE_DIRS:
        for path in sorted((ROOT / name).rglob("*.py")):
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def test_the_diagram_pages_exist():
    assert len(_pages()) >= 10


def test_each_page_has_exactly_one_diagram():
    for page in _pages():
        blocks = _MERMAID.findall(page.read_text(encoding="utf-8"))
        assert len(blocks) == 1, f"{page.name} has {len(blocks)} mermaid blocks"
        assert blocks[0].lstrip().startswith("flowchart"), f"{page.name} is not a flowchart"


def test_no_step_letters_come_back():
    for path in [*_pages(), DIAGRAMS / "README.md"]:
        found = _STEP_LETTER.findall(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name} uses the retired step letters: {found}"


def test_every_code_name_in_a_diagram_exists_in_the_source():
    source = _source_text()
    missing = []
    for page in _pages():
        for block in _MERMAID.findall(page.read_text(encoding="utf-8")):
            for name in sorted(set(_CODE_NAME.findall(block))):
                if not re.search(rf"\b{re.escape(name)}\b", source):
                    missing.append(f"{page.name}: {name}")
    assert not missing, "names in a diagram that the code no longer has: " + "; ".join(missing)


def test_the_index_lists_every_diagram_page():
    index = (DIAGRAMS / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"\]\(([0-9]{2}_[a-z0-9_]+\.md)\)", index))
    assert listed == {p.name for p in _pages()}
