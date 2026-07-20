from django.contrib import admin

from .models import Attachment, Issue


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ("id",)


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "owner",
        "status",
        "is_validated",
        "date_created",
    )

    list_filter = (
        "status",
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

    inlines = [AttachmentInline]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "issue",
    )

    search_fields = (
        "issue__title",
        "issue__owner__email",
    )

    readonly_fields = ("id",)