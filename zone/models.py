import uuid

from django import forms
from django.conf import settings
from django.db import models


class Zone(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=50,
    )

    neighborhood = models.CharField(
        max_length=100,
    )

    color = models.CharField(
        max_length=50,
    )

    agents = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="zones",
        blank=True,
        limit_choices_to={
            "role": "agent",
        },
    )


    @property
    def agent_ids_str(self):
        return ", ".join(
            str(agent.id) for agent in self.agents.all() if agent.status != 'deleted'
        )


    def __str__(self):
        return self.name