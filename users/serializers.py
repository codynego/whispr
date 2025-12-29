from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    
    class Meta:
        model = User
        fields = (
            'id', 'email', 'whatsapp', 'plan', 'first_name', 'last_name',
            'is_active', 'date_joined'
        )
        read_only_fields = ('id', 'date_joined', 'is_active')


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = (
            'email', 'password', 'password_confirm', 'whatsapp',
            'first_name', 'last_name'
        )
        extra_kwargs = {
            'whatsapp': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': False},  # or True, depending on your needs
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password': 'Passwords do not match'})
        

        validate_password(attrs['password'])
        return attrs
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('password_confirm', None)  # safe pop
        
        # Create user with proper password handling
        user = User.objects.create_user(
            password=password,  
            **validated_data     
        )
        
        user.is_active = True
        user.save(update_fields=['is_active'])
        
        return user


class PasswordUpdateSerializer(serializers.Serializer):
    """Serializer to handle password update"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user

        # Check old password
        if not user.check_password(attrs.get('old_password')):
            raise serializers.ValidationError({'old_password': 'Old password is incorrect.'})

        # Match new and confirm
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer"""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['email'] = user.email
        token['plan'] = user.plan
        return token
