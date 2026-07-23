import django_filters
from issue.models import Issue

class IssueFilter(django_filters.FilterSet):
    # automatically look for min_lat=.

    min_lat = django_filters.NumberFilter(field_name="gps_lat", lookup_expr='gte')
    max_lat = django_filters.NumberFilter(field_name="gps_lat", lookup_expr='lte')
    min_long = django_filters.NumberFilter(field_name="gps_long", lookup_expr='gte')
    max_long = django_filters.NumberFilter(field_name="gps_long", lookup_expr='lte')

    class Meta:
        model = Issue
        fields = ['category', 'status']
