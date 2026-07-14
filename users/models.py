from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = 'citizen', 'Citizen'
        VALIDATOR = 'validator', 'Validator'
        AGENT = 'agent', 'Agent'
        ADMIN = 'admin', 'Admin'
        SUPERADMIN = 'superadmin', 'SuperAdmin'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CITIZEN,
    )

    def __str__(self):
        return f"{self.username} ({self.role})"  # pt debug si a vedea cine si cu rol vrea sa faca
