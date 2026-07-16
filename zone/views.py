from rest_framework import viewsets

from .models import Zone
from .serializers import ZoneSerializer
from users.permissions import IsAdminOrValidator, IsAdminOrReadOnly


class ZoneViewSet(viewsets.ModelViewSet):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer
    permission_classes = [IsAdminOrReadOnly]