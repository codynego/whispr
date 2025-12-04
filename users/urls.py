# Assuming this is in your app's urls.py file
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
# Import the new LogoutView
from .views import (
    UserRegistrationView, 
    UserDetailView, 
    CustomTokenObtainPairView, 
    UpdatePasswordView,
    LogoutView # <-- ADD THIS IMPORT
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('profile/', UserDetailView.as_view(), name='user-profile'),
    path('update-password/', UpdatePasswordView.as_view(), name='update-password'),
    # --- NEW LOGOUT PATH ---
    path('logout/', LogoutView.as_view(), name='user-logout'), # <--- ADD THIS LINE
]