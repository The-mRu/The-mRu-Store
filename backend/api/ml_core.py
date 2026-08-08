# backend/api/ml_core.py
import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import HTTPException
from openai import AsyncOpenAI

load_dotenv()


@lru_cache(maxsize=1)
def get_openai_client():
	"""Create one OpenAI client per process and reuse it."""
	api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_ADMIN_KEY")
	if not api_key:
		raise HTTPException(
			status_code=503,
			detail="OPENAI_API_KEY is missing. Add it to your environment or .env file."
		)
	return AsyncOpenAI(api_key=api_key)


async def get_embedding(text: str) -> list[float]:
	"""Fetch an embedding from OpenAI instead of loading a local model."""
	client = get_openai_client()
	model_name = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
	response = await client.embeddings.create(model=model_name, input=text)
	return response.data[0].embedding