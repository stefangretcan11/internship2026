from rest_framework import serializers

from users.models import CustomUser

from .models import Zone


class ZoneSerializer(serializers.ModelSerializer):
    resolved_issue_count = serializers.IntegerField(read_only=True)
    agents = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CustomUser.objects.filter(
            role=CustomUser.Role.AGENT,
        ),
        required=False,
    )
    agents_display = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = [
            "id",
            "name",
            "neighborhood",
            "color",
            "agents",
            "agents_display",
            "resolved_issue_count"
        ]
        read_only_fields = ["id"]

    def get_agents_display(self, obj):
        return obj.agent_ids_str