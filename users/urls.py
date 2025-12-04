# Assuming this is in your app's urls.py file
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
# Import the new LogoutView
from .views import (
    UserRegistrationView, 
    UserDetailView, 
    CustomTokenObtainPairView, 
    UpdatePasswordView,
    LogoutView,
    LoginView
)

from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework import status

class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # This automatically reads the refresh token from the cookie named 'refresh_token'
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({"detail": "Refresh token not found"}, status=400)
        
        request.data['refresh'] = refresh_token
        return super().post(request, *args, **kwargs)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path("login/", LoginView.as_view(), name="login"),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', UserDetailView.as_view(), name='user-profile'),
    path('update-password/', UpdatePasswordView.as_view(), name='update-password'),
    # --- NEW LOGOUT PATH ---
    path('logout/', LogoutView.as_view(), name='user-logout'), # <--- ADD THIS LINE
]