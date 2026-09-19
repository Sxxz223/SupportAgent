import re

from ..products.catalog import get_product, resolve_product
from .loader import load_knowledge_chunks
from .embeddings import cosine_similarity

def tokenize(text: str) -> set[str]:
    """
    最简单的关键词切分。
    这里只用于学习 Retrieval 的结构。
    """
    return set(
        re.findall(
            r"[a-zA-Z0-9']+",
            text.lower()
        )
    )

def search_knowledge(
    query: str,
    embedding_model,
    top_k: int = 3,
    product: str | None = None,
    product_id: str | None = None,
) -> str:
    catalog_product = get_product(product_id) if product_id else resolve_product(product)
    if catalog_product is None:
        return ""

    chunks = [
        chunk for chunk in load_knowledge_chunks()
        if chunk["product_id"] == catalog_product.product_id
        and chunk["rag_namespace"] == catalog_product.rag_namespace
    ]

    # Query → Vector
    query_vector = embedding_model.encode(query)

    scored_chunks = []

    for chunk in chunks:

        # Chunk → Vector
        chunk_vector = embedding_model.encode(
            chunk["text"]
        )

        score = cosine_similarity(
            query_vector,
            chunk_vector
        )

        scored_chunks.append(
            (score, chunk)
        )

    scored_chunks.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    top_chunks = scored_chunks[:top_k]

    results = []

    for score, chunk in top_chunks:

        results.append(
            f"[Score: {score:.3f}]\n"
            f"[Source: {chunk['source']}]\n"
            f"{chunk['text']}"
        )

    return "\n\n".join(results)
