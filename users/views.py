from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import status
from django.contrib.auth import get_user_model

from users.serializers import CustomTokenObtainPairSerializer
from users.permissions import IsValidator
from rest_framework.permissions import AllowAny

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()

        if user and user.status == User.Status.PENDING:
            raise AuthenticationFailed(
                'Your account is pending validation. Please wait for approval.'
            )
        if user and user.status == User.Status.REJECTED:
            raise AuthenticationFailed(
                'Your account has been rejected. Contact support.'
            )

        return super().post(request, *args, **kwargs)


class ValidateUserView(APIView):
    permission_classes = [IsValidator]

    # dedicated endpoint that only validator can call to change user's status.
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


class ResetPasswordByEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        new_password = request.data.get('new_password')

        if not email or not new_password:
            return Response(
                {'error': 'email and new_password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {'error': 'No user found with this email.'},
                status=status.HTTP_404_NOT_FOUND
            )

        user.set_password(new_password)
        user.save()

        return Response({'message': 'Password reset successfully.'})
