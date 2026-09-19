"""Product catalog and product-scoped RAG regression tests."""
from pathlib import Path
import unittest
from unittest.mock import Mock

import main  # Initialize project/SDK import separation.

from my_project.products.catalog import list_products, resolve_product
from my_project.rag.loader import KNOWLEDGE_DIR, load_knowledge_chunks
from my_project.rag.retriever import search_knowledge


class ConstantEncoder:
    def encode(self, _text):
        return [1.0, 0.0]


class ProductCatalogRagTests(unittest.TestCase):
    def test_catalog_contains_only_the_three_supported_products(self):
        products = list_products()

        self.assertEqual(
            {item.product_id for item in products},
            {"anker-prime-250w", "anker-nano-70w", "soundcore-liberty-4-nc"},
        )
        self.assertEqual(resolve_product("A2345").rag_namespace, "anker_prime_250w")
        self.assertEqual(resolve_product("A121A").rag_namespace, "anker_nano_70w")
        self.assertEqual(resolve_product("Liberty 4 NC").rag_namespace, "liberty_4_nc")

    def test_every_chunk_has_required_product_metadata(self):
        chunks = load_knowledge_chunks()

        self.assertTrue(chunks)
        for chunk in chunks:
            with self.subTest(source=chunk["source"]):
                for field in ("product_id", "category", "issue_type", "source_type"):
                    self.assertTrue(chunk[field])
                self.assertEqual(chunk["source_type"], "official_support")

    def assert_only_namespace(self, result: str, namespace: str):
        sources = [line[9:-1] for line in result.splitlines() if line.startswith("[Source: ")]
        self.assertTrue(sources)
        self.assertTrue(all(source.startswith(f"{namespace}/") for source in sources))

    def test_prime_display_query_returns_only_prime_chunks(self):
        result = search_knowledge(
            "clock display screensaver does not appear",
            ConstantEncoder(),
            top_k=20,
            product_id="anker-prime-250w",
        )

        self.assert_only_namespace(result, "anker_prime_250w")
        self.assertIn("anker_prime_250w/display_clock.md", result)
        self.assertNotIn("indicator light", result.casefold())

    def test_nano_power_query_returns_only_nano_chunks(self):
        result = search_knowledge(
            "why does charging slow down with multiple ports",
            ConstantEncoder(),
            top_k=20,
            product="Anker Nano 70W",
        )

        self.assert_only_namespace(result, "anker_nano_70w")
        self.assertIn("anker_nano_70w/power_distribution.md", result)
        self.assertNotIn("clock screensaver", result.casefold())
        self.assertNotIn("wi-fi", result.casefold())

    def test_liberty_pairing_query_returns_only_earbud_chunks(self):
        result = search_knowledge(
            "earbuds will not pair reset both sides",
            ConstantEncoder(),
            top_k=20,
            product="A3947",
        )

        self.assert_only_namespace(result, "liberty_4_nc")
        self.assertIn("liberty_4_nc/pairing_reset.md", result)
        self.assertNotIn("70W", result)
        self.assertNotIn("140W", result)

    def test_unknown_product_returns_no_knowledge_or_embedding_work(self):
        encoder = Mock()

        result = search_knowledge("charging help", encoder, product="Unknown Device")

        self.assertEqual(result, "")
        encoder.encode.assert_not_called()

    def test_legacy_flat_knowledge_files_are_absent(self):
        self.assertEqual(list(KNOWLEDGE_DIR.glob("*.md")), [])
        self.assertEqual(
            {path.parent.name for path in KNOWLEDGE_DIR.glob("*/*.md")},
            {"anker_prime_250w", "anker_nano_70w", "liberty_4_nc"},
        )


if __name__ == "__main__":
    unittest.main()
