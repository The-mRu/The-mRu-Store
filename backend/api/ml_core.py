# backend/api/ml_core.py
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_embedding_model():
	"""Load the sentence-transformer model on first use only."""
	from sentence_transformers import SentenceTransformer

	model_name = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
	return SentenceTransformer(model_name)