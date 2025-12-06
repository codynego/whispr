from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserCreateSerializer, CustomTokenObtainPairSerializer, PasswordUpdateSerializer

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            'user': UserSerializer(user).data,
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Get and update user profile"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token view"""
    serializer_class = CustomTokenObtainPairSerializer


class UpdatePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordUpdateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password updated successfully."}, status=200)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.permissions import AllowAny

class LogoutView(APIView):
    # Allow unauthenticated users to hit this endpoint 
    # (since their access token might be expired, and we only need the cookie)
    permission_classes = [AllowAny] 
    
    def post(self, request):
        # 1. Try to get the Refresh Token from the HTTP-only cookie
        refresh_token = request.COOKIES.get('refresh_token')
        
        # Initialize the response object
        response = Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)

        if refresh_token:
            try:
                # 2. Blacklist the token
                token = RefreshToken(refresh_token)
                token.blacklist()
                
                # 3. Clear the HTTP-only cookie
                response.delete_cookie('refresh_token')
                
                return response
                
            except TokenError:
                # If the token is already invalid, expired, or malformed, 
                # we still clear the cookie for safety and report success.
                response.delete_cookie('refresh_token')
                return response
        else:
            # No refresh token found in cookies (e.g., user was never logged in)
            # Still return 200 and ensure cookie is cleared (just in case)
            response.delete_cookie('refresh_token')
            return response


class ProfileView(generics.RetrieveAPIView):
    """Get user profile details"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user