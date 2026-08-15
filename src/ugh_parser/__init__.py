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
from .resolve import ResolutionError, ResolutionFailure, ResolutionResult, ResolvedRelation, ObjectTarget, RegionTarget, resolve_relations
from .canonical import CanonicalObject, CanonicalRegion, CanonicalRegionReference, CanonicalRelation, CanonicalUnit, CanonicalizationError, CompletedIngest, canonicalize_ingest
from .substrate import SubstrateError, foreign_key_check, hydrate_unit, write_completed_ingest
from .exact import exact_lookup, build_exact_index
from .lexical import LexicalHit, build_lexical_index, lexical_integrity_check, lexical_lookup

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
    "ResolutionError",
    "ResolutionFailure",
    "ResolutionResult",
    "ResolvedRelation",
    "ObjectTarget",
    "RegionTarget",
    "resolve_relations",
    "CanonicalObject",
    "CanonicalRegion",
    "CanonicalRegionReference",
    "CanonicalRelation",
    "CanonicalUnit",
    "CanonicalizationError",
    "CompletedIngest",
    "canonicalize_ingest",
    "SubstrateError",
    "write_completed_ingest",
    "hydrate_unit",
    "foreign_key_check",
    "build_exact_index",
    "exact_lookup",
    "LexicalHit",
    "build_lexical_index",
    "lexical_lookup",
    "lexical_integrity_check",
]
