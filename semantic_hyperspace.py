"""Build and query the Semantic Hyperspace substrate.

The implementation follows ``docs/Construct Semantic Hyperspace.md``.  The
SQLite canonical unit is authoritative; exact, lexical, graph, and vector
artifacts contain only derivative lookup data and IDs back to canonical units.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

import numpy as np
from markdown_it import MarkdownIt
from ruamel.yaml import YAML


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "docs" / "Build Config Seed.yaml"
DEFAULT_OUTPUT = ROOT / "build"
MODEL = "qwen3-embedding:0.6b"
WIKILINK = re.compile(r"(?<!\\)\[\[([^\]]+)\]\]")


@dataclass
class Relation:
    name: str
    authored: str
    visible: str
    target_object_uuid: str | None = None
    target_region_uuid: str | None = None
    source: str = "body"


@dataclass
class Region:
    region_id: str
    heading: str
    level: int
    path: tuple[str, ...]
    parent_id: str | None


@dataclass
class Unit:
    unit_id: str
    object_uuid: str
    raw_markdown: str
    parsed_text: str
    region_path: tuple[str, ...]
    relations: list[Relation] = field(default_factory=list)
    identifiers: dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectNote:
    path: str
    absolute_path: Path
    uuid: str
    frontmatter: dict[str, Any]
    field_states: dict[str, tuple[str, Any]]
    regions: list[Region]
    units: list[Unit]


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value.isoformat() if hasattr(value, "isoformat") else value


def scalar_values(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def load_config(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle) or {}


def authored_links(text: str) -> list[tuple[str, str, str]]:
    """Return (target, visible, authored) links outside fences/escapes."""
    results = []
    in_fence = False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in WIKILINK.finditer(line):
            authored = match.group(0)
            target = match.group(1).split("|", 1)[0]
            visible = match.group(1).split("|", 1)[1] if "|" in match.group(1) else target.split("#", 1)[-1]
            results.append((target.strip(), visible.strip(), authored))
    return results


def parsed_text(raw: str) -> str:
    """Render Markdown to linguistic text while retaining visible wikilink text."""
    replaced = WIKILINK.sub(lambda m: m.group(1).split("|", 1)[-1].split("#", 1)[-1], raw)
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    rendered = md.render(replaced)
    rendered = re.sub(r"<[^>]+>", " ", rendered)
    return re.sub(r"\s+", " ", html.unescape(rendered)).strip()


def parse_blocks(body: str) -> tuple[list[Region], list[tuple[str, tuple[str, ...], list[tuple[str, str, str]]]]]:
    lines = body.splitlines(keepends=True)
    regions: list[Region] = []
    blocks: list[tuple[str, tuple[str, ...], list[tuple[str, str, str]]]] = []
    stack: list[Region] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        raw = "".join(current).strip("\r\n")
        if raw.strip():
            blocks.append((raw, tuple(r.heading for r in stack), authored_links(raw)))
        current = []

    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$", line.rstrip("\r\n"))
        if heading:
            flush()
            level, title = len(heading.group(1)), heading.group(2).strip()
            while stack and stack[-1].level >= level:
                stack.pop()
            path = tuple(r.heading for r in stack) + (title,)
            region = Region(str(uuid.uuid4()), title, level, path, stack[-1].region_id if stack else None)
            regions.append(region)
            stack.append(region)
        elif not line.strip():
            flush()
        else:
            current.append(line)
    flush()
    return regions, blocks


def parse_note(path: Path, vault: Path, admitted: list[str], errors: list[dict[str, Any]]) -> ObjectNote | None:
    relative = path.relative_to(vault).as_posix()
    text = path.read_text(encoding="utf-8")
    front: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        end = re.search(r"^---\s*$", text[3:], flags=re.MULTILINE)
        if end:
            end_at = 3 + end.end()
            yaml = YAML(typ="safe")
            try:
                front = yaml.load(text[3 : 3 + end.start()]) or {}
                body = text[end_at:]
            except Exception as exc:
                errors.append({"kind": "frontmatter_parse", "path": relative, "message": str(exc)})
                return None
    raw_uuid = front.get("uuid")
    if not raw_uuid:
        errors.append({"kind": "missing_uuid", "path": relative, "field": "uuid"})
        return None
    try:
        object_uuid = str(uuid.UUID(str(raw_uuid)))
    except ValueError:
        errors.append({"kind": "invalid_uuid", "path": relative, "value": str(raw_uuid)})
        return None
    field_states = {}
    for name in admitted:
        field_states[name] = ("Absent", None) if name not in front else ("PresentBlank", None) if front[name] in (None, "", []) else ("PresentValue", json_value(front[name]))
    regions, blocks = parse_blocks(body)
    units = []
    for raw, region_path, links in blocks:
        units.append(Unit(str(uuid.uuid4()), object_uuid, raw, parsed_text(raw), region_path, identifiers=field_states.copy()))
        units[-1].relations = [Relation("linked_to", authored, visible, source="body") for _, visible, authored in links]
    return ObjectNote(relative, path, object_uuid, front, field_states, regions, units)


def resolve_links(objects: list[ObjectNote], errors: list[dict[str, Any]]) -> None:
    by_path = {o.path.casefold(): o for o in objects}
    by_name: dict[str, list[ObjectNote]] = {}
    aliases: dict[str, list[ObjectNote]] = {}
    for obj in objects:
        by_name.setdefault(Path(obj.path).stem.casefold(), []).append(obj)
        for alias in scalar_values(obj.frontmatter.get("aliases", [])):
            aliases.setdefault(str(alias).casefold(), []).append(obj)

    def target_object(address: str, source: ObjectNote) -> ObjectNote | None:
        address = address.replace("\\", "/").strip()
        candidate = by_path.get(address.casefold()) or by_path.get((address + ".md").casefold())
        if candidate:
            return candidate
        matches = by_name.get(Path(address).stem.casefold(), []) + aliases.get(address.casefold(), [])
        unique = {o.uuid: o for o in matches}
        if len(unique) == 1:
            return next(iter(unique.values()))
        errors.append({"kind": "unresolved_wikilink" if not unique else "ambiguous_wikilink", "source": source.path, "target": address, "candidates": [o.path for o in unique.values()]})
        return None

    for obj in objects:
        for field_name in ("__frontmatter__",):
            pass
        for unit in obj.units:
            # Body links are attached to their unit.
            for relation in unit.relations:
                address = relation.authored[2:-2].split("|", 1)[0]
                object_part, _, region_part = address.partition("#")
                target = target_object(object_part, obj)
                if target:
                    relation.target_object_uuid = target.uuid
                    relation.target_region_uuid = next((r.region_id for r in target.regions if r.heading.casefold() == region_part.casefold()), None) if region_part else None
                    if region_part and not relation.target_region_uuid:
                        errors.append({"kind": "unresolved_region", "source": obj.path, "target": address})
            # Inherited frontmatter wikilinks are separate typed relations.
            for field_name in admitted_fields(obj):
                value = obj.frontmatter.get(field_name)
                for target_text in scalar_values(value) if value is not None else []:
                    if not isinstance(target_text, str) or not target_text.startswith("[["):
                        continue
                    address = target_text[2:-2].split("|", 1)[0]
                    object_part, _, region_part = address.partition("#")
                    target = target_object(object_part, obj)
                    if target:
                        region_id = next((r.region_id for r in target.regions if r.heading.casefold() == region_part.casefold()), None) if region_part else None
                        if region_part and not region_id:
                            errors.append({"kind": "unresolved_region", "source": obj.path, "target": address, "field": field_name})
                        unit.relations.append(Relation(field_name, target_text, target_text, target.uuid, region_id, "frontmatter"))


def admitted_fields(obj: ObjectNote) -> list[str]:
    return list(obj.field_states)


def schema(connection: sqlite3.Connection) -> None:
    connection.executescript("""
    PRAGMA foreign_keys=ON;
    CREATE TABLE objects(uuid TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, frontmatter_json TEXT NOT NULL);
    CREATE TABLE regions(region_id TEXT PRIMARY KEY, object_uuid TEXT NOT NULL REFERENCES objects(uuid), heading TEXT NOT NULL, level INTEGER NOT NULL, path_json TEXT NOT NULL, parent_id TEXT REFERENCES regions(region_id));
    CREATE TABLE units(unit_id TEXT PRIMARY KEY, object_uuid TEXT NOT NULL REFERENCES objects(uuid), raw_markdown TEXT NOT NULL, parsed_text TEXT NOT NULL, region_path_json TEXT NOT NULL);
    CREATE TABLE identifiers(unit_id TEXT NOT NULL REFERENCES units(unit_id), field_name TEXT NOT NULL, state TEXT NOT NULL, value_json TEXT, PRIMARY KEY(unit_id, field_name));
    CREATE TABLE relations(source_unit_id TEXT NOT NULL REFERENCES units(unit_id), relation_name TEXT NOT NULL, authored TEXT NOT NULL, visible TEXT NOT NULL, target_object_uuid TEXT NOT NULL REFERENCES objects(uuid), target_region_id TEXT, source_kind TEXT NOT NULL);
    CREATE TABLE graph_nodes(node_id TEXT PRIMARY KEY, node_kind TEXT NOT NULL, authored_path TEXT NOT NULL);
    CREATE TABLE graph_edges(source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL, relation_name TEXT NOT NULL, UNIQUE(source_node_id,target_node_id,relation_name));
    CREATE TABLE exact_index(field_name TEXT NOT NULL, normalized_value TEXT NOT NULL, unit_id TEXT NOT NULL REFERENCES units(unit_id), PRIMARY KEY(field_name,normalized_value,unit_id));
    CREATE VIRTUAL TABLE lexical_index USING fts5(unit_id UNINDEXED, parsed_text, semantic_identifiers, region_path, semantic_path, raw_markdown, tokenize='unicode61 remove_diacritics 0');
    CREATE TABLE vector_records(vector_id TEXT PRIMARY KEY, unit_id TEXT NOT NULL REFERENCES units(unit_id), segment_ordinal INTEGER NOT NULL, row_index INTEGER NOT NULL);
    CREATE INDEX relations_target_idx ON relations(target_object_uuid,target_region_id,relation_name);
    CREATE INDEX graph_edges_source_idx ON graph_edges(source_node_id,relation_name);
    CREATE INDEX graph_edges_target_idx ON graph_edges(target_node_id,relation_name);
    """)


def ollama_model_info(endpoint: str = "http://127.0.0.1:11434/api/show") -> dict[str, Any]:
    request = Request(endpoint, json.dumps({"name": MODEL}).encode(), {"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except (OSError, URLError) as exc:
        raise RuntimeError(f"Ollama model metadata unavailable at {endpoint}: {exc}") from exc
    info = payload.get("model_info", {})
    context_length = info.get("qwen3.context_length")
    dimensions = info.get("qwen3.embedding_length")
    if not isinstance(context_length, int) or not isinstance(dimensions, int):
        raise RuntimeError("Ollama model metadata did not expose context length and embedding dimensions")
    digest_match = re.search(r"sha256-[0-9a-f]{64}", payload.get("modelfile", ""))
    return {"model": MODEL, "digest": digest_match.group(0) if digest_match else None, "context_length": context_length, "dimensions": dimensions}


def _embed(text: str, endpoint: str, model_info: dict[str, Any]) -> tuple[list[float], int]:
    request = Request(endpoint, json.dumps({"model": MODEL, "input": text, "truncate": False}).encode(), {"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=120) as response:
            payload = json.loads(response.read())
    except (OSError, URLError) as exc:
        raise RuntimeError(f"Ollama embedding runtime unavailable at {endpoint}: {exc}") from exc
    embeddings = payload.get("embeddings") or ([payload["embedding"]] if "embedding" in payload else [])
    vector = embeddings[0] if embeddings else []
    if len(vector) != model_info["dimensions"]:
        raise RuntimeError(f"Ollama returned an incompatible embedding dimension; expected {model_info['dimensions']}")
    token_count = payload.get("prompt_eval_count")
    if not isinstance(token_count, int):
        raise RuntimeError("Ollama did not report prompt_eval_count; cannot enforce the model input limit")
    return vector, token_count


def _split_overflow(text: str, endpoint: str, model_info: dict[str, Any]) -> list[str]:
    """Split only after Ollama rejects the complete intrinsic text.

    Paragraphs are the preferred natural boundaries.  A paragraph that still
    exceeds the model limit is divided at word boundaries; no text is dropped
    or silently truncated.
    """
    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    segments: list[str] = []
    for paragraph in paragraphs or [text]:
        words = paragraph.split()
        start = 0
        while start < len(words):
            low, high, best = start + 1, len(words), start + 1
            while low <= high:
                middle = (low + high) // 2
                candidate = " ".join(words[start:middle])
                try:
                    _, count = _embed(candidate, endpoint, model_info)
                except RuntimeError as exc:
                    if "context" not in str(exc).casefold() and "token" not in str(exc).casefold():
                        raise
                    count = model_info["context_length"] + 1
                if count <= model_info["context_length"]:
                    best, low = middle, middle + 1
                else:
                    high = middle - 1
            segment = " ".join(words[start:best])
            if not segment:
                raise RuntimeError("Unable to create a non-empty segment within the Ollama model input limit")
            segments.append(segment)
            start = best
    return segments


def ollama_embeddings(units: list[Unit], model_info: dict[str, Any], endpoint: str = "http://127.0.0.1:11434/api/embed") -> tuple[list[tuple[str, int, str]], list[list[float]]]:
    records: list[tuple[str, int, str]] = []
    vectors = []
    for unit in units:
        try:
            vector, token_count = _embed(unit.parsed_text, endpoint, model_info)
            if token_count > model_info["context_length"]:
                raise RuntimeError("model context limit exceeded")
            segments = [unit.parsed_text]
            embedded = [vector]
        except RuntimeError as exc:
            if "context" not in str(exc).casefold() and "token" not in str(exc).casefold():
                raise
            segments = _split_overflow(unit.parsed_text, endpoint, model_info)
            embedded = [_embed(segment, endpoint, model_info)[0] for segment in segments]
        for ordinal, (segment, vector) in enumerate(zip(segments, embedded)):
            records.append((unit.unit_id, ordinal, segment))
            vectors.append(vector)
    return records, vectors


def build(vault: Path, config_path: Path, output: Path) -> int:
    config = load_config(config_path)
    excluded = {str(x).replace("\\", "/").strip("/").casefold() for x in config.get("excluded_folders", [])}
    admitted = [str(x) for x in config.get("semantic_identifier_fields", [])]
    errors: list[dict[str, Any]] = []
    paths = [p for p in vault.rglob("*.md") if not any(part.casefold() in excluded for part in p.relative_to(vault).parts)]
    objects: list[ObjectNote] = []
    seen_uuid: dict[str, str] = {}
    for path in sorted(paths):
        obj = parse_note(path, vault, admitted, errors)
        if not obj:
            continue
        if obj.uuid in seen_uuid:
            errors.append({"kind": "duplicate_uuid", "uuid": obj.uuid, "paths": [seen_uuid[obj.uuid], obj.path]})
        seen_uuid[obj.uuid] = obj.path
        objects.append(obj)
    resolve_links(objects, errors)
    # Do not publish or overwrite the prior valid build until all validation and embeddings succeed.
    output.mkdir(parents=True, exist_ok=True)
    repair = output / "repair_manifest.json"
    if errors:
        repair.write_text(json.dumps({"errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2
    units = [unit for obj in objects for unit in obj.units]
    try:
        model_info = ollama_model_info()
        vector_records, vectors = ollama_embeddings(units, model_info)
    except RuntimeError as exc:
        repair.write_text(json.dumps({"errors": [{"kind": "embedding_runtime", "message": str(exc)}]}, indent=2), encoding="utf-8")
        return 3
    staging = output / ".staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    db_path = staging / "substrate.sqlite3"
    conn = sqlite3.connect(db_path)
    schema(conn)
    unit_by_id = {}
    for obj in objects:
        conn.execute("INSERT INTO objects VALUES(?,?,?)", (obj.uuid, obj.path, json.dumps(json_value(obj.frontmatter), ensure_ascii=False)))
        scope_parts = PurePosixPath(obj.path).parts[:-1]
        previous = None
        for i in range(1, len(scope_parts) + 1):
            scope = "/".join(scope_parts[:i]); node = "scope:" + scope
            conn.execute("INSERT OR IGNORE INTO graph_nodes VALUES(?,?,?)", (node, "scope", scope))
            if previous: conn.execute("INSERT OR IGNORE INTO graph_edges VALUES(?,?,?)", (previous, node, "contains_scope"))
            previous = node
        object_node = "object:" + obj.uuid
        conn.execute("INSERT INTO graph_nodes VALUES(?,?,?)", (object_node, "semantic_object", obj.path))
        if previous: conn.execute("INSERT INTO graph_edges VALUES(?,?,?)", (previous, object_node, "contains_object"))
        for region in obj.regions:
            conn.execute("INSERT INTO regions VALUES(?,?,?,?,?,?)", (region.region_id,obj.uuid,region.heading,region.level,json.dumps(region.path),region.parent_id))
            node = "region:" + region.region_id
            conn.execute("INSERT INTO graph_nodes VALUES(?,?,?)", (node,"semantic_region","#".join(region.path)))
            parent = "region:" + region.parent_id if region.parent_id else object_node
            conn.execute("INSERT INTO graph_edges VALUES(?,?,?)", (parent,node,"contains_region"))
        for unit in obj.units:
            unit_by_id[unit.unit_id] = unit
            conn.execute("INSERT INTO units VALUES(?,?,?,?,?)", (unit.unit_id,obj.uuid,unit.raw_markdown,unit.parsed_text,json.dumps(unit.region_path)))
            identifiers_text=[]
            for field_name,(state,value) in unit.identifiers.items():
                conn.execute("INSERT INTO identifiers VALUES(?,?,?,?)", (unit.unit_id,field_name,state,json.dumps(value,ensure_ascii=False)))
                if state != "Absent":
                    identifiers_text.append(" ".join(str(x) for x in scalar_values(value)))
                    for item in scalar_values(value): conn.execute("INSERT OR IGNORE INTO exact_index VALUES(?,?,?)", (field_name,norm(item),unit.unit_id))
            for item in obj.regions:
                if item.heading in unit.region_path: conn.execute("INSERT OR IGNORE INTO exact_index VALUES(?,?,?)", ("semantic_region",norm(item.heading),unit.unit_id))
            conn.execute("INSERT INTO exact_index VALUES(?,?,?)", ("parsed_text",norm(unit.parsed_text),unit.unit_id))
            conn.execute("INSERT INTO exact_index VALUES(?,?,?)", ("raw_markdown",norm(unit.raw_markdown),unit.unit_id))
            path_values=list(PurePosixPath(obj.path).parts[:-1])+list(unit.region_path)
            for value in path_values: conn.execute("INSERT OR IGNORE INTO exact_index VALUES(?,?,?)", ("semantic_path",norm(value),unit.unit_id))
            conn.execute("INSERT INTO lexical_index VALUES(?,?,?,?,?,?)", (unit.unit_id,unit.parsed_text," ".join(identifiers_text)," ".join(unit.region_path)," ".join(path_values),unit.raw_markdown))
            conn.execute("INSERT INTO graph_nodes VALUES(?,?,?)", ("unit:"+unit.unit_id,"semantic_unit",obj.path))
            region_id = next((r.region_id for r in obj.regions if tuple(r.path) == unit.region_path), None)
            parent = "region:" + region_id if region_id else object_node
            conn.execute("INSERT INTO graph_edges VALUES(?,?,?)", (parent,"unit:"+unit.unit_id,"contains_unit"))
            for relation in unit.relations:
                conn.execute("INSERT INTO relations VALUES(?,?,?,?,?,?,?)", (unit.unit_id,relation.name,relation.authored,relation.visible,relation.target_object_uuid,relation.target_region_uuid,relation.source))
    matrix=np.asarray(vectors,dtype=np.float32); matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
    np.save(staging/"vectors.npy",matrix)
    for row,(unit_id,ordinal,_) in enumerate(vector_records):
        conn.execute("INSERT INTO vector_records VALUES(?,?,?,?)", (str(uuid.uuid4()),unit_id,ordinal,row))
    conn.commit(); conn.close()
    catalog=make_catalog(objects,admitted)
    (staging/"capability_catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest={"schema_version":"1","build_configuration":json_value(config),"admitted_semantic_identifier_fields":admitted,"parser":{"markdown_it":"markdown-it-py","frontmatter":"ruamel.yaml"},"embedding":{**model_info,"normalized":True},"lexical":{"tokenizer":"unicode61","case_insensitive":True,"preserve_diacritics":True,"stemming":False,"custom_stopwords":False},"artifacts":{name:hashlib.sha256((staging/name).read_bytes()).hexdigest() for name in ["substrate.sqlite3","vectors.npy","capability_catalog.json"]}}
    (staging/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    for name in ["substrate.sqlite3","vectors.npy","capability_catalog.json","manifest.json"]:
        destination=output/name
        if destination.exists(): destination.unlink()
        shutil.move(staging/name,destination)
    staging.rmdir()
    if repair.exists(): repair.unlink()
    return 0


def make_catalog(objects: list[ObjectNote], admitted: list[str]) -> dict[str, Any]:
    values={f:set() for f in admitted}; regions=set(); paths=set(); relations=set()
    for obj in objects:
        paths.update(PurePosixPath(obj.path).parts[:-1])
        regions.update("#".join(r.path) for r in obj.regions)
        for unit in obj.units:
            for f,(state,value) in unit.identifiers.items():
                if state != "Absent": values[f].update(str(x) for x in scalar_values(value))
            relations.update(r.name for r in unit.relations)
    fields=[{"field_class":"parsed_text","values":"free text from semantic units","exact":True,"lexical":True,"vector":True}]
    fields += [{"field_class":"admitted semantic identifier","field":f,"values":sorted(v),"exact":True,"lexical":True,"vector":False} for f,v in values.items() if v]
    fields += [{"field_class":"semantic region","values":sorted(regions),"exact":True,"lexical":True,"vector":False},{"field_class":"semantic path component","values":sorted(paths),"exact":True,"lexical":True,"vector":False},{"field_class":"raw_markdown","values":"authored Markdown of semantic units","exact":True,"lexical":False,"vector":False}]
    return {"fields":fields,"relations":{"wikilink_relations":sorted(relations),"grammar":[{"relation":"linked_to","source":"semantic_unit","target":"semantic_object / semantic_region"},{"relation":"contains_scope","source":"scope","target":"scope"},{"relation":"contains_object","source":"scope","target":"semantic_object"},{"relation":"contains_region","source":"semantic_object / semantic_region","target":"semantic_region"},{"relation":"contains_unit","source":"semantic_object / semantic_region","target":"semantic_unit"}]},"operations":{"exact":["equals"],"lexical":["terms","phrase"],"vector":["semantic similarity"],"graph":["relation traversal"]}}


def main() -> int:
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    b=sub.add_parser("build"); b.add_argument("--vault",type=Path,required=True); b.add_argument("--config",type=Path,default=DEFAULT_CONFIG); b.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    if args.command=="build": return build(args.vault,args.config,args.output)
    return 1


if __name__ == "__main__": sys.exit(main())
