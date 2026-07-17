import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'superadmin')
        extra_fields.setdefault('status', 'active')
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    class Role(models.TextChoices):
        CITIZEN = 'citizen', 'Citizen'
        VALIDATOR = 'validator', 'Validator'
        AGENT = 'agent', 'Agent'
        ADMIN = 'admin', 'Admin'
        SUPERADMIN = 'superadmin', 'SuperAdmin'
        # the superadmin will have superuser =1 and staff =1 (true)

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        REJECTED = 'rejected', 'Rejected'

    photo = models.CharField(max_length=500, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True)
    personal_number = models.CharField(max_length=50, blank=True, null=True)

    username = None
    USERNAME_FIELD = 'email'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CITIZEN,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    def save(self, *args, **kwargs):
        # for making the superadmin = superadmin in django
        # it needs to be different from the website admin role
        # any other role has is_staff and is_superuser on false
        self.is_active = (self.status == self.Status.ACTIVE)

        if self.role == self.Role.SUPERADMIN:
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f" ({self.role}) [{self.status}]"

