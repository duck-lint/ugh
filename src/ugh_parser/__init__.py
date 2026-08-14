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
from .materialize import MaterializedCorpus, MaterializedUnit, MaterializationError, RelationCandidate, materialize_context

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
    "MaterializedCorpus",
    "MaterializedUnit",
    "MaterializationError",
    "RelationCandidate",
    "materialize_context",
]
