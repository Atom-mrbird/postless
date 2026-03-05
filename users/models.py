from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    pass

class SocialAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_accounts')
    platform = models.CharField(max_length=50) # e.g., 'Instagram', 'YouTube'
    account_id = models.CharField(max_length=255)
    account_name = models.CharField(max_length=255, blank=True, null=True) # Added for display name
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.platform} - {self.user.username}"

class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan_name = models.CharField(max_length=50) # e.g., 'Free', 'Pro', 'Enterprise'
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan_name}"
