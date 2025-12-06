# Assuming this is in your app's urls.py file
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
# Import the new LogoutView
from .views import (
    UserRegistrationView, 
    UserDetailView, 
    UpdatePasswordView,
)
from .views import LoginView, LogoutView, CustomTokenRefreshView

from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework import status



urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path('profile/', UserDetailView.as_view(), name='user-profile'),
    path('update-password/', UpdatePasswordView.as_view(), name='update-password'),
]