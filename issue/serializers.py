from rest_framework import serializers

from issue.models import Comment


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ('id', 'issue_id', 'user_id', 'description', 'attachments', 'date_created', 'date_updated')
        read_only_fields = ('id', 'user_id', 'issue_id', 'date_created', 'date_updated')
