from django.shortcuts import render
from django.http import JsonResponse
import json
from .services import get_all_products, send_chat_message

def catalog_view(request):
    """Renders the homepage with all products."""
    products = get_all_products()
    return render(request, 'store/catalog.html', {'products': products})

def chat_interface_view(request):
    """Renders the AI chat page."""
    return render(request, 'store/chat.html')

def api_chat_proxy(request):
    """Receives AJAX from the browser, sends it to FastAPI, and returns the AI response."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # Send to FastAPI via our service
            ai_response = send_chat_message(user_message)
            
            return JsonResponse(ai_response)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request"}, status=400)