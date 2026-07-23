import uuid
from django.conf import settings
from django.db import models
from zone.models import Zone


class Issue(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        DELAYED = "delayed", "Delayed"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    class ValidationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VALIDATED = "validated", "Validated"
        REJECTED_DUPLICATE = "rejected_duplicate", "Rejected Duplicate"
        CHANGES_REQUESTED = "changes_requested", "Changes Requested"

    class Category(models.TextChoices):
        INFRASTRUCTURE = "infrastructure", "Infrastructure"
        HAZARD = "hazard", "Hazard"
        OTHERS = "others", "Others"

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

    location = models.TextField(
        blank=True,
        null=True,
    )
    zone = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        related_name="issues",
        null=True,
        blank=True,
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

    is_validated = models.BooleanField(default=False)

    validation_status = models.CharField(
        max_length=30,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )

    validation_message = models.TextField(
        blank=True,
        default="",
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHERS,
    )

    date_created = models.DateTimeField(auto_now_add=True)

    date_updated = models.DateTimeField(auto_now=True)

    report_count = models.PositiveIntegerField(default=0)


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class IssueReport(models.Model):
    # Universally Unique Identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('issue', 'user')  # one vote per user per issue

    def __str__(self):
        return f"Report by {self.user} on Issue {self.issue_id}"


class IssueFollower(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="followers",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_issues",
    )

    date_created = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("issue", "user"),
                name="unique_issue_follower",
            )
        ]

    def __str__(self):
        return (
            f"{self.user} follows "
            f"{self.issue.title}"
        )


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issue = models.ForeignKey('Issue', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    is_system = models.BooleanField(default=False, editable=False)
    attachments = models.ManyToManyField('Attachment', blank=True)

    def __str__(self):
        return f"Comment by {self.user} on Issue {self.issue_id}"


class Attachment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    image = models.TextField()

    def __str__(self):
        return f"Attachment for {self.issue.title}"


class Alert(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        SEEN = "seen", "Seen"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.NEW,
    )
    date_created = models.DateTimeField(auto_now_add=True)

    issue = models.ForeignKey(
        'Issue',
        on_delete=models.CASCADE,
        related_name='alerts'
    )

    def __str__(self):
        return f"Alert: {self.name} ({self.status})"


class AlertRecipient(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        SEEN = "seen", "Seen"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE,
        related_name="recipient_states",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alert_states",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.NEW,
    )

    date_created = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("alert", "user"),
                name="unique_alert_recipient_state",
            )
        ]
