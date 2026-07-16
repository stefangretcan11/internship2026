# from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from djoser.serializers import UserCreatePasswordRetypeSerializer as BaseUserCreateSerializer

User = get_user_model()


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    personal_number = serializers.CharField(required=True)
    confirm_password = serializers.CharField(style={"input_type": "password"}, write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("re_password", None)  # remove Djoser default re_password field

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = (
            'id', 'email', 'password', 'confirm_password',
            'first_name', 'last_name',
            'personal_number',
        )
        read_only_fields = ('role', 'status')
        extra_kwargs = {
            'password': {'write_only': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'personal_number': {'required': True},
        }

    def validate(self, attrs):
        confirm_password = attrs.pop("confirm_password", None)
        attrs["re_password"] = confirm_password
        return super().validate(attrs)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        token['status'] = user.status
        return token


# functions from admin
class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'password', 'first_name', 'last_name',
            'personal_number', 'role', 'status'
        )
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'personal_number': {'required': True},
        }

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def validate(self, attrs):
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({"password": "Password is required when creating a user."})
        return attrs


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name',
            'personal_number', 'role', 'status', 'photo', 'address'
        )
        # Prevent users from changing their own role and status
        read_only_fields = ('role', 'status', 'email')
