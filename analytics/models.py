from django.db import models
from django.conf import settings
from scheduling.models import Schedule

class AnalyticsData(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    likes = models.IntegerField(default=0)
    views = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    fetched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analytics for {self.schedule}"
