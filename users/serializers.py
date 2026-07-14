from django.contrib.auth.base_user import BaseUserManager
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'password', 're_password')
        read_only_fields = ('role',)

    def perform_create(self, validated_data):
        email = validated_data.get('email', '')
        username = email.split('@')[0]

        validated_data['username'] = username

        return super().perform_create(validated_data)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    # embeds role and status inside the JWT payload so the frontend knows the user's role and activation state without an extra API call.

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        token['status'] = user.status
        return token
