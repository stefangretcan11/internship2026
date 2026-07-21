from django.db import transaction
from rest_framework import serializers
from issue.models import Comment
from users.models import CustomUser
from .models import (
    Alert,
    Attachment,
    Issue,
    IssueFollower,
)
from .utils import (
    validate_latitude,
    validate_longitude,
)


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            "id",
            "image",
        )
        read_only_fields = ("id",)


class AssignedAgentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class IssueSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(
        many=True,
        required=False,
    )
    followers_count = serializers.IntegerField(
        source="followers.count",
        read_only=True,
    )
    is_following = serializers.SerializerMethodField()
    # Returns nested agent info (id, first_name, last_name) or null.
    # Read-only so CITIZEN/AGENT can see it without needing user-list access.
    assigned = serializers.SerializerMethodField()

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
            "is_validated",
            "date_created",
            "date_updated",
            "report_count",
            "attachments",
            "validation_status",
            "validation_message",
            "category",
            "followers_count",
            "is_following",
        )

        read_only_fields = (
            "id",
            "owner",
            "validator",
            "status",
            "is_validated",
            "date_created",
            "date_updated",
            "report_count",
            "validation_status",
            "validation_message",
        )

    def validate_gps_lat(self, value):
        return validate_latitude(value)

    def validate_gps_long(self, value):
        return validate_longitude(value)

    @transaction.atomic
    def create(self, validated_data):
        attachments_data = validated_data.pop(
            "attachments",
            [],
        )

        issue = Issue.objects.create(**validated_data)

        Attachment.objects.bulk_create(
            [
                Attachment(
                    issue=issue,
                    image=attachment_data["image"],
                )
                for attachment_data in attachments_data
            ]
        )

        return issue

    def get_is_following(self, issue):
        request = self.context.get("request")

        if (
            request is None
            or not request.user.is_authenticated
        ):
            return False

        return IssueFollower.objects.filter(
            issue=issue,
            user=request.user,
        ).exists()

    def get_assigned(self, issue):
        agent = issue.assigned
        if agent is None:
            return None
        return AssignedAgentSerializer(agent).data


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
        )

    def validate_gps_lat(self, value):
        return validate_latitude(value)

    def validate_gps_long(self, value):
        return validate_longitude(value)

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user
        instance = self.instance

        changed_fields = {
            field_name
            for field_name, new_value in attrs.items()
            if (
                    instance is None
                    or getattr(instance, field_name) != new_value
            )
        }

        if user.role == CustomUser.Role.CITIZEN:
            if "status" in changed_fields:
                raise serializers.ValidationError(
                    {
                        "status": (
                            "Citizens cannot modify issue status."
                        )
                    }
                )

        elif user.role == CustomUser.Role.AGENT:
            forbidden_fields = changed_fields.difference(
                {"status"}
            )

            if forbidden_fields:
                raise serializers.ValidationError(
                    {
                        field_name: (
                            "Agents can only change the issue "
                            "status."
                        )
                        for field_name in forbidden_fields
                    }
                )

            allowed_statuses = {
                Issue.Status.NEW,
                Issue.Status.DELAYED,
                Issue.Status.IN_PROGRESS,
                Issue.Status.DONE,
            }

            if (
                    "status" in changed_fields
                    and attrs["status"] not in allowed_statuses
            ):
                raise serializers.ValidationError(
                    {
                        "status": "Invalid issue status."
                    }
                )

        elif user.role == CustomUser.Role.VALIDATOR:
            if changed_fields:
                raise serializers.ValidationError(
                    {
                        "detail": (
                            "Validators must use the dedicated "
                            "validation endpoints."
                        )
                    }
                )

        elif user.role not in {
            CustomUser.Role.ADMIN,
            CustomUser.Role.SUPERADMIN,
        }:
            raise serializers.ValidationError(
                {
                    "detail": "You cannot update this issue."
                }
            )

        return attrs


class CommentSerializer(serializers.ModelSerializer):
    issue_id = serializers.UUIDField(source="issue.id", read_only=True)
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    attachments = AttachmentSerializer(many=True, required=False)

    class Meta:
        model = Comment
        fields = (
            "id",
            "issue_id",
            "user_id",
            "description",
            "attachments",
            "date_created",
            "date_updated",
        )
        read_only_fields = (
            "id",
            "date_created",
            "date_updated",
        )

    @transaction.atomic
    def create(self, validated_data):
        attachments_data = validated_data.pop("attachments", [])
        comment = Comment.objects.create(**validated_data)

        for attachment_data in attachments_data:
            attachment = Attachment.objects.create(
                issue_id=comment.issue_id,
                image=attachment_data["image"]
            )
            comment.attachments.add(attachment)

        return comment


class AlertSerializer(serializers.ModelSerializer):
    # allowto send "issue_id": "<uuid>" for the sow post/api/alert
    issue_id = serializers.PrimaryKeyRelatedField(
        queryset=Issue.objects.all(),
        source='issue'
    )

    class Meta:
        model = Alert
        fields = ('id', 'name', 'status', 'date_created', 'issue_id')
        read_only_fields = ('id', 'status', 'date_created')


class IssueAssignSerializer(serializers.Serializer):
    agent_id = serializers.UUIDField()

    def validate_agent_id(self, value):
        try:
            agent = CustomUser.objects.get(id=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError(
                "Agent not found."
            )

        if agent.role != CustomUser.Role.AGENT:
            raise serializers.ValidationError(
                "The selected user is not an agent."
            )

        return value

    def update(self, instance, validated_data):
        agent = CustomUser.objects.get(
            id=validated_data["agent_id"]
        )

        instance.assigned = agent
        instance.save(
            update_fields=[
                "assigned",
                "date_updated",

            ]
        )

        return instance

    def create(self, validated_data):
        raise NotImplementedError
