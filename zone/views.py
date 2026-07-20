from rest_framework import viewsets

from users.permissions import IsAdminOrReadOnly

from .models import Zone
from .serializers import ZoneSerializer


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.prefetch_related('agents')
    serializer_class = ZoneSerializer
    permission_classes = [IsAdminOrReadOnly]