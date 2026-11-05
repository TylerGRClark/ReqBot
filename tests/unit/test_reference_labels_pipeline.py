"""pipeline/reference_labels.py: the step that reads the PDF reader's items and writes the labels file beside the document."""
import json
from types import SimpleNamespace

import pytest

from core import reference_lookup as RL
from core.doc_styles import load_style
from pipeline import reference_labels


class FakeDoc:
    """Stands in for the DoclingDocument: iterate_items() yields (item, level) in reading order."""

    def __init__(self, items):
        self._items = items

    def iterate_items(self):
        return iter((i, 0) for i in self._items)


def item(label, text, page, marker=None):
    return SimpleNamespace(label=label, text=text, marker=marker, prov=[SimpleNamespace(page_no=page)])


QUOTE = "The Director shall maintain the central repository of service level agreements."
DOC = FakeDoc([
    item("DocItemLabel.SECTION_HEADER", "ENCLOSURE 2", 7),
    item("DocItemLabel.LIST_ITEM", "DIRECTOR, DISA.", 7, marker="2."),
    item("DocItemLabel.LIST_ITEM", QUOTE, 7, marker="b."),
    item("DocItemLabel.PICTURE", "", 7),
    SimpleNamespace(label="DocItemLabel.TEXT", text="No page information.", marker=None, prov=[]),
])


def test_the_readers_items_become_grammar_items():
    items = reference_labels.items_from_docling(DOC)
    assert [i["kind"] for i in items] == ["heading", "list_item", "list_item", "other", "text"]
    assert items[2] == {"kind": "list_item", "text": QUOTE, "marker": "b.", "page": 7}
    assert items[4]["page"] is None


def test_the_labels_file_is_written_beside_the_document(tmp_path):
    path = reference_labels.write_for_document(DOC, load_style("outline-dod"), tmp_path, "DODI 8410.03")
    assert path == tmp_path / "DODI 8410.03_references.json"
    lookup = RL.load_lookup(tmp_path, "DODI 8410.03")
    assert lookup.find(QUOTE, 7, 7) == "Encl 2, 2.b"
    assert json.loads(path.read_text(encoding="utf-8"))["style"] == {"name": "outline-dod", "version": "1"}


def test_a_style_without_a_grammar_cannot_label(tmp_path):
    with pytest.raises(ValueError, match="no reference grammar"):
        reference_labels.write_for_document(DOC, load_style("general"), tmp_path, "doc")
