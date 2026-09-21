import numpy as np
from functools import lru_cache
from threading import Lock
from sentence_transformers import SentenceTransformer


_embedding_lock = Lock()


@lru_cache(maxsize=1)
def _create_embedding_model_cached():
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


def create_embedding_model():
    """Initialize the large local model only once, including concurrent first calls."""
    with _embedding_lock:
        return _create_embedding_model_cached()


create_embedding_model.cache_clear = _create_embedding_model_cached.cache_clear

def cosine_similarity(a, b):
    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )
