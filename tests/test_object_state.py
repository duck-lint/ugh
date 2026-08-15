import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ugh_parser import (
    BuildConfig,
    canonicalize_ingest,
    hydrate_object,
    materialize_context,
    parse_vault,
    resolve_relations,
    write_completed_ingest,
)


class CanonicalObjectStateTests(unittest.TestCase):
    def _write(self, root: Path, relative: str, content: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _build(self):
        config = BuildConfig(
            "test", "uuid", (),
            ("score", "tags", "related", "other", "blank", "missing"),
        )
        directory = TemporaryDirectory()
        root = Path(directory.name)
        self._write(root, "source.md", """---
uuid: source
score: 7
tags: [one, one, two]
related:
  - "[[target#Inner|first]]"
  - "[[target#Inner|second]]"
other: "[[target#Inner|other-field]]"
blank:
---
""")
        self._write(root, "target.md", """---
uuid: target
---
# Inner
target unit
""")
        parsed = parse_vault(root, config)
        completed = canonicalize_ingest(resolve_relations(materialize_context(parsed)))
        return directory, completed

    def test_zero_unit_object_preserves_and_hydrates_authored_state(self):
        directory, completed = self._build()
        try:
            source = next(obj for obj in completed.objects if obj.source_object_uuid == "source")
            self.assertEqual(len(completed.units), 1)
            self.assertEqual(completed.units[0].source_object_uuid, "target")
            self.assertEqual([(f.name, f.state, f.value) for f in source.admitted_identifiers], [
                ("score", "present_value", 7),
                ("tags", "present_value", ["one", "one", "two"]),
                ("related", "present_value", ["[[target#Inner|first]]", "[[target#Inner|second]]"]),
                ("other", "present_value", "[[target#Inner|other-field]]"),
                ("blank", "present_blank", None),
                ("missing", "absent", None),
            ])
            self.assertEqual(len(source.regions), 0)
            self.assertEqual(len(source.relations), 3)
            self.assertEqual([relation.source_field for relation in source.relations], ["related", "related", "other"])
            self.assertTrue(all(relation.target_region is not None for relation in source.relations))
            self.assertTrue(all(not hasattr(relation, "source_local_order") for relation in source.relations))

            database = Path(directory.name) / "substrate.sqlite3"
            connection = sqlite3.connect(database)
            write_completed_ingest(connection, completed)
            connection.close()
            reopened = sqlite3.connect(database)
            self.assertEqual(hydrate_object(reopened, "source"), source)
            self.assertEqual(hydrate_object(reopened, "target"), next(
                obj for obj in completed.objects if obj.source_object_uuid == "target"
            ))
            with self.assertRaises(KeyError):
                hydrate_object(reopened, "unknown")
            self.assertEqual(reopened.execute("SELECT COUNT(*) FROM object_identifiers").fetchone()[0], 12)
            self.assertEqual(reopened.execute("SELECT COUNT(*) FROM object_relations").fetchone()[0], 3)
            self.assertEqual(reopened.execute("PRAGMA foreign_key_check").fetchall(), [])
            reopened.close()
        finally:
            directory.cleanup()

    def test_object_relational_foreign_keys_reject_invalid_provenance(self):
        directory, completed = self._build()
        try:
            connection = sqlite3.connect(":memory:")
            write_completed_ingest(connection, completed)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO object_identifiers VALUES (?, ?, ?, ?, ?)",
                    ("missing", 0, "field", "absent", None),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """INSERT INTO object_relations
                    (source_object_uuid, relation_name, origin, source_field, raw,
                     authored_target, authored_label, authored_region_fragment, source_path,
                     target_object_uuid, target_region_path_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("source", "related", "frontmatter", "related", "[[missing]]",
                     "missing", "missing", None, "source.md", "missing", None),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """INSERT INTO object_relations
                    (source_object_uuid, relation_name, origin, source_field, raw,
                     authored_target, authored_label, authored_region_fragment, source_path,
                     target_object_uuid, target_region_path_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("source", "related", "frontmatter", "related", "[[target#Missing]]",
                     "target", "target", "Missing", "source.md", "target", "[\"missing\"]"),
                )
            connection.close()
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
