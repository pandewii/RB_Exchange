from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import CustomUser

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(username=email, password=password)

        if not user:
            raise AuthenticationFailed("Email ou mot de passe incorrect.")

        if not user.is_active:
            raise AuthenticationFailed("Ce compte est désactivé.")

        refresh = RefreshToken.for_user(user)

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': user.role, # type: ignore
            'email': user.email
        }
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

