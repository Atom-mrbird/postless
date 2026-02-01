from celery import shared_task
from .models import Schedule
from django.utils import timezone

@shared_task
def schedule_post_task():
    now = timezone.now()
    pending_schedules = Schedule.objects.filter(status='pending', scheduled_time__lte=now)
    
    for schedule in pending_schedules:
        # Trigger publishing logic here (e.g., call make.com webhook)
        # For now, just mark as published
        schedule.status = 'published'
        schedule.save()
        
    return f"Processed {pending_schedules.count()} schedules"
