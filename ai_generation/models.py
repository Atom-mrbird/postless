from django.db import models
from django.conf import settings

class AIPrompt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    prompt_text = models.TextField()
    generated_content = models.TextField(blank=True)
    prompt_type = models.CharField(max_length=20, choices=[('image', 'Image'), ('text', 'Text')], default='text')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prompt by {self.user.username} at {self.created_at}"
