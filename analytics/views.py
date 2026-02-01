from rest_framework import viewsets
from .models import AnalyticsData
from .serializers import AnalyticsDataSerializer

class AnalyticsDataViewSet(viewsets.ModelViewSet):
    queryset = AnalyticsData.objects.all()
    serializer_class = AnalyticsDataSerializer
