from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from users.serializers import CustomTokenObtainPairSerializer, AdminUserSerializer, CustomUserSerializer
from users.permissions import IsValidator, IsAdminOrValidator, IsAdmin

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        if user and user.status == User.Status.REJECTED:
            raise AuthenticationFailed(
                'Your account has been rejected. Contact support.'
            )

        return super().post(request, *args, **kwargs)


class ValidateUserView(APIView):
    permission_classes = [IsValidator]

    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get('status')

        allowed = [User.Status.ACTIVE, User.Status.REJECTED]
        if new_status not in allowed:
            return Response(
                {'error': f'Invalid status. Allowed values: {allowed}'},
                status=status.HTTP_400_BAD_REQUEST
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
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrValidator]

    def get_permissions(self):
        # only admins can create or delete  users
        if self.action in ['create', 'destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()

    def perform_update(self, serializer):
        if self.request.user.role == 'validator':
            new_status = self.request.data.get('status')
            if not new_status:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Validators can only update user status.")
            serializer.save(status=new_status)
        else:
            serializer.save()


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)
