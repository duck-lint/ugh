"""Parse one Markdown note into the stage-one canonical structures.

This module deliberately stops at parsing.  It does not resolve wikilinks,
persist records, build retrieval representations, or perform embedding.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
from typing import Any, Iterable

from markdown_it import MarkdownIt
from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError


class NoteParseError(ValueError):
    """The note cannot be represented by the scoped parse contract."""


@dataclass(frozen=True)
class Wikilink:
    """An authored wikilink, retained without target resolution."""

    raw: str
    target: str
    label: str


@dataclass(frozen=True)
class FrontmatterField:
    """An admitted field with authored presence/blank/value distinction."""

    name: str
    state: str  # absent, present_blank, or present_value
    value: Any = None


@dataclass(frozen=True)
class SemanticObject:
    uuid: str
    authored_path: str
    path_hierarchy: tuple[str, ...]
    frontmatter: dict[str, Any]
    admitted_fields: tuple[FrontmatterField, ...]


@dataclass(frozen=True)
class HeadingRegion:
    region_id: str
    level: int
    heading: str
    raw_markdown: str
    region_path: tuple[str, ...]
    parent_region_id: str | None


@dataclass(frozen=True)
class SemanticUnit:
    unit_id: str
    source_object_uuid: str
    authored_path: str
    path_hierarchy: tuple[str, ...]
    region_path: tuple[str, ...]
    raw_markdown: str
    parsed_text: str
    wikilinks: tuple[Wikilink, ...]


@dataclass(frozen=True)
class ParsedNote:
    semantic_object: SemanticObject
    regions: tuple[HeadingRegion, ...]
    units: tuple[SemanticUnit, ...]


_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def _wikilink_rule(state: Any, silent: bool) -> bool:
    """markdown-it inline rule for Obsidian wikilinks.

    It runs as an inline rule, so code spans are already consumed by the
    upstream parser and cannot accidentally become wikilink tokens.
    """

    match = _WIKILINK.match(state.src, state.pos)
    if match is None or (state.pos > 0 and state.src[state.pos - 1] == "\\"):
        return False
    if silent:
        return True
    token = state.push("wikilink", "", 0)
    token.content = match.group(2) or match.group(1)
    token.attrs = {
        "target": match.group(1),
        "label": match.group(2) or match.group(1),
        "raw": match.group(0),
    }
    state.pos = match.end()
    return True


def _markdown_parser() -> MarkdownIt:
    parser = MarkdownIt("commonmark")
    parser.inline.ruler.before("text", "semantic_traversal_wikilink", _wikilink_rule)
    return parser


def _frontmatter(source: str) -> tuple[dict[str, Any], int]:
    lines = source.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise NoteParseError("note must begin with YAML frontmatter")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise NoteParseError("frontmatter closing delimiter is missing")
    yaml = YAML(typ="safe", pure=True)
    yaml.version = (1, 2)
    try:
        values = yaml.load("".join(lines[1:end])) or {}
    except DuplicateKeyError as exc:
        raise NoteParseError("frontmatter contains duplicate keys") from exc
    if not isinstance(values, dict):
        raise NoteParseError("frontmatter must contain a mapping")
    return dict(values), end + 1


def _path_data(authored_path: str) -> tuple[str, ...]:
    normalized = authored_path.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise NoteParseError("authored path must be a relative, vault-scoped path")
    return path.parts


def _admitted_fields(frontmatter: dict[str, Any], names: Iterable[str]) -> tuple[FrontmatterField, ...]:
    fields = []
    for name in names:
        if name not in frontmatter:
            fields.append(FrontmatterField(name, "absent"))
        elif frontmatter[name] is None or frontmatter[name] == "":
            fields.append(FrontmatterField(name, "present_blank", frontmatter[name]))
        else:
            fields.append(FrontmatterField(name, "present_value", frontmatter[name]))
    return tuple(fields)


def _root_block_spans(tokens: list[Any], body_lines: list[str]) -> list[tuple[int, int, Any]]:
    """Return root Markdown blocks; nesting, not blank lines, defines spans."""

    spans: list[tuple[int, int, Any]] = []
    depth = 0
    current: tuple[int, Any] | None = None
    current_end = 0
    for token in tokens:
        token_map = token.map
        if depth == 0 and token_map is not None and token.type != "heading_close":
            if current is not None:
                spans.append((current[0], current_end, current[1]))
                current = None
            current = (token_map[0], token)
            current_end = token_map[1]
        if current is not None and token_map is not None:
            current_end = max(current_end, token_map[1])
        depth += token.nesting
        if depth < 0:
            raise NoteParseError("Markdown parser produced invalid block nesting")
    if current is not None:
        spans.append((current[0], current_end, current[1]))
    return [(start, end, token) for start, end, token in spans if end > start and end <= len(body_lines)]


def _parsed_text_and_links(parser: MarkdownIt, raw: str) -> tuple[str, tuple[Wikilink, ...]]:
    """Extract visible text from parsed Markdown blocks, not source lines."""

    tokens = parser.parse(raw)
    text_parts: list[str] = []
    links: list[Wikilink] = []
    for token in tokens:
        if token.type == "inline" and token.children:
            for child in token.children:
                if child.type == "wikilink":
                    attrs = child.attrs or {}
                    links.append(Wikilink(attrs["raw"], attrs["target"], attrs["label"]))
                    text_parts.append(child.content)
                elif child.type in {"text", "code_inline", "softbreak", "hardbreak"}:
                    text_parts.append(child.content if child.type != "softbreak" else "\n")
        elif token.type in {"code_block", "fence"}:
            text_parts.append(token.content)
    return "".join(text_parts), tuple(links)


def parse_note(path: str | Path, *, vault_root: str | Path | None = None, semantic_identifier_fields: Iterable[str]) -> ParsedNote:
    """Parse exactly one Markdown note using the supplied build admission list."""

    source_path = Path(path)
    source = source_path.read_text(encoding="utf-8")
    frontmatter, body_start = _frontmatter(source)
    uuid = frontmatter.get("uuid")
    if not isinstance(uuid, str) or not uuid.strip():
        raise NoteParseError("frontmatter must contain one non-empty uuid")
    authored_path = source_path.relative_to(vault_root).as_posix() if vault_root else source_path.as_posix()
    hierarchy = _path_data(authored_path)
    semantic_object = SemanticObject(uuid, authored_path, hierarchy, frontmatter, _admitted_fields(frontmatter, semantic_identifier_fields))

    body = "".join(source.splitlines(keepends=True)[body_start:])
    body_lines = body.splitlines(keepends=True)
    parser = _markdown_parser()
    tokens = parser.parse(body)
    regions: list[HeadingRegion] = []
    active: list[HeadingRegion] = []
    units: list[SemanticUnit] = []
    for start, end, token in _root_block_spans(tokens, body_lines):
        raw = "".join(body_lines[start:end])
        if token.type == "heading_open":
            level = int(token.tag[1:])
            inline = next(t for t in tokens[tokens.index(token) + 1 :] if t.type == "inline")
            heading, _ = _parsed_text_and_links(parser, inline.content)
            active[:] = [region for region in active if region.level < level]
            region = HeadingRegion(f"region-{len(regions) + 1:04d}", level, heading, raw, tuple(r.region_id for r in active), active[-1].region_id if active else None)
            regions.append(region)
            active.append(region)
        else:
            parsed, links = _parsed_text_and_links(parser, raw)
            units.append(SemanticUnit(f"unit-{len(units) + 1:04d}", uuid, authored_path, hierarchy, tuple(r.region_id for r in active), raw, parsed, links))
    return ParsedNote(semantic_object, tuple(regions), tuple(units))
