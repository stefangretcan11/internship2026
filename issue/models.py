import uuid
from django.db import models
from django.conf import settings
from django.db import models


class Issue(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        DELAYED = "delayed", "Delayed"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_issues",
    )

    title = models.CharField(max_length=50)

    description = models.TextField()

    gps_lat = models.FloatField()

    gps_long = models.FloatField()

    location = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    assigned = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_issues",
        blank=True,
        null=True,
    )

    validator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="validated_issues",
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )

    is_private = models.BooleanField(default=False)

    is_validated = models.BooleanField(default=False)

    date_created = models.DateTimeField(auto_now_add=True)

    date_updated = models.DateTimeField(auto_now=True)

    report_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    is_system = models.BooleanField(default=False)  # cannot be modified

    def __str__(self):
        return f"Comment by {self.user} on Issue {self.issue_id}"


class IssueReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('issue', 'user')  # one vote per user per issue

    def __str__(self):
        return f"Report by {self.user} on Issue {self.issue_id}"
