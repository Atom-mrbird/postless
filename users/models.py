from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import datetime

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
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('past_due', 'Past Due'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='trial')
    trial_end = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.status == 'trial' and not self.trial_end:
            self.trial_end = timezone.now() + datetime.timedelta(days=30)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.status}"

    @property
    def is_active_or_trial(self):
        """
        Checks if the subscription is active or in a trial period.
        """
        if self.status == 'active':
            return True
        if self.status == 'trial' and self.trial_end and self.trial_end > timezone.now():
            return True
        return False
