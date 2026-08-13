import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ugh_parser import parse_note


ROOT = Path(__file__).parents[1]


class SingleNoteParserTests(unittest.TestCase):
    def test_fixture_has_object_regions_and_markdown_blocks(self):
        parsed = parse_note(
            ROOT / "docs/07_Tuesday.md",
            vault_root=ROOT / "docs",
            semantic_identifier_fields=["uuid", "note_type", "architect_or_operator", "book_read_today"],
        )
        self.assertEqual(parsed.semantic_object.uuid, "019d6d8f-8b3c-752d-b2c8-5936367992bf")
        self.assertEqual(len(parsed.regions), 4)
        self.assertEqual(len(parsed.units), 6)
        self.assertEqual(parsed.semantic_object.authored_path, "07_Tuesday.md")
        self.assertEqual(parsed.units[0].region_path, ("region-0001",))
        self.assertEqual(parsed.units[-1].region_path, ("region-0004",))
        self.assertTrue(all(unit.source_object_uuid == parsed.semantic_object.uuid for unit in parsed.units))
        self.assertEqual([region.heading for region in parsed.regions], ["Dream Recall:", "Yesterday Review:", "Daily Intent:", "Freeform Journaling:"])

    def test_raw_markdown_and_visible_parsed_text_are_distinct(self):
        parsed = parse_note(ROOT / "docs/07_Tuesday.md", semantic_identifier_fields=[])
        unit = parsed.units[0]
        self.assertIn("[[mission]]", unit.raw_markdown)
        self.assertIn("mission", unit.parsed_text)
        self.assertNotIn("[[mission]]", unit.parsed_text)
        self.assertEqual(unit.wikilinks[0].target, "mission")
        self.assertEqual(unit.wikilinks[0].label, "mission")

    def test_admitted_absence_and_blank_are_distinct(self):
        parsed = parse_note(ROOT / "docs/07_Tuesday.md", semantic_identifier_fields=["architect_or_operator", "missing"])
        states = {field.name: field.state for field in parsed.semantic_object.admitted_fields}
        self.assertEqual(states["architect_or_operator"], "present_blank")
        self.assertEqual(states["missing"], "absent")

    def test_block_parser_defines_units_for_non_paragraph_blocks(self):
        source = """---\nuuid: test-object\n---\n# Scope\n\n- first\n- second\n\n```python\nprint('third')\n```\n\n| a | b |\n|---|---|\n| c | d |\n"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            path.write_text(source, encoding="utf-8")
            parsed = parse_note(path, semantic_identifier_fields=[])
        self.assertEqual(len(parsed.units), 3)
        self.assertEqual(parsed.units[0].parsed_text, "firstsecond")
        self.assertIn("print('third')", parsed.units[1].parsed_text)
        self.assertIn("a", parsed.units[2].parsed_text)


if __name__ == "__main__":
    unittest.main()
