from django.urls import path
from . import views

urlpatterns = [
    path('', views.catalog_view, name='catalog'),
    path('chat/', views.chat_interface_view, name='chat_interface'),
    path('api/chat/', views.api_chat_proxy, name='api_chat_proxy'),
]