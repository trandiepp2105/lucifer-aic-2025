from django.urls import path
from . import views

urlpatterns = [
    path('info/', views.websocket_info, name='speech-websocket-info'),
]
