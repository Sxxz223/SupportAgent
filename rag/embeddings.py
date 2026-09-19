import numpy as np
from functools import lru_cache
from sentence_transformers import SentenceTransformer

@lru_cache(maxsize=1)
def create_embedding_model():
    embedding_model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    return embedding_model

def cosine_similarity(a, b):
    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )
