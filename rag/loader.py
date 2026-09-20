"""Load product-scoped Markdown knowledge with compact metadata."""
import re
from pathlib import Path

from products.catalog import list_products


KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    closing = text.find("\n---\n", 4)
    if closing == -1:
        return {}, text
    metadata = {}
    for line in text[4:closing].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip()
    return metadata, text[closing + 5:]


def load_knowledge_chunks() -> list[dict]:
    chunks = []
    products_by_namespace = {item.rag_namespace: item for item in list_products()}

    for file_path in sorted(KNOWLEDGE_DIR.glob("*/*.md")):
        product = products_by_namespace.get(file_path.parent.name)
        if product is None:
            continue
        metadata, text = _frontmatter(file_path.read_text(encoding="utf-8"))
        sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        for section in sections:
            section = section.strip()
            if not section:
                continue
            chunks.append({
                "source": file_path.relative_to(KNOWLEDGE_DIR).as_posix(),
                "text": section,
                "product_id": product.product_id,
                "product_model": product.model,
                "category": product.category,
                "rag_namespace": product.rag_namespace,
                "issue_type": metadata.get("issue_type", file_path.stem),
                "source_type": metadata.get("source_type", "official_support"),
                "source_title": metadata.get("source_title", ""),
                "source_url": metadata.get("source_url", ""),
            })
    return chunks
