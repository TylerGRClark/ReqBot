#!/usr/bin/env python3
"""WP-45.10 exploratory: print the label profile of one document's default conversion as JSON, for the release this interpreter has (used by bisect_release.py)."""

import collections
import json
import sys
import warnings

import common

warnings.filterwarnings("ignore")


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "DODI 5200.01"
    from docling.document_converter import DocumentConverter
    doc = DocumentConverter().convert(str(common.pdf_path(name))).document
    counts = collections.Counter(str(t.label.value) for t in doc.texts)
    print("PROFILE " + json.dumps({"document": name, "versions": common.versions(), "code": counts.get("code", 0), "list_item": counts.get("list_item", 0),
                                   "text": counts.get("text", 0), "tables": len(doc.tables), "items": len(doc.texts)}), flush=True)


if __name__ == "__main__":
    main()
