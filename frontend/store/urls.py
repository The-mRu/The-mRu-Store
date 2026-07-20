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
    path('shop/', views.shop_view, name='shop'),
    
    # API Routes (Kept the correct ones, removed duplicates)
    path('api/cart/sync/', views.sync_cart_api, name='sync_cart_api'), 
    path('api/orders/place/', views.place_order_api, name='place_order_api'),
    
    # Dashboard Routes
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('order-history/', views.order_history_view, name='order_history'),
    
    #admin
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-logout/', views.admin_logout_view, name='admin_logout'),
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('admin-dashboard/products/', views.admin_products_view, name='admin_products'),
    path('admin-dashboard/products/delete/<str:product_id>/', views.admin_delete_product, name='admin_delete_product'),
    path('admin-dashboard/products/add/', views.admin_add_product_view, name='admin_add_product'),
]