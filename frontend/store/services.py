import requests
import logging

# Point this to your FastAPI server
FASTAPI_BASE_URL = "http://127.0.0.1:8000"
logger = logging.getLogger(__name__)

def get_all_products():
    """Fetches the catalog from FastAPI."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/products/")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Could not connect to FastAPI: {e}")
        return [] 

def send_chat_message(message: str, session_id: str, user_id: str = None):
    """Sends a message to the FastAPI AI Chatbot with session and user tracking."""
    
    # 1. Base JSON payload
    payload = {"message": message}
    
    # 2. If the user is logged into Django, attach their ID to the payload
    if user_id:
        payload["user_id"] = user_id

    try:
        # 3. Hit the exact FastAPI endpoint: /chat/{session_id}
        response = requests.post(f"{FASTAPI_BASE_URL}/chat/{session_id}", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Chatbot offline: {e}")
        return {"reply": "Sorry, the AI assistant is currently offline."}
    

def api_register_user(name, email, password):
    """Sends registration data to FastAPI (MongoDB)."""
    try:
        # Match your MongoDB schema attributes
        payload = {
            "name": name,
            "email": email,
            "password": password,
            "role": "customer",
            "isVerified": False,
            "isActive": True
        }
        # Assuming your FastAPI endpoint is POST /users/register
        response = requests.post(f"{FASTAPI_BASE_URL}/users/register", json=payload)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as e:
        logger.error(f"Registration failed: {e}")
        return None, "Email might already exist or backend is unreachable."

def api_login_user(email, password):
    """Verifies user credentials against FastAPI (MongoDB)."""
    try:
        payload = {"email": email, "password": password}
        # Assuming your FastAPI endpoint is POST /users/login
        response = requests.post(f"{FASTAPI_BASE_URL}/users/login", json=payload)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as e:
        logger.error(f"Login failed: {e}")
        return None, "Invalid email or password."
    
def get_product(product_id: str):
    """Fetches a single product from FastAPI by its ID."""
    try:
        response = requests.get(f"{FASTAPI_BASE_URL}/products/{product_id}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Could not fetch product {product_id}: {e}")
        return None
    
def get_all_categories():
    """Fetches all categories from the FastAPI backend."""
    try:
        # Assuming your main.py includes this router with prefix="/categories"
        response = requests.get(f"{FASTAPI_BASE_URL}/categories/")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error connecting to FastAPI Categories: {e}")
        return []