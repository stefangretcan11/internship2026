import uuid

from django.db import models


class Zone(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(
        max_length=50,
        unique=True,
    )
    neighborhood = models.CharField(
        max_length=100,
    )
    color = models.CharField(
        max_length=50,
    )
    agent_ids = models.CharField(
        max_length=1000,
    )

    def __str__(self):
        return self.name