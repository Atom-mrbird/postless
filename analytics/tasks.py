from celery import shared_task
from scheduling.models import Schedule
from .models import AnalyticsData

@shared_task
def fetch_analytics_task():
    published_schedules = Schedule.objects.filter(status='published')
    
    for schedule in published_schedules:
        # Simulate fetching analytics
        # In a real scenario, you would call social media APIs
        analytics, created = AnalyticsData.objects.get_or_create(schedule=schedule)
        analytics.likes += 1 # Dummy increment
        analytics.views += 10
        analytics.save()
        
    return f"Updated analytics for {published_schedules.count()} schedules"
