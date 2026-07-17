import requests
import logging

# Point this to your FastAPI server
FASTAPI_BASE_URL = "http://127.0.0.1:8000"
logger = logging.getLogger(__name__)

def get_all_products():
    """Fetches the catalog from FastAPI."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/products/")
        response.raise_for_status() # Raises an error if the status is 4xx or 5xx
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Could not connect to FastAPI: {e}")
        return [] # Return an empty list if the backend is down

def send_chat_message(message: str):
    """Sends a message to the FastAPI AI Chatbot."""
    try:
        # Assuming your FastAPI expects a JSON payload like {"message": "..."}
        # Adjust the payload based on your exact FastAPI /chat endpoint design
        response = requests.post(f"{FASTAPI_BASE_URL}/chat/", json={"message": message})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Chatbot offline: {e}")
        return {"response": "Sorry, the AI assistant is currently offline."}