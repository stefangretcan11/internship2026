from django.contrib import admin

from .models import Issue


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "status",
        "is_private",
        "is_validated",
        "date_created",
    )

    list_filter = (
        "status",
        "is_private",
        "is_validated",
    )

    search_fields = (
        "title",
        "description",
        "location",
        "owner__email",
    )

    readonly_fields = (
        "id",
        "date_created",
        "date_updated",
    )