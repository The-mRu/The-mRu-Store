from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage

import json
import requests
import os
from datetime import datetime

from pymongo import MongoClient
from bson.objectid import ObjectId  
import uuid
from bson.objectid import ObjectId

from .services import (
    FASTAPI_BASE_URL,
    get_all_products,
    send_chat_message,
    api_register_user,
    api_login_user,
    get_product,
    get_all_categories,
)
from .forms import CustomRegistrationForm





# Initialize MongoDB Connection
client = MongoClient('mongodb://localhost:27017/')
db = client['amazon_clone_db']
orders_collection = db['Orders']
order_items_collection = db['OrderItems']
carts_collection = db['Carts']
products_collection = db['Products']
cart_items_collection = db['CartItems']


 


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

# def product_detail_view(request, product_id):
#     """Fetches a single product's details for the product page."""
#     # In a production app, you would fetch just the single product from FastAPI
#     # For now, we filter it from the main list
#     all_products = get_all_products() or []
    
#     product = next((p for p in all_products if str(p.get('id')) == str(product_id)), None)
    
#     if not product:
#         # If someone types a bad URL, send them back home
#         return redirect('catalog')
        
#     context = {
#         'product': product
#     }
#     return render(request, 'store/product_detail.html', context)

from bson.objectid import ObjectId
from django.http import Http404

def product_detail_view(request, product_id):
    # Try to find product by its string 'id' field first
    product = db['Products'].find_one({"id": product_id})
    if not product:
        # If not, try by MongoDB _id (converted to ObjectId)
        try:
            product = db['Products'].find_one({"_id": ObjectId(product_id)})
        except:
            pass
    if not product:
        raise Http404("Product not found")

    # Convert _id to string for use in templates and URLs
    product['id'] = str(product['_id'])

    # Get related products from the same category (if categoryId exists)
    related_products = []
    if product.get('categoryId'):
        related = db['Products'].find({
            "categoryId": product['categoryId'],
            "_id": {"$ne": product['_id']}
        }).limit(4)
        for p in related:
            p['id'] = str(p['_id'])
            related_products.append(p)

    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'store/product_detail.html', context)
import json

def cart_view(request):
    """Renders the shopping cart page and passes product data for JS to map."""
    all_products = list(products_collection.find({})) 
    
    product_dict = {}
    for p in all_products:
        # 1. Safely convert MongoDB _id to string
        p['_id'] = str(p.get('_id'))
        
        # 2. Prevent json.dumps crashes by stringifying dates
        if 'createdAt' in p:
            p['createdAt'] = str(p['createdAt'])
        if 'updatedAt' in p:
            p['updatedAt'] = str(p['updatedAt'])
            
        # 3. DOUBLE-KEY TRICK: Save the product under BOTH IDs
        str_id = p.get('id')
        mongo_id = p['_id']
        
        # If JS asks for the custom string ID, it finds it:
        if str_id:
            product_dict[str_id] = p
            
        # If JS asks for the MongoDB _id, it ALSO finds it:
        if mongo_id:
            product_dict[mongo_id] = p
            
    context = {
        'products_json': json.dumps(product_dict)
    }
    return render(request, 'store/cart.html', context)

def cart_sync_view(request):
    # Grab the current active user from the Django session profile
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'items': []}, status=200) # Silent fallback for anonymous guests

    # Ensure a master Cart document exists for this user profile
    cart = carts_collection.find_one({"userId": user_id})
    if not cart:
        cart_id = str(uuid.uuid4())
        carts_collection.insert_one({
            "id": cart_id,
            "userId": user_id,
            "totalAmount": 0.0,
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        })
    else:
        cart_id = cart.get('id')

    # --- HANDLE GET REQUEST: Pull cart data from MongoDB to the browser ---
    if request.method == 'GET':
        db_items = list(cart_items_collection.find({"cartId": cart_id}))
        
        # Format database rows to match local JavaScript properties
        formatted_items = [
            {"productId": item.get("productId"), "quantity": item.get("quantity", 1)}
            for item in db_items
        ]
        return JsonResponse({'items': formatted_items}, status=200)

    # --- HANDLE POST REQUEST: Push browser storage states down to MongoDB ---
    elif request.method == 'POST':
        try:
            payload = json.loads(request.body)
            browser_items = payload.get('items', [])

            # Clear older cached items to write the current cart batch fresh
            cart_items_collection.delete_many({"cartId": cart_id})

            total_amount = 0.0
            
            for item in browser_items:
                product_id = item.get('productId')
                quantity = int(item.get('quantity', 1))
                
                # --- BULLETPROOF FIX: Check both "id" and "_id" ---
                query = [{"id": product_id}]
                # If the JS sent a 24-character MongoDB ObjectId, add it to the search
                if product_id and len(str(product_id)) == 24:
                    query.append({"_id": ObjectId(product_id)})
                
                product = products_collection.find_one({"$or": query})
                # --------------------------------------------------

                unit_price = float(product.get('price', 0)) if product else 0.0
                total_price = unit_price * quantity
                total_amount += total_price

                cart_items_collection.insert_one({
                    "id": str(uuid.uuid4()),
                    "cartId": cart_id,
                    "productId": product_id,
                    "variantId": None,
                    "quantity": quantity,
                    "unitPrice": unit_price,
                    "totalPrice": total_price,
                    "createdAt": datetime.utcnow()
                })

            # Update the master Cart record with the new total sum
            carts_collection.update_one(
                {"id": cart_id},
                {"$set": {"totalAmount": total_amount, "updatedAt": datetime.utcnow()}}
            )
            return JsonResponse({'status': 'synchronized'}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


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
        



# Initialize MongoDB Connection (You can also move this to settings.py)
client = MongoClient('mongodb://localhost:27017/')
db = client['amazon_clone_db']
products_collection = db['Products']
brands_collection = db['Brands']

def search_view(request):
    # 1. Grab all the filter parameters from the URL
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    brand_id = request.GET.get('brand', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    price_preset = request.GET.get('price', '')

    # 2. Build the MongoDB Query Dictionary
    mongo_query = {}

    # Text Search (Looks in name OR description using Regex)
    if query:
        mongo_query["$or"] = [
            {"name": {"$regex": query, "$options": "i"}}, # "i" means case-insensitive
            {"description": {"$regex": query, "$options": "i"}}
        ]

    # Category Filter
    if category_id:
        mongo_query["categoryId"] = category_id

    # Brand Filter
    if brand_id:
        mongo_query["brandId"] = brand_id

    # Custom Price Range
    if min_price or max_price:
        price_filter = {}
        if min_price:
            price_filter["$gte"] = float(min_price)
        if max_price:
            price_filter["$lte"] = float(max_price)
        mongo_query["price"] = price_filter

    # Sidebar Price Presets
    if price_preset == 'under_500':
        mongo_query["price"] = {"$lt": 500}
    elif price_preset == '500_2000':
        mongo_query["price"] = {"$gte": 500, "$lte": 2000}
    elif price_preset == '2000_5000':
        mongo_query["price"] = {"$gte": 2000, "$lte": 5000}
    elif price_preset == 'over_5000':
        mongo_query["price"] = {"$gt": 5000}

    # 3. Execute the Query
    # We convert the cursor to a list so we can easily pass it to the Django template
    results = list(products_collection.find(mongo_query))
    
    # --- ADDED FIX: Convert MongoDB '_id' to string 'id' for the template ---
    for product in results:
        if 'id' not in product:
            product['id'] = str(product.get('_id'))
    # -------------------------------------------------------------------------
    
    # 4. Package everything up to send to our HTML template
    context = {
        'results': results,
        'result_count': len(results),
        'query': query,
        'category_id': category_id,
        'brand_id': brand_id,
        'min_price': min_price,
        'max_price': max_price,
        'price_filter': price_preset,
    }
    
    return render(request, 'store/search.html', context)

def checkout_view(request):
    """Renders the checkout page. Restricted to logged-in users."""
    if 'user_id' not in request.session:
        # Kick unauthorized users back to the login page
        return redirect('login')

    # 1. Fetch fresh directly from the DB to bypass any caching delays
    all_products = list(products_collection.find({})) 
    
    product_dict = {}
    for p in all_products:
        # 2. Safely convert MongoDB _id to string
        p['_id'] = str(p.get('_id'))
        
        # 3. Prevent json.dumps crashes by stringifying dates
        if 'createdAt' in p:
            p['createdAt'] = str(p['createdAt'])
        if 'updatedAt' in p:
            p['updatedAt'] = str(p['updatedAt'])
            
        # 4. DOUBLE-KEY TRICK: Save the product under BOTH IDs
        str_id = p.get('id')
        mongo_id = p['_id']
        
        if str_id:
            product_dict[str_id] = p
        if mongo_id:
            product_dict[mongo_id] = p

    return render(request, 'store/checkout.html', {
        'products_json': json.dumps(product_dict)
    })

def place_order_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        # 1. Parse incoming checkout payload from our frontend JS script
        data = json.loads(request.body)
        items = data.get('items', [])
        shipping_data = data.get('shipping', {})
        total_amount = data.get('total', 0)
        
        user_id = request.session.get('user_id', 'guest')
        
        if not items:
            return JsonResponse({'error': 'No items found in order payload'}, status=400)
            
        # 2. Generate Unique Structural Tracking Elements
        order_id = str(uuid.uuid4())
        order_number = f"MRU-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # 3. Create the Master Order Document matching your collection attributes
        order_document = {
            "id": order_id,
            "orderNumber": order_number,
            "userId": user_id,
            "addressData": shipping_data, 
            "paymentId": f"PAY-{uuid.uuid4().hex[:8].upper()}", 
            "subtotal": float(total_amount) - 120.00, 
            "discount": 0.0,
            "shippingFee": 120.0,
            "totalAmount": float(total_amount),
            "status": "Pending",
            "paymentStatus": "Unpaid",
            "orderedAt": datetime.utcnow(),
            "deliveredAt": None
        }
        
        # Insert Master Order
        orders_collection.insert_one(order_document)
        
        # 4. Loop through specific checkout items and insert into OrderItems mapping
        for item in items:
            product_id = item.get('productId')
            quantity = int(item.get('quantity', 1))
            
            # --- BULLETPROOF FIX: Check both "id" and "_id" ---
            query = [{"id": product_id}]
            if product_id and len(str(product_id)) == 24:
                query.append({"_id": ObjectId(product_id)})
            
            product = products_collection.find_one({"$or": query})
            # --------------------------------------------------

            # Ensure we default to 0.0, not 500.00, if something genuinely goes missing
            unit_price = float(product.get('price', 0.0)) if product else 0.0
            
            order_item_document = {
                "id": str(uuid.uuid4()),
                "orderId": order_id,
                "productId": product_id,
                "variantId": None,
                "quantity": quantity,
                "unitPrice": unit_price,
                "totalPrice": unit_price * quantity
            }
            order_items_collection.insert_one(order_item_document)
            
        # 5. Reset persistence layer state for the specific User Cart profile
        if user_id != 'guest':
            carts_collection.update_one(
                {"userId": user_id},
                {"$set": {"totalAmount": 0.0, "updatedAt": datetime.utcnow()}}
            )
            
        return JsonResponse({'status': 'success', 'orderNumber': order_number}, status=200)
        
    except Exception as e:
        print(f"Database error executing order batch: {str(e)}")
        return JsonResponse({'error': 'Internal server pipeline failure'}, status=500)

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











def dashboard_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    # ==========================================
    # HANDLE ALL FORM SUBMISSIONS (POST)
    # ==========================================
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        # 1. Update Profile (including profile picture)
        if form_type == 'update_profile':
            new_name = request.POST.get('full_name')
            
            # Prepare update data
            update_data = {
                "name": new_name,
                "phone": request.POST.get('phone'),
                "dateOfBirth": request.POST.get('dob'),
                "gender": request.POST.get('gender'),
                "updatedAt": datetime.now()
            }

            # Handle profile picture upload
            if 'profile_image' in request.FILES:
                uploaded_file = request.FILES['profile_image']
                
                # Optional: validate file size (max 2MB)
                if uploaded_file.size > 2 * 1024 * 1024:
                    # You could add a message here, but we'll just ignore for now
                    pass
                
                # Save the file using Django's FileSystemStorage
                fs = FileSystemStorage()
                # Generate unique filename to avoid collisions
                ext = os.path.splitext(uploaded_file.name)[1]
                filename = f"profile_{user_id}_{int(datetime.now().timestamp())}{ext}"
                saved_name = fs.save(os.path.join('profile_pics', filename), uploaded_file)
                # Store the URL in the database
                update_data['profileImage'] = fs.url(saved_name)

            # Update the user document in MongoDB
            db['Users'].update_one(
                {"id": user_id},
                {"$set": update_data}
            )
            
            if new_name:
                request.session['user_name'] = new_name
                
            return redirect('/dashboard/?tab=settings')

        # 2. Add Address
        elif form_type == 'add_address':
            is_default = request.POST.get('is_default') == 'on'
            new_address = {
                "userId": user_id,
                "fullName": request.POST.get('address_name'),
                "phone": request.POST.get('address_phone'),
                "street": request.POST.get('street'),
                "area": request.POST.get('area'),
                "city": request.POST.get('city'),
                "postalCode": request.POST.get('postal_code'),
                "isDefault": is_default,
                "createdAt": datetime.now()
            }
            if is_default:
                db['Addresses'].update_many(
                    {"userId": user_id},
                    {"$set": {"isDefault": False}}
                )
            db['Addresses'].insert_one(new_address)
            return redirect('/dashboard/?tab=settings')

        # 3. Edit Address
        elif form_type == 'edit_address':
            address_id = request.POST.get('address_id')
            is_default = request.POST.get('is_default') == 'on'
            update_data = {
                "fullName": request.POST.get('address_name'),
                "phone": request.POST.get('address_phone'),
                "street": request.POST.get('street'),
                "area": request.POST.get('area'),
                "city": request.POST.get('city'),
                "postalCode": request.POST.get('postal_code'),
                "isDefault": is_default,
                "updatedAt": datetime.now()
            }
            if is_default:
                db['Addresses'].update_many(
                    {"userId": user_id},
                    {"$set": {"isDefault": False}}
                )
            db['Addresses'].update_one(
                {"_id": ObjectId(address_id), "userId": user_id},
                {"$set": update_data}
            )
            return redirect('/dashboard/?tab=settings')

        # 4. Delete Address
        elif form_type == 'delete_address':
            address_id = request.POST.get('address_id')
            if address_id:
                db['Addresses'].delete_one({
                    "_id": ObjectId(address_id),
                    "userId": user_id
                })
            return redirect('/dashboard/?tab=settings')

    # ==========================================
    # GET: BUILD CONTEXT FOR RENDER
    # ==========================================
    active_tab = request.GET.get('tab', 'profile')
    context = {
        'active_tab': active_tab,
        'user_name': request.session.get('user_name', 'User'),
    }

    # --- ALWAYS FETCH USER PROFILE (for sidebar and settings) ---
    user_profile = db['Users'].find_one({"id": user_id})
    if user_profile:
        user_profile.pop('password', None)  # remove sensitive data
    context['profile'] = user_profile

    # --- TAB-SPECIFIC DATA ---
    if active_tab == 'profile':
        # Overview counts
        context['total_orders'] = db['Orders'].count_documents({"userId": user_id})
        context['wishlist_count'] = db['Wishlist'].count_documents({"userId": user_id})
        context['active_tickets'] = db['SupportTickets'].count_documents(
            {"userId": user_id, "status": {"$ne": "Closed"}}
        )

        # Recent orders with item totals and string_id
        recent_orders = list(db['Orders'].find({"userId": user_id}).sort("created_at", -1).limit(5))
        for order in recent_orders:
            # Use order_id if it exists, else fallback to _id
            order['string_id'] = str(order.get('order_id', order.get('_id', '')))
            order['item_count'] = sum(int(item.get("quantity", 1)) for item in order.get("items", []))
        context['recent_orders'] = recent_orders

        # Wishlist snapshot
        wishlist_records = list(db['Wishlist'].find({"userId": user_id}).sort("createdAt", -1).limit(4))
        wishlist_items = []
        for item in wishlist_records:
            prod = db['Products'].find_one({"id": item.get("productId")})
            if prod:
                wishlist_items.append(prod)
        context['wishlist_items'] = wishlist_items

    elif active_tab == 'settings':
        # Fetch addresses and convert _id to id for safe template use
        addresses = list(db['Addresses'].find({"userId": user_id}))
        for addr in addresses:
            addr['id'] = str(addr['_id'])
        context['addresses'] = addresses

    elif active_tab == 'addresses':
        # If you still have a standalone addresses tab, keep it
        addresses = list(db['Addresses'].find({"userId": user_id}))
        for addr in addresses:
            addr['id'] = str(addr['_id'])
        context['addresses'] = addresses

    elif active_tab == 'orders':
        context['orders'] = list(db['Orders'].find({"userId": user_id}).sort("orderedAt", -1))

    elif active_tab == 'notifications':
        context['notifications'] = list(db['Notifications'].find({"userId": user_id}).sort("createdAt", -1))

    return render(request, 'store/dashboard.html', context)

def order_history_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    # Fetch ALL orders for the history page
    all_orders = list(db['Orders'].find({"userId": user_id}).sort("created_at", -1))
    
    for order in all_orders:
        # Force it to look for 'order_id' first. Only use '_id' as a last resort.
        if 'order_id' in order and order['order_id']:
            order['string_id'] = str(order['order_id'])
        else:
            order['string_id'] = str(order.get('_id', ''))
            
        order['item_count'] = sum(int(item.get("quantity", 1)) for item in order.get("items", []))
        
    context = {
        'orders': all_orders,
        # add any other context variables you need here
    }
    return render(request, 'store/order_history.html', context)


def order_history_view(request): # (Make sure the name matches your actual view name)
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    # THE FIX: Fetch ALL orders for the history page
    all_orders = list(db['Orders'].find({"userId": user_id}).sort("created_at", -1))
    
    for order in all_orders:
        # order['string_id'] = str(order.get('_id', order.get('id', '')))
        
        # This tells Django to look for your custom 'order_id' first. 
        # If it fails (e.g., for older test orders), it falls back to the MongoDB '_id'.
        order['string_id'] = str(order.get('order_id' or order.get('_id', '')))
        order['item_count'] = sum(int(item.get("quantity", 1)) for item in order.get("items", []))
        
    context = {
        'orders': all_orders,
        # add any other context variables you need here
        'user_name': request.session.get('user_name', 'User'),
    }
    return render(request, 'store/order_history.html', context)




def order_detail_view(request, order_id):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
        
    try:
        # First try looking it up by the MongoDB _id (for old test orders)
        order = db['Orders'].find_one({"_id": ObjectId(order_id), "userId": user_id})
    except:
        # THE FIX: If it's a UUID, it will fail the ObjectId check and fall back to here.
        # We must look for 'order_id', not 'id'!
        order = db['Orders'].find_one({"order_id": order_id, "userId": user_id})
        
    if not order:
        return redirect('order_history')
        
    # THE FIX: Apply the exact same bulletproof string_id logic here!
    if 'order_id' in order and order['order_id']:
        order['string_id'] = str(order['order_id'])
    else:
        order['string_id'] = str(order.get('_id', ''))
        
    order['item_count'] = sum(int(item.get("quantity", 1)) for item in order.get("items", []))
    
    # Hydrate product details
    for item in order.get("items", []):
        product_id = item.get("productId")
        product_data = db['Products'].find_one({"id": product_id}) 
        
        if product_data:
            item['name'] = product_data.get('name', 'Product Name Missing')
            item['price'] = product_data.get('price', 0)
            item['thumbnail'] = product_data.get('thumbnail', '')
            
    context = {
        'order': order,
    }
    return render(request, 'store/order_detail.html', context)


from django.shortcuts import render
from django.core.paginator import Paginator

def shop_view(request):
    category_slug = request.GET.get('category')
    search_query = request.GET.get('q')
    sort = request.GET.get('sort', 'newest')
    page = request.GET.get('page', 1)

    # ---- Build the filter ----
    conditions = []
    current_category = 'All Products'

    if category_slug:
        # ---- Mapping from URL slug to exact categoryId ----
        category_map = {
            'smartphones': 'cat_smartphones',
            'laptops': 'cat_computers',          # or 'cat_gaming_laptops' – choose as needed
            'headphones': 'cat_audio',
            'mens-clothing': 'cat_mens_clothing',
            'womens-clothing': 'cat_womens_clothing',
            'sneakers': 'cat_footwear',
            # add more as you discover them
        }

        if category_slug in category_map:
            exact_id = category_map[category_slug]
            conditions.append({'categoryId': exact_id})
            current_category = category_slug.replace('-', ' ').title()
        else:
            # ---- Fallback: search for categoryId that contains the slug (case‑insensitive) ----
            # Replace hyphens with underscores to match DB format
            search_term = category_slug.replace('-', '_')
            conditions.append({'categoryId': {'$regex': search_term, '$options': 'i'}})
            current_category = category_slug.replace('-', ' ').title()

    # ---- Search query ----
    if search_query:
        regex = {'$regex': search_query, '$options': 'i'}
        conditions.append({
            '$or': [
                {'name': regex},
                {'description': regex},
                {'category': regex},          # if you have a display name field
                {'categoryId': regex},        # also search the ID
            ]
        })

    # ---- Combine conditions ----
    if conditions:
        filter_criteria = {'$and': conditions} if len(conditions) > 1 else conditions[0]
    else:
        filter_criteria = {}

    # ---- Fetch products ----
    products = list(db['Products'].find(filter_criteria))

    # ---- Sorting ----
    if sort == 'newest':
        # FIX: Wrapped in str() to prevent mixed-type crashes
        products.sort(key=lambda p: str(p.get('createdAt', '')), reverse=True)
    elif sort == 'price_low':
        products.sort(key=lambda p: float(p.get('price', 0)))
    elif sort == 'price_high':
        products.sort(key=lambda p: float(p.get('price', 0)), reverse=True)

    # ---- Pagination ----
    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(page)

    context = {
        'products': page_obj,
        'category_slug': category_slug,
        'current_category': current_category,
        'sort': sort,
        'total_products': len(products),
        'search_query': search_query,
    }
    return render(request, 'store/shop.html', context)


def admin_dashboard_view(request):
    # SECURITY: Check for admin_id instead of user_id
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('admin_login')

    # Fetch admin details from the Admins collection, not Users
    admin_profile = db['Admins'].find_one({"id": admin_id})
    if not admin_profile:
        return redirect('admin_login')

    # ==========================================
    # AGGREGATE METRICS FROM MONGO DB
    # ==========================================
    total_products = db['Products'].count_documents({})
    total_orders = db['Orders'].count_documents({})
    total_customers = db['Users'].count_documents({"role": {"$ne": "admin"}})

    # Calculate Total Revenue from completed or paid orders
    pipeline = [
        {"$match": {"status": {"$ne": "Cancelled"}}},
        {"$group": {"_id": None, "total_revenue": {"$sum": "$total_price"}}}
    ]
    revenue_result = list(db['Orders'].aggregate(pipeline))
    total_revenue = revenue_result[0]['total_revenue'] if revenue_result else 0.0

    # Recent Orders (Top 5)
    recent_orders = list(db['Orders'].find().sort("createdAt", -1).limit(5))
    for order in recent_orders:
        order['string_id'] = str(order.get('order_id', order.get('_id', '')))

    # Low Stock Warning (Products with stock <= 5)
    low_stock_products = list(db['Products'].find({"stock": {"$lte": 5}}).limit(5))

    context = {
        'admin_name': admin_profile.get('name', 'Admin'),
        'total_revenue': round(total_revenue, 2),
        'total_orders': total_orders,
        'total_products': total_products,
        'total_customers': total_customers,
        'recent_orders': recent_orders,
        'low_stock_products': low_stock_products,
        'active_tab': 'overview'
    }

    return render(request, 'store/admin/dashboard.html', context)

from django.contrib.auth.hashers import check_password
from django.contrib import messages

def admin_login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Look specifically in the Admins collection
        admin_user = db['Admins'].find_one({"email": email})

        if admin_user and check_password(password, admin_user.get('password', '')):
            if not admin_user.get('isActive', True):
                messages.error(request, "This admin account is disabled.")
                return redirect('admin_login')

            # Set specific ADMIN session variables
            request.session['admin_id'] = admin_user['id']
            request.session['admin_role'] = admin_user['role']
            request.session['admin_name'] = admin_user['name']
            
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid admin credentials.")
            return redirect('admin_login')

    return render(request, 'store/admin/login.html')

from django.shortcuts import redirect
from django.contrib import messages

def admin_logout_view(request):
    if request.method == 'POST':
        # 1. Clear all admin-specific session keys
        request.session.pop('admin_id', None)
        request.session.pop('admin_role', None)
        request.session.pop('admin_name', None)
        
        # 2. (Optional) Send a success message to the login page
        messages.success(request, "You have been successfully logged out of the Admin Portal.")
        
    # 3. Redirect back to the secure admin login screen
    return redirect('admin_login')

from bson.objectid import ObjectId
from django.shortcuts import redirect
from django.contrib import messages

def admin_products_view(request):
    # Security Check
    if not request.session.get('admin_id'):
        return redirect('admin_login')
        
    # Fetch all products, newest first
    products = list(db['Products'].find().sort('_id', -1))
    
    # Convert MongoDB ObjectIds to strings for the HTML template
    for p in products:
        p['str_id'] = str(p.get('_id'))
        
    return render(request, 'store/admin/products.html', {'products': products})

def admin_delete_product(request, product_id):
    if not request.session.get('admin_id'):
        return redirect('admin_login')
        
    if request.method == 'POST':
        # Delete the product from MongoDB
        db['Products'].delete_one({"_id": ObjectId(product_id)})
        messages.success(request, "Product deleted successfully.")
        
    return redirect('admin_products')


from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages

def admin_add_product_view(request):
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        
        try:
            price = float(request.POST.get('price', 0))
            stock = int(request.POST.get('stock', 0))
        except ValueError:
            price, stock = 0.0, 0
            
        image_url = request.POST.get('image')
        description = request.POST.get('description')

        # Generate a unique string ID just like the old 'prod_auto_402'
        custom_id = f"prod_custom_{uuid.uuid4().hex[:6]}"

        # Create the document matching your ORIGINAL schema
        new_product = {
            "id": custom_id,                             # CRITICAL: Fixes the 0 price bug
            "name": name,
            "categoryId": f"cat_{category.lower()}",     # Mimics 'cat_smartphones'
            "category": category,                        # Kept for safety
            "price": price,
            "stock": stock,
            "thumbnail": image_url,                      # Mimics original image field
            "image": image_url,                          # Kept for safety
            "description": description,
            "createdAt": datetime.now(),
            "status": "active"
        }

        db['Products'].insert_one(new_product)
        messages.success(request, f'Product "{name}" added successfully!')
        
        return redirect('admin_products')

    return render(request, 'store/admin/add_product.html')


from bson.objectid import ObjectId

def admin_edit_product_view(request, product_id):
    # 1. Security Check
    if not request.session.get('admin_id'):
        return redirect('admin_login')

    # 2. Safely find the product in MongoDB (handling both _id and custom id)
    try:
        # First, try treating product_id as a MongoDB ObjectId
        query = {"_id": ObjectId(product_id)}
    except:
        # If it's a custom string ID, fallback to searching the 'id' field
        query = {"id": product_id}

    product = db['Products'].find_one(query)
    
    if not product:
        messages.error(request, "Product not found.")
        return redirect('admin_products')

    # 3. Handle Form Submission (POST)
    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        
        try:
            price = float(request.POST.get('price', 0))
            stock = int(request.POST.get('stock', 0))
        except ValueError:
            price, stock = 0.0, 0
            
        image_url = request.POST.get('image')
        description = request.POST.get('description')

        # Define the fields to update
        update_data = {
            "name": name,
            "categoryId": f"cat_{category.lower()}",
            "category": category,
            "price": price,
            "stock": stock,
            "thumbnail": image_url,
            "image": image_url,
            "description": description,
            "updatedAt": datetime.now()
        }

        # Update the database
        db['Products'].update_one(query, {"$set": update_data})
        messages.success(request, f'Product "{name}" updated successfully!')
        
        return redirect('admin_products')

    # 4. Render the form with existing data (GET)
    # Ensure we have a string version of the _id for the template form action
    product['str_id'] = str(product['_id'])
    
    return render(request, 'store/admin/edit_product.html', {'product': product})


def admin_orders_view(request):
    # 1. Security Check
    if not request.session.get('admin_id'):
        return redirect('admin_login')
        
    # 2. Fetch all orders, sorted by newest first. 
    # We sort by '_id' instead of 'orderedAt' because old orders don't have 'orderedAt'!
    orders = list(db['Orders'].find().sort('_id', -1))
    
    # 3. Normalize data schema (bridge old test orders and new checkout format)
    for o in orders:
        o['str_id'] = str(o.get('_id'))
        
        # Bridge the Order ID
        if 'orderNumber' not in o:
            o['orderNumber'] = o.get('order_id', o['str_id'])
            
        # Bridge the Date
        if 'orderedAt' not in o:
            o['orderedAt'] = o.get('created_at')
            
        # Bridge the Total Amount
        if 'totalAmount' not in o:
            o['totalAmount'] = o.get('total', 0.0)
            
    return render(request, 'store/admin/orders.html', {'orders': orders})

from bson.objectid import ObjectId

def admin_order_details_view(request, order_id):
    # 1. Security Check
    if not request.session.get('admin_id'):
        return redirect('admin_login')
        
    # 2. Fetch the master order (Handle both old _id strings and new custom id strings)
    try:
        query = {"_id": ObjectId(order_id)}
    except:
        query = {"id": order_id}
        
    order = db['Orders'].find_one(query)
    
    if not order:
        messages.error(request, "Order not found.")
        return redirect('admin_orders')

    # 3. Normalize the Order Data (Bridge old test orders to the new layout)
    order['str_id'] = str(order.get('_id'))
    order['orderNumber'] = order.get('orderNumber', order.get('order_id', order['str_id']))
    order['orderedAt'] = order.get('orderedAt', order.get('created_at'))
    order['totalAmount'] = order.get('totalAmount', order.get('total', 0.0))
    order['subtotal'] = order.get('subtotal', float(order['totalAmount']) - 120.0)
    order['shippingFee'] = order.get('shippingFee', 120.0)
    
    # Extract the correct address dictionary
    address_data = order.get('addressData', order.get('shipping', {}))
    
    # 4. Fetch the Order Items
    # First, try looking in the new 'OrderItems' collection
    order_items = list(db['OrderItems'].find({"orderId": order.get('id')}))
    
    # Fallback: If it's an old order, the items might be embedded directly inside the order document
    if not order_items and 'items' in order:
        order_items = order['items']
        
    # 5. Enrich the items with product names and images
    enriched_items = []
    for item in order_items:
        product_id = item.get('productId')
        
        # Look up the product to get its name/image
        product = db['Products'].find_one({"id": product_id})
        
        # Fallback for old database products using MongoDB _id
        if not product and product_id and len(str(product_id)) == 24:
            product = db['Products'].find_one({"_id": ObjectId(product_id)})
            
        unit_price = item.get('unitPrice', float(product.get('price', 0.0)) if product else 0.0)
        quantity = int(item.get('quantity', 1))
        
        enriched_items.append({
            'product_name': product.get('name', 'Unknown Product') if product else 'Unknown Product',
            'product_image': product.get('image', product.get('thumbnail', '')) if product else '',
            'quantity': quantity,
            'unitPrice': unit_price,
            'totalPrice': item.get('totalPrice', unit_price * quantity)
        })

    # 6. Package and render
    context = {
        'order': order,
        'address': address_data,
        'items': enriched_items
    }
    return render(request, 'store/admin/order_details.html', context)

def admin_ai_assistant_view(request):
    """Renders the AI Assistant interface for the admin dashboard."""
    # Security Check
    if not request.session.get('admin_id'):
        return redirect('admin_login')
        
    return render(request, 'store/admin/ai_assistant.html')