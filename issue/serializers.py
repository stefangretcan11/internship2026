from django.db import transaction

from rest_framework import serializers
from issue.models import Comment
from users.models import CustomUser
from .models import Issue
from .models import Attachment, Issue


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            "id",
            "image",
        )
        read_only_fields = ("id",)


class IssueSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(
        many=True,
        required=False,
    )

    class Meta:
        model = Issue
        fields = (
            "id",
            "owner",
            "title",
            "description",
            "gps_lat",
            "gps_long",
            "location",
            "assigned",
            "validator",
            "status",
            "is_private",
            "is_validated",
            "date_created",
            "date_updated",
            "report_count",
            "attachments",
            "validation_status",
            "validation_message",
            "category"
        )

        read_only_fields = (
            "id",
            "owner",
            "assigned",
            "validator",
            "status",
            "is_validated",
            "date_created",
            "date_updated",
            'report_count',
            "validation_status",
            "validation_message",
        )

    def validate_gps_lat(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError(
                "Latitude must be between -90 and 90."
            )

        return value

    def validate_gps_long(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError(
                "Longitude must be between -180 and 180."
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        attachments_data = validated_data.pop("attachments", [])

        issue = Issue.objects.create(**validated_data)

        Attachment.objects.bulk_create([
            Attachment(
                issue=issue,
                image=attachment_data["image"],
            )
            for attachment_data in attachments_data
        ])

        return issue


class IssueUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = (
            "title",
            "description",
            "gps_lat",
            "gps_long",
            "location",
            "status",
            "is_private",
        )

    def validate_gps_lat(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError(
                "Latitude must be between -90 and 90."
            )

        return value

    def validate_gps_long(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError(
                "Longitude must be between -180 and 180."
            )

        return value

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user
        instance = self.instance

        changed_fields = {
            field_name
            for field_name, new_value in attrs.items()
            if instance is None
               or getattr(instance, field_name) != new_value
        }

        if user.role == CustomUser.Role.CITIZEN:
            forbidden_fields = changed_fields.intersection({"status"})

            if forbidden_fields:
                raise serializers.ValidationError({
                    "status": "Citizens cannot modify issue status."
                })

        elif user.role == CustomUser.Role.AGENT:
            forbidden_fields = changed_fields.difference({"status"})

            if forbidden_fields:
                raise serializers.ValidationError({
                    field_name: "Agents can only change the issue status."
                    for field_name in forbidden_fields
                })

            if (
                    "status" in changed_fields
                    and attrs["status"] not in {
                Issue.Status.NEW,
                Issue.Status.DELAYED,
                Issue.Status.IN_PROGRESS,
                Issue.Status.DONE,
            }
            ):
                raise serializers.ValidationError({
                    "status": "Invalid issue status."
                })

        elif user.role == CustomUser.Role.VALIDATOR:
            if changed_fields:
                raise serializers.ValidationError({
                    "detail": (
                        "Validators must use the dedicated validation endpoints."
                    )
                })

        elif user.role not in {
            CustomUser.Role.ADMIN,
            CustomUser.Role.SUPERADMIN,
        }:
            raise serializers.ValidationError({
                "detail": "You cannot update this issue."
            })

        return attrs

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)

        if instance.is_validated:
            instance.is_private = False

        if instance.status == Issue.Status.DONE:
            instance.is_private = False

        instance.save(update_fields=["is_private"])

        return instance


class CommentSerializer(serializers.ModelSerializer):
    issue_id = serializers.UUIDField(source='issue.id', read_only=True)
    user_id = serializers.UUIDField(source='user.id', read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'issue_id', 'user_id', 'description', 'attachments', 'date_created', 'date_updated')
        read_only_fields = ('id', 'date_created', 'date_updated')
