import uuid

from django.db import models
from django.conf import settings


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    is_system = models.BooleanField(default=False) #cannot be modified

    def __str__(self):
        return f"Comment by {self.user} on Issue {self.issue_id}"