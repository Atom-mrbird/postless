from django.db import models
from django.conf import settings
from scheduling.models import Schedule

class PublishLog(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    response_data = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log for {self.schedule} - Success: {self.success}"
