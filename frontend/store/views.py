from django.shortcuts import render, redirect
from django.http import JsonResponse
import json
import requests

from .services import FASTAPI_BASE_URL, get_all_products, send_chat_message, api_register_user, api_login_user, get_product,get_all_categories

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomRegistrationForm

def register_view(request):
    """Handles user registration."""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        payload = {"name": name, "email": email, "password": password}
        try:
            response = requests.post(f"{FASTAPI_BASE_URL}/auth/register", json=payload)
            if response.status_code == 200:
                user_data = response.json()
                # Log the user in immediately after registering
                request.session['user_id'] = user_data['id']
                request.session['user_name'] = user_data['name']
                return redirect('catalog')
            else:
                error = response.json().get('detail', 'Registration failed')
                return render(request, 'store/register.html', {'error': error})
        except Exception as e:
            return render(request, 'store/register.html', {'error': 'Server error. Please try again.'})

    return render(request, 'store/register.html')

def login_view(request):
    """Handles user login."""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        payload = {"email": email, "password": password}
        try:
            response = requests.post(f"{FASTAPI_BASE_URL}/auth/login", json=payload)
            if response.status_code == 200:
                user_data = response.json()
                # Securely establish the session
                request.session['user_id'] = user_data['id']
                request.session['user_name'] = user_data['name']
                return redirect('catalog')
            else:
                error = response.json().get('detail', 'Invalid credentials')
                return render(request, 'store/login.html', {'error': error})
        except Exception as e:
            return render(request, 'store/login.html', {'error': 'Server error. Please try again.'})

    return render(request, 'store/login.html')

def logout_view(request):
    """Clears the session and logs the user out."""
    request.session.flush()
    return redirect('catalog')

def api_chat_proxy(request):
    """Updated to force session creation so session_id is never None."""
    if request.method == "POST":
        try:
            # 1. Force session generation if guest
            if not request.session.session_key:
                request.session.create()
                request.session.save() # <-- This fixes the 'None' URL bug!
            
            session_id = request.session.session_key
            user_id = request.session.get('user_id', None)

            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # 2. Send to FastAPI
            ai_response = send_chat_message(user_message, session_id, user_id)
            return JsonResponse(ai_response, safe=False) # safe=False allows raw strings
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request"}, status=400)

#
def catalog_view(request):
    """Fetches products and real categories for the homepage."""
    all_products = get_all_products() or []
    
    # 1. Fetch real category objects from MongoDB via FastAPI
    categories = get_all_categories() or []
            
    # 2. Slice the products list to only show the first 20 as "Featured"
    featured_products = all_products[:20]

    context = {
        'products': featured_products,
        'categories': categories,
    }
    return render(request, 'store/catalog.html', context)

def chat_interface_view(request):
    """Renders the AI chat page."""
    return render(request, 'store/chat.html')

def product_detail_view(request, product_id):
    """Fetches a single product's details for the product page."""
    # In a production app, you would fetch just the single product from FastAPI
    # For now, we filter it from the main list
    all_products = get_all_products() or []
    
    product = next((p for p in all_products if str(p.get('id')) == str(product_id)), None)
    
    if not product:
        # If someone types a bad URL, send them back home
        return redirect('catalog')
        
    context = {
        'product': product
    }
    return render(request, 'store/product_detail.html', context)


def cart_view(request):
    """Renders the shopping cart page and passes product data for JS to map."""
    all_products = get_all_products() or []
    
    # Create a dictionary mapped by string IDs so JavaScript can easily look up items
    product_dict = {str(p.get('id')): p for p in all_products}
    
    context = {
        # json.dumps converts the Python dictionary safely into a JSON string
        'products_json': json.dumps(product_dict)
    }
    return render(request, 'store/cart.html', context)


def sync_cart_api(request):
    """Bridging view for frontend JavaScript to sync the cart."""
    user_id = request.session.get('user_id')
    
    # If they are a guest, tell JavaScript to just use localStorage
    if not user_id:
        return JsonResponse({"error": "Guest user"}, status=401)

    # If saving to database (POST)
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            items = data.get("items", [])
            
            payload = {"user_id": user_id, "items": items}
            response = requests.post(f"{FASTAPI_BASE_URL}/cart/sync", json=payload)
            return JsonResponse(response.json())
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # If loading from database (GET)
    elif request.method == "GET":
        try:
            response = requests.get(f"{FASTAPI_BASE_URL}/cart/{user_id}")
            if response.status_code == 200:
                return JsonResponse(response.json())
            return JsonResponse({"items": []})
        except Exception:
            return JsonResponse({"items": []})
        
def search_view(request):
    """Handles smart keyword searches, sidebar links, and custom price ranges."""
    query = request.GET.get('q', '').strip().lower()
    category_id = request.GET.get('category', '')
    price_filter = request.GET.get('price', '')
    
    # NEW: Get custom price inputs
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')

    all_products = get_all_products() or []
    results = all_products

    # 1. Category Filter
    if category_id:
        results = [p for p in results if str(p.get('categoryId', '')) == category_id or str(p.get('category', '')) == category_id]

    # 2. Smart Search (Keyword Matching)
    if query:
        query_words = query.split()
        filtered_results = []
        for p in results:
            searchable_text = (p.get('name', '') + ' ' + p.get('description', '')).lower()
            if all(word in searchable_text for word in query_words):
                filtered_results.append(p)
        results = filtered_results

    # 3. Pre-set Price Filter Links
    if price_filter:
        try:
            if price_filter == 'under_500':
                results = [p for p in results if float(p.get('price', 0)) < 500]
            elif price_filter == '500_2000':
                results = [p for p in results if 500 <= float(p.get('price', 0)) <= 2000]
            elif price_filter == '2000_5000':
                results = [p for p in results if 2000 <= float(p.get('price', 0)) <= 5000]
            elif price_filter == 'over_5000':
                results = [p for p in results if float(p.get('price', 0)) > 5000]
        except ValueError:
            pass 

    # 4. NEW: Custom Price Range Filter
    if min_price or max_price:
        filtered_by_custom = []
        for p in results:
            try:
                p_price = float(p.get('price', 0))
                # If they left a box blank, assume 0 for min, or infinity for max
                min_val = float(min_price) if min_price else 0.0
                max_val = float(max_price) if max_price else float('inf')
                
                if min_val <= p_price <= max_val:
                    filtered_by_custom.append(p)
            except ValueError:
                continue
        results = filtered_by_custom

    context = {
        'query': request.GET.get('q', ''),
        'category_id': category_id,
        'price_filter': price_filter,
        'min_price': min_price,
        'max_price': max_price,
        'results': results,
        'result_count': len(results)
    }
    return render(request, 'store/search.html', context)

def checkout_view(request):
    """Renders the checkout page. Restricted to logged-in users."""
    if 'user_id' not in request.session:
        # Kick unauthorized users back to the login page
        return redirect('login')
    
    return render(request, 'store/checkout.html')

def place_order_api(request):
    """Bridge view to securely place an order via FastAPI."""
    if request.method == "POST":
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        
        try:
            data = json.loads(request.body)
            payload = {
                "user_id": user_id,
                "items": data.get("items", []),
                "shipping": data.get("shipping", {}),
                "total": data.get("total", 0.0)
            }
            
            response = requests.post(f"{FASTAPI_BASE_URL}/orders/place", json=payload)
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid method"}, status=405)

def order_success_view(request):
    """Renders the professional order confirmation page."""
    return render(request, 'store/order_success.html')