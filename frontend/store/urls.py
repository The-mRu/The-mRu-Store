from django.urls import path
from . import views



urlpatterns = [
    path('', views.catalog_view, name='catalog'),
    path('chat/', views.chat_interface_view, name='chat_interface'),
    path('api/chat/', views.api_chat_proxy, name='api_chat_proxy'),
    
    # Auth Routes
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('product/<str:product_id>/', views.product_detail_view, name='product_detail'),
    path('cart/', views.cart_view, name='cart'),
    path('search/', views.search_view, name='search'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('order-success/', views.order_success_view, name='order_success'),
    path('order/<str:order_id>/', views.order_detail_view, name='order_detail'),
    
    # API Routes (Kept the correct ones, removed duplicates)
    path('api/cart/sync/', views.sync_cart_api, name='sync_cart_api'), 
    path('api/orders/place/', views.place_order_api, name='place_order_api'),
    
    # Dashboard Routes
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('order-history/', views.order_history_view, name='order_history'),
]