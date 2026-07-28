# backend/api/ml_core.py
from sentence_transformers import SentenceTransformer

print("Loading AI Embedding Model (Singleton)...")
# Initialize the model exactly once here
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')