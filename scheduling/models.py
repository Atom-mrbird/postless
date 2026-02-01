from django.db import models
from django.conf import settings
from content.models import Content

class Schedule(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField()
    platform = models.CharField(max_length=50) # e.g., 'Instagram', 'YouTube'
    status = models.CharField(max_length=20, default='pending', choices=[('pending', 'Pending'), ('published', 'Published'), ('failed', 'Failed')])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.content.title} on {self.platform} at {self.scheduled_time}"
