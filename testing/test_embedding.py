import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load your existing API key
load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def test_magic():
    # 1. The word we want the AI to understand
    text = "fleece winter jacket"
    print(f"Asking OpenAI to translate: '{text}'...")

    # 2. Ask OpenAI to translate the text into a mathematical vector
    response = await client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )

    # 3. Extract the array of numbers from the response
    numbers = response.data[0].embedding

    # 4. Print the results to see what an "embedding" actually looks like
    print(f"\nSuccess! OpenAI turned your text into {len(numbers)} numbers.")
    print(f"Here are the first 5 numbers: {numbers[:5]}")

if __name__ == "__main__":
    asyncio.run(test_magic())