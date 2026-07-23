from django.core.cache import cache
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.exceptions import (
    AuthenticationFailed, Throttled, PermissionDenied,
)
from django.contrib.auth import get_user_model
from users.serializers import (
    CustomTokenObtainPairSerializer, AdminUserSerializer, CustomUserSerializer,
)
from users.permissions import IsValidator, IsAdminOrValidator, IsAdmin

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets

User = get_user_model()

MAX_LOGIN_ATTEMPTS = 10
LOGIN_LOCKOUT_SECONDS = 10


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        if user and user.status == User.Status.REJECTED:
            raise AuthenticationFailed(
                'Your account has been rejected. Contact support.'
            )

        cache_key = f"failed_logins_{get_client_ip(request)}"

        if cache.get(cache_key, 0) >= MAX_LOGIN_ATTEMPTS:
            raise Throttled(
                detail="Too many failed login attempts. Try again in a minute."
            )

        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            try:
                cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, timeout=LOGIN_LOCKOUT_SECONDS)
            raise
        else:
            cache.delete(cache_key)
            return response


class ValidateUserView(APIView):
    permission_classes = [IsValidator]
    ALLOWED_STATUSES = [User.Status.ACTIVE, User.Status.REJECTED]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        new_status = request.data.get('status')
        if new_status not in self.ALLOWED_STATUSES:
            return Response(
                {'error': f'Invalid status. Allowed values: {self.ALLOWED_STATUSES}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.status = new_status
        user.save()

        return Response({
            'message': f'User has been {new_status}.',
            'user_id': user.id,
            'status': user.status,
            'is_active': user.is_active,
        })


class UserManagementViewSet(viewsets.ModelViewSet):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrValidator]
    queryset = User.objects.exclude(status=User.Status.DELETED)


    VALIDATOR_ALLOWED_FIELDS = {'status'}

    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()

    def perform_update(self, serializer):
        if self.request.user.role == 'validator':
            submitted_fields = set(self.request.data.keys())
            if not submitted_fields or not submitted_fields <= self.VALIDATOR_ALLOWED_FIELDS:
                raise PermissionDenied("Validators can only update a user's status.")
        serializer.save()


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)