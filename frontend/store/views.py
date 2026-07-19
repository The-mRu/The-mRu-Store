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
                
                # Fetch product price snapshot from your collection
                product = products_collection.find_one({"id": product_id})
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

    all_products = get_all_products() or []
    product_dict = {str(p.get('id')): p for p in all_products}

    return render(request, 'store/checkout.html', {
        'products_json': json.dumps(product_dict)
    })

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
            "addressData": shipping_data, # Directly storing structural snapshot 
            "paymentId": f"PAY-{uuid.uuid4().hex[:8].upper()}", # COD Placeholder token
            "subtotal": float(total_amount) - 120.00, # Back-calculating flat shipping fee
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
            
            # Fetch product details for unit price snapshot mapping
            product = products_collection.find_one({"id": product_id})
            unit_price = float(product.get('price', 0)) if product else 500.00
            
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