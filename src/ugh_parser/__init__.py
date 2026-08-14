"""Single-note parsing for the build's first implementation stage."""

from .parser import (
    BuildConfig,
    Embed,
    FrontmatterField,
    HeadingRegion,
    NoteParseError,
    ParsedNote,
    SemanticObject,
    SemanticUnit,
    Wikilink,
    load_build_config,
    parse_note,
)
from .vault import CorpusFailure, VaultParseResult, discover_markdown_notes, parse_vault

__all__ = [
    "FrontmatterField",
    "BuildConfig",
    "Embed",
    "HeadingRegion",
    "NoteParseError",
    "ParsedNote",
    "SemanticObject",
    "SemanticUnit",
    "Wikilink",
    "load_build_config",
    "parse_note",
    "CorpusFailure",
    "VaultParseResult",
    "discover_markdown_notes",
    "parse_vault",
]
