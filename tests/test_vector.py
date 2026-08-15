import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from ugh_parser import (
    EmbeddingContract,
    EmbeddingProviderError,
    VectorError,
    VectorTarget,
    build_vector_index,
    segment_and_embed,
    validate_vector_index,
    vector_eligible_targets,
    vector_lookup,
)
from ugh_parser.substrate import SCHEMA


class ProviderDouble:
    def __init__(self, capacity=5, identity="test-provider"):
        self.contract = EmbeddingContract("test-model", identity, 1024, "float32", "l2", "cosine", capacity)
        self.calls = []

    def embed(self, text, *, truncate=False):
        self.calls.append((text, truncate))
        if truncate:
            raise AssertionError("tests must not request provider truncation")
        if len(text) > self.contract.input_capacity:
            raise EmbeddingProviderError("provider context capacity", capacity_exceeded=True)
        vector = np.zeros(1024, dtype=np.float32)
        vector[hash(text) % 1023] = 1.0
        vector[1023] = 1.0
        return vector


class VectorProjectionTests(unittest.TestCase):
    def _connection(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO canonical_objects VALUES (?, ?, ?)",
            [("unit-object", "Unit.md", 0), ("zero-object", "folder/Zero.md", 1), ("empty-object", "Empty.md", 2)],
        )
        connection.execute(
            "INSERT INTO canonical_units VALUES (?, ?, ?, ?, ?, ?)",
            (1, "unit-object", "Unit.md", 1, "raw", "alpha unit text"),
        )
        connection.execute(
            "INSERT INTO canonical_units VALUES (?, ?, ?, ?, ?, ?)",
            (2, "empty-object", "Empty.md", 1, "raw", ""),
        )
        return connection

    def test_targets_are_exact_units_or_zero_unit_object_names(self):
        connection = self._connection()
        self.assertEqual(
            vector_eligible_targets(connection),
            (
                VectorTarget("semantic_unit", 1, "alpha unit text"),
                VectorTarget("semantic_object", "zero-object", "Zero"),
            ),
        )

    def test_provider_confirmed_fallback_preserves_code_points(self):
        provider = ProviderDouble(capacity=3)
        source = "abcdefgh"
        segments = segment_and_embed(provider, source)
        self.assertEqual("".join(text for text, _ in segments), source)
        self.assertEqual([text for text, _ in segments], ["abc", "def", "gh"])
        self.assertTrue(all(truncate is False for _, truncate in provider.calls))

    def test_build_persists_float32_vectors_and_reopens(self):
        connection = self._connection()
        provider = ProviderDouble(capacity=100)
        with TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "vectors.npy"
            build_vector_index(connection, matrix_path, provider)
            validate_vector_index(connection, matrix_path)
            matrix = np.load(matrix_path, allow_pickle=False)
            self.assertEqual(matrix.dtype, np.float32)
            self.assertEqual(matrix.shape, (2, 1024))
            self.assertEqual(
                connection.execute("SELECT target_kind, target_identity_json FROM vector_segments ORDER BY matrix_row").fetchall(),
                [("semantic_unit", "1"), ("semantic_object", '"zero-object"')],
            )
            reopened = sqlite3.connect(":memory:")
            connection.backup(reopened)
            validate_vector_index(reopened, matrix_path)
            hits = vector_lookup(reopened, matrix_path, "query", provider)
            self.assertEqual({(hit.target_kind, hit.target_identity) for hit in hits}, {("semantic_unit", 1), ("semantic_object", "zero-object")})

    def test_provider_contract_mismatch_is_rejected(self):
        connection = self._connection()
        provider = ProviderDouble(capacity=100)
        with TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "vectors.npy"
            build_vector_index(connection, matrix_path, provider)
            mismatch = ProviderDouble(capacity=100, identity="different-provider")
            with self.assertRaises(VectorError):
                vector_lookup(connection, matrix_path, "query", mismatch)
