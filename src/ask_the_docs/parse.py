"""Turn one Markdown file into a file record and ordered section records.

Follows docs/architecture/indexing.md §Parsing and §Records, minus the
catalogue fields and section parts, which later stories add.
"""

import hashlib
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token

_MARKDOWN = MarkdownIt("commonmark")


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: str
    mtime_ns: int
    size: int
    content_hash: str
    title: str | None
    summary: str | None
    section_count: int


@dataclass(frozen=True, slots=True)
class SectionRecord:
    path: str
    anchor: str
    ordinal: int
    heading: str
    heading_trail: tuple[str, ...]
    level: int
    start_line: int
    end_line: int
    body: str
    title: str | None
    summary: str | None


@dataclass(frozen=True, slots=True)
class ParsedFile:
    file: FileRecord
    sections: list[SectionRecord]


@dataclass(frozen=True, slots=True)
class _Heading:
    level: int
    text: str
    slug: str
    start: int  # 0-based index of the heading's first line
    body_start: int  # 0-based index of the first line after the heading


def parse_file(root: Path, rel_path: str) -> ParsedFile:
    """Parse ``root / rel_path``; line numbers in the records are 1-based and inclusive."""
    with open(root / rel_path, "rb") as handle:
        stat = os.fstat(handle.fileno())
        raw = handle.read()

    text = (
        raw.decode("utf-8-sig", errors="replace")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    front_matter, lines = _split_front_matter(lines)
    headings = _headings(lines)

    title = _string_field(front_matter, "title")
    if title is None:
        title = next((h.text for h in headings if h.level == 1), None)
    summary = _string_field(front_matter, "summary")

    sections: list[SectionRecord] = []

    def add(
        anchor: str,
        heading: str,
        trail: tuple[str, ...],
        level: int,
        start: int,
        body_start: int,
        stop: int,
    ) -> None:
        end = _trim_trailing_blanks(lines, start, stop)
        body = "\n".join(lines[body_start : end + 1]).strip("\n")
        sections.append(
            SectionRecord(
                path=rel_path,
                anchor=anchor,
                ordinal=len(sections),
                heading=heading,
                heading_trail=trail,
                level=level,
                start_line=start + 1,
                end_line=end + 1,
                body=body,
                title=title,
                summary=summary,
            )
        )

    preamble_stop = headings[0].start if headings else len(lines)
    first_text = next((i for i in range(preamble_stop) if lines[i].strip()), None)
    slugs: dict[str, int] = {}
    if first_text is not None:
        add("", title or "", (), 0, first_text, first_text, preamble_stop)
        slugs[""] = 0  # the preamble owns the empty anchor
    stack: list[_Heading] = []
    for index, heading in enumerate(headings):
        while stack and stack[-1].level >= heading.level:
            stack.pop()
        stack.append(heading)
        stop = headings[index + 1].start if index + 1 < len(headings) else len(lines)
        add(
            _unique_slug(heading.slug, slugs),
            heading.text,
            tuple(h.text for h in stack),
            heading.level,
            heading.start,
            heading.body_start,
            stop,
        )

    record = FileRecord(
        path=rel_path,
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
        content_hash=hashlib.sha256(raw).hexdigest(),
        title=title,
        summary=summary,
        section_count=len(sections),
    )
    return ParsedFile(file=record, sections=sections)


def _split_front_matter(lines: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Return the front-matter mapping and the lines with the block blanked out.

    Blanking, rather than removing, keeps every later line number true to the
    file. An empty block counts as an empty mapping. A block that is not valid
    YAML or not a mapping is left in place and parsed as ordinary Markdown.
    """
    if not lines or lines[0].rstrip() != "---":
        return {}, lines
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if close is None:
        return {}, lines
    try:
        data = yaml.safe_load("\n".join(lines[1:close]))
    except yaml.YAMLError:
        return {}, lines
    if data is None:  # an empty block is still front matter
        data = {}
    if not isinstance(data, dict):
        return {}, lines
    return data, [""] * (close + 1) + lines[close + 1 :]


def _string_field(front_matter: dict[str, Any], key: str) -> str | None:
    value = front_matter.get(key)
    return value if isinstance(value, str) else None


def _headings(lines: list[str]) -> list[_Heading]:
    tokens = _MARKDOWN.parse("\n".join(lines) + "\n")
    headings: list[_Heading] = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.map is None:
            continue
        start, body_start = token.map
        raw = _inline_text(tokens[index + 1])
        headings.append(
            _Heading(
                level=int(token.tag[1:]),
                # A line break reads as a space, but GitHub's anchor drops it.
                text=raw.replace("\n", " "),
                slug=_slug(raw),
                start=start,
                body_start=body_start,
            )
        )
    return headings


def _inline_text(inline: Token) -> str:
    parts: list[str] = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append("\n")
    return "".join(parts).strip()


def _trim_trailing_blanks(lines: list[str], start: int, stop: int) -> int:
    """Return the 0-based index of the last non-blank line in ``[start, stop)``."""
    end = stop - 1
    while end > start and not lines[end].strip():
        end -= 1
    return end


def _slug(text: str) -> str:
    """Build a GitHub-style anchor for ordinary heading text."""
    kept = (
        char
        for char in text.lower()
        if char in "_- " or unicodedata.category(char)[0] in "LM" or char.isdecimal()
    )
    return "".join(kept).replace(" ", "-")


def _unique_slug(slug: str, seen: dict[str, int]) -> str:
    """Suffix repeats with ``-1``, ``-2`` and so on, as GitHub's slugger does."""
    unique = slug
    while unique in seen:
        seen[slug] += 1
        unique = f"{slug}-{seen[slug]}"
    seen[unique] = 0
    return unique
