"""A closed front-matter heading (SUMMARY OF CHANGES) must not stay the parent of body sections."""
from types import SimpleNamespace

from pipeline.section_parser import _parse_ancestry


def _item(ref, label, text):
    return SimpleNamespace(self_ref=ref, label=label, text=text)


def _doc(items):
    return SimpleNamespace(iterate_items=lambda: [(i, 0) for i in items])


def _paths(items):
    _, item_ancestry, _, _ = _parse_ancestry(_doc(items))
    return {ref: v["section_title_path"] for ref, v in item_ancestry.items()}


def test_numbered_body_heading_closes_summary_of_changes():
    # Reading order puts "1.1." before the "Chapter 1" heading (dafman17-1305).
    paths = _paths([
        _item("#/0", "section_header", "SUMMARY OF CHANGES"),
        _item("#/1", "text", "This document is substantially different."),
        _item("#/2", "section_header", "1.1. Overview."),
        _item("#/3", "text", "1.1.1. The program furthers goals."),
        _item("#/4", "section_header", "Chapter 1"),
    ])
    assert paths["#/1"] == ["SUMMARY OF CHANGES"]
    assert paths["#/3"] == ["1.1. Overview."]


def test_summary_without_numbered_heading_is_unchanged():
    paths = _paths([
        _item("#/0", "section_header", "SUMMARY OF CHANGES"),
        _item("#/1", "text", "Policy language updated."),
        _item("#/2", "section_header", "Chapter 1"),
    ])
    assert paths["#/1"] == ["SUMMARY OF CHANGES"]


def test_ordinary_numbered_nesting_is_unchanged():
    paths = _paths([
        _item("#/0", "section_header", "GENERAL INFORMATION"),
        _item("#/1", "section_header", "1.2. Network Access"),
        _item("#/2", "text", "Body."),
    ])
    assert paths["#/2"] == ["GENERAL INFORMATION", "1.2. Network Access"]
