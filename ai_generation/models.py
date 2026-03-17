from django.db import models
from django.conf import settings
import uuid

class AIPrompt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    prompt_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.prompt_text[:20]}"

class AutomationStrategy(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]

    PLATFORM_CHOICES = [
        ('Instagram', 'Instagram'),
        ('YouTube', 'YouTube'),
    ]

    CONTENT_TYPE_CHOICES = [
        ('image', 'Image (DALL-E 3)'),
        ('video', 'Video (Sora)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=100, help_text="Strategy Name (e.g., Daily Cat Facts)")
    concept_prompt = models.TextField(help_text="The core concept for AI generation")
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES, default='image')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='daily')
    time_of_day = models.TimeField(help_text="Preferred time to post")
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Automation Strategy"
        verbose_name_plural = "Automation Strategies"

    def __str__(self):
        return f"{self.title} - {self.user.username} ({self.get_frequency_display()})"
