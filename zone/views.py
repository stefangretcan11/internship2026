from django.db.models import Count,Q
from rest_framework import viewsets

from issue.models import Issue
from users.permissions import IsAdminOrReadOnly

from .models import Zone
from .serializers import ZoneSerializer


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.prefetch_related('agents').annotate(
        resolved_issue_count=Count(
            'issues',
            filter=Q(issues__status=Issue.Status.DONE)
        )
    )
    serializer_class = ZoneSerializer
    permission_classes = [IsAdminOrReadOnly]