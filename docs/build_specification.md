## 1. Build configuration
### 1.1 Semantic-identifier admission list
The build configuration contains a mutable list of frontmatter fields that are admitted as semantic identifiers on ingest. 
[[Build Config Seed]] 
### 1.2 UUID is identity, not a semantic identifier
`uuid` identifies the semantic object. It is not a semantic identifier merely because it appears in frontmatter. Duplicate or missing `uuid` on ingest is hard fail.
### 1.3 Build and runtime configuration are separate concerns
The semantic-identifier admission list belongs to build configuration because changing the YAML schema changes ingest behavior. A runtime configuration is expected separately.
## 2. Read and parse one Markdown note
### 2.1 One Markdown note is one semantic object
Each `.md` note is one semantic object. If the Markdown note is renamed/moved while retaining its UUID, it must remain the same semantic object.
### 2.2 Preserve the authored path and its ordered hierarchy
Path represents authored scope hierarchy. Path components express the scope within which the author located a semantic object. Preserve both the complete authored path and its ordered hierarchy. Do not flatten authored scope topology into frontmatter identifiers. If the Markdown note is renamed/moved while retaining its UUID, it must remain the same semantic object while its meaningful path context changes.
### 2.3 Preserve three states for admitted frontmatter fields
For an admitted field, absence, authored blank, and authored value are different semantic states. `PresentBlank` is the semantic state. A programming language may internally use `null` or `None`, but that spelling is not the authored meaning.
### 2.4 Excluded folders
Each excluded_folders entry is an exact vault-relative directory path; that directory and its descendants are excluded, while directories with the same leaf name at other vault-relative paths remain included.
## 3. Build regions
### 3.1 Headings create nested semantic regions
Markdown headings from `#` through `######` form nested semantic regions. A region is a path-addressable semantic scope boundary that organizes semantic units. Addressing a region provides access to the units inhabiting that scope; the region itself is not a semantic unit. Region resolution first attempts exact canonical heading-address equality. If no exact match exists, compare the authored region fragment and canonical heading-address text using a normalized address key that applies Unicode case-folding, treats runs of non-letter/non-number characters as separators, collapses separator runs to one space, and trims leading/trailing space. Canonical authored heading text and heading-address text remain unchanged. Normalization is comparison-only and does not authorize substring, prefix, fuzzy, stemming, synonym, or semantic matching.
### 3.2 Units inherit the complete region path
A unit under nested headings inherits the complete region path, not only its immediate heading—store or resolve the ordered chain of scoped regions from the highest level heading to the most immediate region.
## 4. Build semantic units and chunk boundaries
### 4.1 Markdown-formatted semantic units become chunks
Authored content units under regions become semantic units/chunks. Blank separator lines do not become chunks. Regions do not become chunks. Markdown structure determines semantic-unit boundaries; paragraphs, tables, lists, code blocks, and other supported Markdown block forms may each materialize as semantic units/chunks.
### 4.2 Preserve raw Markdown and parsed text separately
Each unit preserves both its authored Markdown and parsed linguistic text.
### 4.3 Every unit remains traceable to its source object
Every semantic unit must remain connected to the object it came from. Hydration during runtime will surface provenance for synthesis. Every semantic unit receives a `unit_id` within the completed ingest, and every retrieval representation uses that `unit_id` to hydrate the canonical semantic unit. Each unit separately retains `source_object_uuid` for object-level provenance. Unit IDs are not required to persist across ingests. 
### 4.4 Overflow
- canonical semantic unit is never split because of embedding limits;
- embedding input is never silently truncated;
- every character/token of parsed_text must be represented by at least
  one vector segment;
- segmentation prefers natural textual boundaries;
- adjacent segments may overlap to preserve boundary context;
- all vector segments point to the same unit_id;
- hydration always returns the complete canonical unit, not merely
  the matching vector segment.
### 4.5 Semantic Model Sample
path: `C:\Users\madis\Desktop\kháos\LAYER-1 PILLARS\PILLAR 2-DYNAMIC COHERENCE\JOURNAL\2026\2026-04\07_Tuesday.md`
- Lines 1-26: YAML **frontmatter** with 3 **wikilink** connections—I'd expect the semantics of those **wikilink** connections to be carried into the **units** along with the rest of the **frontmatter identifiers**
- Line 27: "Dream Recall" semantic **region**
	- Line 28: semantic **unit** with 2 **wikilink** connections—I'd expect the semantics of those **wikilink** connections to be carried into the **unit** itself
- Line 29: blank
- Line 30: "Yesterday Review" semantic **region**
	- Line 31: semantic **unit** with 2 **wikilink** connections—I'd expect the semantics of those **wikilink** connections to be carried into the **unit** itself
- Line 32: blank
- Line 33: "Daily Intent" semantic **region**
	- Line 34: semantic **unit*** with 1 **wikilink**—I'd expect the semantics of those **wikilink** connections to be carried into the **unit** itself
- Line 35: blank
- Line 36: "Freeform Journaling" semantic **region**
	- Line 37: semantic **unit*** with 2 **wikilink** connections—I'd expect the semantics of those **wikilink** connections to be carried into the **unit** itself
	- Line 38: blank
	- Line 39: semantic **unit*** with 2 **wikilink** connections—I'd expect the semantics of those **wikilink** connections to be carried into the **unit** itself
	- Line 40: blank
	- Line 41: semantic **unit*** with 4 **wikilink** connections—I'd expect the semantics of those **wikilink** connections to be carried into the **unit** itself
	- Line 42: blank

- x1 semantic **object**
- x4 semantic **regions**
- x6 semantic **units** = x6 **chunks**
	- all **units** inherit the region they inhabit, the **object frontmatter**, and the **substrate/hyperspace topology** through **path** 
	- semantic **regions** are not **chunks**, semantic **units** are
## 5. Inherit object context into every unit
### 5.1 Inherit the path and admitted semantic identifiers
Every unit inherits its object's meaningful path and all frontmatter fields admitted by the current build configuration as semantic identifiers. This makes the unit traceable and lets the object's semantic context participate in retrieval through appropriate surfaces.
### REGION ADDRESS NORMALIZATION
Region resolution occurs only within the already-resolved target object. First attempt exact authored heading-text equality. If no exact heading matches, compare the authored region fragment and candidate heading text using a punctuation-insensitive address key:
- preserve authored canonical heading text unchanged;
- treat runs of non-letter/non-number characters as separators;
- collapse separator runs to one space;
- trim leading/trailing space;
- do not otherwise alter words.
Resolution remains equality on that normalized address key.
```text
exactly 1 normalized match → resolve to that canonical region
0 matches                  → unresolved
>1 matches                 → ambiguous, list contextual candidate regions
```
This normalization is only for region addressing. It does not rewrite canonical heading text and does not authorize substring, prefix, fuzzy, stemming, synonym, or wording-based matching.
## 6. Parse and resolve wikilinks
### 6.1 A wikilink is structured topology, not only text
The Markdown brackets are authored syntax. The parser must preserve the authored form, visible text, and addressed target as distinct information. Each output must retain the correct target address and visible text without losing the raw Markdown.
### 6.2 Frontmatter wikilinks create typed inherited relations
When an admitted frontmatter field contains a wikilink, every unit in that object inherits a relation to the target. The relation name is the frontmatter field name.
### 6.3 Body wikilinks create `linked_to`
A body wikilink has no additional authored relation type. It creates a generic `linked_to` relation. Build runtime will not infer anything.
### 6.4 Preserve distinct reasons for the same connection
A frontmatter-derived relation and a body-derived relation remain distinct facts even when they share the same source unit and target object—differentiated by either inheriting the relation from frontmatter, or being `linked_to` if from body. A semantic region preserves its raw authored heading Markdown, parsed linguistic heading text, and canonical heading-address text separately. Region resolution first attempts exact canonical heading-address equality. If no exact match exists, compare the authored region fragment and canonical heading-address text using a normalized address key that applies Unicode case-folding, treats runs of non-letter/non-number characters as separators, collapses separator runs to one space, and trims leading/trailing space. Canonical authored heading text and heading-address text remain unchanged. Normalization is comparison-only and does not authorize substring, prefix, fuzzy, stemming, synonym, or semantic matching.
### 6.5 Authored wikilinks outside of escape characters must resolve
Every authored wikilink—not prefaced with an escape character (\) or inside of `codeblocks`—must resolve to the semantic target it addresses. An object link requires the object. An object-plus-region link requires both the object and region. Ingest hard fails otherwise—with vault-wide manifest of what target object is missing and where the source for the link is. Object-name and alias address comparison is case-insensitive using Unicode case-folding. Canonical authored names, aliases, paths, and link text remain unchanged. Case normalization is comparison-only and does not create fuzzy, substring, lexical, or semantic matching.
```text
WIKILINK RESOLUTION

1. A resolved relation stores the canonical target_object_uuid,
   not merely the authored filename.

2. If the wikilink contains a vault-relative path:
   resolve that exact path → target object → target UUID.

3. If the wikilink contains only a note name or alias:
   resolve against matching objects across the vault.

   exactly 1 match → resolve to that object's UUID
   0 matches       → ingest hard fail: unresolved
   >1 matches      → ingest hard fail: ambiguous, list candidates

4. [[Object#Region]]
   additionally resolves the region inside the resolved target object.

5. Once resolved, later retrieval uses the UUID, so two objects named
   02_Tuesday in different folders remain completely distinct.
```
## 7. Canonical semantic-unit record
### 7.1 The canonical unit owns its semantics
The semantic unit is the canonical thing. Retrieval surfaces own representations of, and pointers back to, that unit. Retrieval indexes are not additional authoritative copies of the unit's semantic state. Store rich semantic context on the canonical unit. Store only the fields each retrieval surface needs to retrieve a `unit_id`, unless a later explicit decision requires duplication. A canonical unit must be able to retain:
```text
unit_id
source_object_uuid
source path
complete semantic path hierarchy
complete region path
raw Markdown
parsed text
admitted inherited identifier states
typed inherited relations
body linked_to relations
```
Runtime hydration by `unit_id` will return the canonical record and its full differing semantic context without relying on duplicated index metadata.
### 7.2 Retrieval hits converge on `unit_id` and hydrate
A hit through any retrieval surface lands on a `unit_id`. Hydration uses that ID to return the canonical semantic unit and all of its context for synthesis.
## 9. Exact and lexical representations
### 9.1 Searchable fields remain separate
Structured semantic fields must not be flattened into one large string for search. Fields remain separately addressable:
```text
raw_markdown
parsed_text
every admitted semantic identifier
complete region path
semantic path hierarchy/components
```
### 9.2 Exact-index record shape
Exact retrieval is a fielded inverted lookup: each enabled exact-search field maps exact field values to the `unit_id`s carrying that value. The exact index is derivative of canonical units and returns `unit_id`s for hydration; it is not another semantic source of truth.
### 9.3 Exact matching normalization
- Preserve the authored field value exactly as written.
- Compare text-like values case-insensitively.
- Ignore insignificant whitespace differences during comparison:
    - trim leading/trailing whitespace;
    - collapse runs of whitespace to a single space.
- Exact matching is still **field-value equality**, not substring matching.
- Normalization is used only for lookup/comparison; it does not rewrite the canonical unit.
### 9.4 Lexical content is searchable
Parsed unit content is lexically searchable. Admitted frontmatter fields (semantic identifiers) are lexical-searchable—this being driven by the build config. Region text and semantic path components are lexical-searchable as separate fields. Lexical retrieval performs word/phrase matching over their authored text; it does not embed them or infer semantic similarity. Date-valued admitted semantic identifiers are exact-searchable by value. Aliases are alternative authored names resolving to the same canonical target. Aliases are exact- and lexical-searchable without replacing the canonical name. Tags, when admitted by build config, are multi-valued semantic identifiers. Each tag value is separately exact- and lexical-searchable. Tags express authored semantic grouping; they do not create graph relations unless a separate explicit rule later says they do.
### 9.5 lexical-index technology and tokenization
Lexical retrieval uses a fielded inverted full-text index with Unicode-aware tokenization, case-insensitive terms, BM25 ranking, and phrase-query support. Common words are retained and naturally downweighted by BM25. No custom stopword list, stemming, synonym expansion, or semantic query expansion is used. Parsed unit text and admitted semantic-identifier fields remain separate lexical fields.
## 10. Vector representation
### 10.1 Vector records derive from semantic units
Each semantic unit produces one or more vector records derived only
from its parsed intrinsic text.
```text
VectorRecord {
    vector_id,
    unit_id,
    segment_ordinal,
    vector
}
```
### 10.2 Vector input is parsed intrinsic unit text only
The embedding input is the unit's parsed intrinsic text and nothing else. It excludes:
- object UUID;
- unit ID;
- raw path;
- semantic path components;
- region heading text;
- frontmatter field names and values;
- inherited relations;
- body-link target metadata; and
- raw Markdown syntax.
Visible link text remains in parsed linguistic text.
### 10.3 The vector index is not a semantic source of truth
Canonical semantic metadata belongs to the semantic unit, not to duplicated vector metadata. Hydration will retrieve the canonical unit through `unit_id` that contains all the rest of the semantics.
### 10.4 Build-time and query-time embeddings must be compatible
Stored corpus vectors and conversation-time query vectors must use a compatible embedding model and version. This dependency must be driven chronologically (ingest comes before conversation, therefore conversation runtime will be dependent on verification against build embedding model, not the otherway around)
## 11. Graph representation
### 11.1 Graph edges come only from authored structure in this scope
Admitted frontmatter wikilinks produce field-named relations; body wikilinks produce `linked_to`; prose does not generate inferred relation labels. Path-derived scope topology remains semantically meaningful regardless of future graph representation choices—implementation must accommodate this and not silently subsume decision.
### 11.2 Authored containment and scope topology is projected onto the graph
The graph represents direct authored structural containment in addition to wikilink-derived relations. Graph structural node kinds are: `scope` (an authored vault-relative path scope), `semantic_object`, `semantic_region`, `semantic_unit`. Direct structural relations are: `contains_scope`, `contains_object`, `contains_region`, `contains_unit`. Only direct authored containment edges are materialized. Transitive containment is derived by graph traversal and is not stored as additional semantic facts. Traversal may follow an edge outbound or inbound; inverse copies of the same structural relation are not separately materialized. Scope-node identity is determined by its complete vault-relative scope path, not by the component name alone. Region-node identity is contextual to its semantic object and complete region hierarchy, not by heading text alone. Structural graph edges are derivative representations of the authored path, object, region, and unit topology. They do not create additional semantic authority.
## 13. Corpus semantic capability catalog
### 13.1 Capability catalog contents
The specification defines catalog classes and generation rules. Concrete semantic-identifier field names, identifier values, region values, path values, and field-derived relation names are generated from the current build configuration and ingested corpus and are not hardcoded by this specification. The capability catalog does not contain occurrence counts. Presence in the capability catalog means the value, structure, relation, or retrieval capability exists in the current ingested corpus. **Availability not cardinality.**
### 13.2 Capability catalog representation
The capability catalog uses a hybrid structured representation:
1. a field/capability matrix describing semantic dimensions, represented values, retrieval surfaces, and supported operators;
2. a relation grammar describing available relation types and their allowed source and target kinds.
#### Fields

| field class                  | values                                                                        | exact | lexical | vector |
| ---------------------------- | ----------------------------------------------------------------------------- | ----- | ------- | ------ |
| `parsed_text`                | free text from semantic units                                                 | yes   | yes     | yes    |
| admitted semantic identifier | every unique represented value for each field admitted by build configuration | yes   | yes     | no     |
| semantic region              | every unique represented region heading/path value                            | yes   | yes     | no     |
| semantic path component      | every unique represented vault-relative scope/path value                      | yes   | yes     | no     |
| `raw_markdown`               | authored Markdown of semantic units                                           | yes   | no      | no     |
#### Relations

| relation class | relation name | source | target |
|---|---|---|---|
| admitted wikilink-valued semantic identifier | the admitted field name | `semantic_unit` | resolved `semantic_object` / `semantic_region` as permitted by the authored wikilink |
| body wikilink | `linked_to` | `semantic_unit` | resolved `semantic_object` / `semantic_region` |
| structural scope containment | `contains_scope` | `scope` | `scope` |
| structural object containment | `contains_object` | `scope` | `semantic_object` |
| structural region containment | `contains_region` | `semantic_object` / `semantic_region` | `semantic_region` |
| structural unit containment | `contains_unit` | `semantic_object` / `semantic_region` | `semantic_unit` |
#### Operations

| surface | operations          |
| ------- | ------------------- |
| exact   | equals              |
| lexical | terms, phrase       |
| vector  | semantic similarity |
| graph   | relation traversal  |
**SPEC:** defines the rule that generates relation types
**BUILD CONFIG:** defines which semantic-identifier fields are admitted
**CORPUS:** supplies the actual values and wikilink targets
**BUILT CAPABILITY CATALOG:** contains the concrete instantiated fields, values, and relation names
## 14. Build publication and repair behavior
### 14.1 Publish only a referentially valid completed build
An ingest with unresolved authored links does not publish a completed build. Complete parsing and validation before marking the build publishable. On failure, keep the prior valid published build unaffected if one exists and emit the repair manifest.
### 14.2 Build validation and repair manifest
Validation is aggregate rather than fail-fast. Before rejecting an ingest, the build must collect and report every independently detectable validation failure across the included corpus. One validation failure must not prevent validation of unrelated objects or relations. The repair manifest records all detected failures with sufficient source location and target/collision information to repair them. A failure that prevents further parsing of a particular source may limit validation downstream of that source, but must not stop validation of the remainder of the corpus. Any validation failure prevents publication of the new build.
## 15 Tech stack
### 15.1 The below technologies are intended to implement the contracts above, not the other way around
#### Build runtime
- Python 3.14.x
#### Markdown parsing
- markdown-it-py
- mdit-py-plugins for supported extended Markdown structures
- a small Semantic Traversal markdown-it-py extension for Obsidian wikilinks/callout syntax that the upstream parser does not represent
#### Frontmatter parsing
- ruamel.yaml
- YAML 1.2
- safe, pure-Python parsing mode
#### Canonical substrate storage
- SQLite
- foreign-key enforcement enabled
- canonical objects, regions, units, semantic identifiers, aliases/tags, and graph relations stored in ordinary relational tables
#### Exact retrieval
- SQLite ordinary indexed tables
- fielded inverted lookup:
  (field_name, normalized_value) -> unit_id
- normalized text comparison key uses Unicode case-folding and collapsed/trimmed whitespace
- canonical authored values remain unchanged
#### Lexical retrieval
- SQLite FTS5
- separate searchable fields
- unicode61 tokenizer
- case-insensitive
- preserve diacritics
- no stemming
- no custom stopword removal
- no synonym expansion
- BM25 ranking
- phrase queries enabled
#### Graph storage
- ordinary SQLite relation/edge tables
- indexed source, target, and relation-type columns
- no separate graph database
#### Embedding runtime
- Ollama
- qwen3-embedding:0.6b
- pin the exact model identity/digest used by the build
- if `parsed_text` fits within the embedding input limit, one vector record
- document embedding input is parsed intrinsic unit text only
- 1024-dimensional float vectors
- L2-normalized vectors
- cosine similarity
#### Vector storage/search
- NumPy float32 matrix stored as .npy
- one matrix row per vector record/segment. If it exceeds the limit:
	- multiple vector-segment records
	- all → same unit_id
- SQLite stores the mapping between vector row and unit_id
- exhaustive cosine search over the complete matrix
- no ANN/vector database
#### Generated capability catalog
- JSON
- structured field/capability matrix + relation grammar + operator table
#### Build manifest
- JSON
- records build schema/version, build configuration, admitted semantic-identifier fields,
  parser versions/configuration, embedding model identity, embedding dimensions,
  lexical tokenizer configuration, and generated artifact identities
#### Published build artifacts
- substrate.sqlite3
- vectors.npy
- capability_catalog.json
- manifest.json
## Specimen acceptance checklist
The `07_Tuesday.md` fixture must prove all of the following.
- One semantic object is created with the recorded UUID.
- Four regions are created.
- Six semantic units are created with individual `unit_id`.
- Blank separator lines create no units.
- Every unit retains source-object traceability through `unit_id`.
- Every unit inherits the complete meaningful path.
- Every unit inherits the complete containing region path.
- Every unit preserves raw Markdown and parsed text separately.
- Every admitted blank frontmatter field differs from an absent field.
- Every unit inherits admitted scalar identifier state.
- Every unit inherits typed relations from admitted frontmatter wikilinks.
- Every body wikilink creates `linked_to`.
- Frontmatter-derived and body-derived relations to the same target remain distinct denoted through path type either carrying frontmatter semantics or body default `linked_to`.
- Object and region wikilinks resolve or the ingest fails with a repair report.
- Every unit inherits admitted frontmatter as semantic identifiers.
- Each semantic unit produces one or more vector records derived only from its parsed intrinsic text.
- Vector inputs exclude UUID, path, region, frontmatter (semantic identifiers), relations, and raw Markdown syntax.
- Every retrieval representation returns a `unit_id` that hydrates the full canonical unit.
- No invalid build is published as a completed capability catalog.
- The semantic capability catalog exposes every represented semantic and relation type and accurately states surface availability.
