import os
import shutil
from pathlib import Path

import pytest

from ask_the_docs.parse import parse_file

FIXTURES = Path(__file__).parent.parent / "fixtures" / "docs"


def fixture_lines(name: str, start: int, end: int) -> list[str]:
    """Return the fixture's 1-based, inclusive line range."""
    return (FIXTURES / name).read_text().split("\n")[start - 1 : end]


def test_guide_sections_in_order():
    parsed = parse_file(FIXTURES, "guide.md")

    summary = [
        (s.ordinal, s.anchor, s.heading, s.level, s.start_line, s.end_line)
        for s in parsed.sections
    ]
    assert summary == [
        (0, "", "Widget Guide", 0, 6, 6),
        (1, "widget-guide", "Widget Guide", 1, 8, 10),
        (2, "install", "Install", 2, 12, 14),
        (3, "requirements", "Requirements", 3, 16, 18),
        (4, "usage", "Usage", 2, 20, 27),
        (5, "setext-heading", "Setext Heading", 2, 29, 32),
        (6, "usage-1", "Usage", 2, 34, 36),
    ]


def test_heading_trails():
    sections = parse_file(FIXTURES, "guide.md").sections

    assert [s.heading_trail for s in sections] == [
        (),
        ("Widget Guide",),
        ("Widget Guide", "Install"),
        ("Widget Guide", "Install", "Requirements"),
        ("Widget Guide", "Usage"),
        ("Widget Guide", "Setext Heading"),
        ("Widget Guide", "Usage"),
    ]


def test_line_ranges_match_fixture_text():
    sections = parse_file(FIXTURES, "guide.md").sections

    for section in sections[1:]:
        lines = fixture_lines("guide.md", section.start_line, section.end_line)
        assert section.heading in lines[0]
        assert lines[-1].strip()
    preamble = fixture_lines("guide.md", sections[0].start_line, sections[0].end_line)
    assert preamble == ["Intro text before any heading."]


def test_code_fence_line_is_not_a_heading():
    sections = parse_file(FIXTURES, "guide.md").sections

    assert all("not a heading" not in s.heading for s in sections)
    usage = sections[4]
    assert "# not a heading" in usage.body
    assert usage.body.startswith("Turn the crank.")


def test_title_and_summary_from_front_matter():
    parsed = parse_file(FIXTURES, "guide.md")

    assert parsed.file.title == "Widget Guide"
    assert parsed.file.summary == "How to assemble and tune the sample widget."
    assert {(s.title, s.summary) for s in parsed.sections} == {
        ("Widget Guide", "How to assemble and tune the sample widget.")
    }


def test_front_matter_stays_out_of_bodies():
    sections = parse_file(FIXTURES, "guide.md").sections

    for section in sections:
        for text in ("title:", "summary:", "How to assemble"):
            assert text not in section.body
    assert sections[0].body == "Intro text before any heading."


def test_title_falls_back_to_first_h1(tmp_path):
    (tmp_path / "doc.md").write_text("Lead.\n\n## Before\n\n# First\n\n# Second\n")

    parsed = parse_file(tmp_path, "doc.md")

    assert parsed.file.title == "First"
    assert parsed.file.summary is None
    assert parsed.sections[0].heading == "First"


def test_non_string_front_matter_counts_as_absent():
    parsed = parse_file(FIXTURES, "non-string-title.md")

    assert parsed.file.title == "Real Title"
    assert parsed.file.summary is None
    assert [(s.heading, s.start_line, s.end_line) for s in parsed.sections] == [
        ("Real Title", 6, 8)
    ]


def test_invalid_front_matter_is_parsed_as_markdown():
    parsed = parse_file(FIXTURES, "invalid-front-matter.md")

    assert parsed.file.title is None
    summary = [
        (s.anchor, s.heading, s.level, s.start_line, s.end_line, s.heading_trail)
        for s in parsed.sections
    ]
    assert summary == [
        ("", "", 0, 1, 1, ()),
        ("title-unclosed", "title: [unclosed", 2, 2, 4, ("title: [unclosed",)),
    ]
    assert parsed.sections[1].body == "Body line after the block."


def test_unclosed_front_matter_is_parsed_as_markdown(tmp_path):
    (tmp_path / "doc.md").write_text("---\ntitle: Open\n\n# Heading\n")

    parsed = parse_file(tmp_path, "doc.md")

    assert parsed.file.title == "Heading"
    assert parsed.sections[0].start_line == 1


def test_file_without_headings_is_one_preamble():
    parsed = parse_file(FIXTURES, "plain.md")

    assert len(parsed.sections) == 1
    preamble = parsed.sections[0]
    assert (preamble.anchor, preamble.heading, preamble.level) == ("", "", 0)
    assert (preamble.start_line, preamble.end_line) == (1, 3)
    assert preamble.body == "Just a paragraph with no headings.\n\nAnother paragraph."


def test_empty_file_has_no_sections(tmp_path):
    (tmp_path / "empty.md").write_text("")

    parsed = parse_file(tmp_path, "empty.md")

    assert parsed.sections == []
    assert parsed.file.section_count == 0


def test_heading_text_and_anchor_rules(tmp_path):
    (tmp_path / "doc.md").write_text(
        "# The `atd sync` Command!\n\n## Café & Crème\n\n## snake_case-name\n\n"
        "## Usage\n\n## Usage\n\n## Usage-1\n"
    )

    sections = parse_file(tmp_path, "doc.md").sections

    assert [(s.heading, s.anchor) for s in sections] == [
        ("The atd sync Command!", "the-atd-sync-command"),
        ("Café & Crème", "café--crème"),
        ("snake_case-name", "snake_case-name"),
        ("Usage", "usage"),
        ("Usage", "usage-1"),
        ("Usage-1", "usage-1-1"),
    ]


def test_file_record_fields():
    path = FIXTURES / "guide.md"
    stat = path.stat()

    record = parse_file(FIXTURES, "guide.md").file

    assert record.path == "guide.md"
    assert record.size == stat.st_size
    assert record.mtime_ns == stat.st_mtime_ns
    assert record.section_count == 7
    assert len(record.content_hash) == 64


def test_content_hash_changes_with_one_byte(tmp_path):
    shutil.copy(FIXTURES / "guide.md", tmp_path / "guide.md")
    before = parse_file(tmp_path, "guide.md").file.content_hash

    data = bytearray((tmp_path / "guide.md").read_bytes())
    data[-3] = ord("x")
    (tmp_path / "guide.md").write_bytes(bytes(data))

    assert parse_file(tmp_path, "guide.md").file.content_hash != before


@pytest.mark.parametrize("newline", ["\r\n", "\n"])
def test_line_numbers_ignore_newline_style(tmp_path, newline):
    text = newline.join(["---", "title: T", "---", "", "# A", "", "Body.", ""])
    (tmp_path / "doc.md").write_bytes(text.encode())

    sections = parse_file(tmp_path, "doc.md").sections

    assert [(s.heading, s.start_line, s.end_line) for s in sections] == [("A", 5, 7)]


def test_nested_path_is_kept(tmp_path):
    os.makedirs(tmp_path / "docs" / "sub")
    (tmp_path / "docs" / "sub" / "a.md").write_text("# A\n")

    parsed = parse_file(tmp_path, "docs/sub/a.md")

    assert parsed.file.path == "docs/sub/a.md"
    assert parsed.sections[0].path == "docs/sub/a.md"
