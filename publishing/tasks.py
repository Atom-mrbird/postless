from celery import shared_task
import requests
from scheduling.models import Schedule
from .models import PublishLog

@shared_task
def make_webhook_trigger_task(schedule_id, webhook_url):
    try:
        schedule = Schedule.objects.get(id=schedule_id)
        payload = {
            'content_title': schedule.content.title,
            'content_description': schedule.content.description,
            'file_url': schedule.content.file.url if schedule.content.file else None,
            'platform': schedule.platform,
        }
        
        response = requests.post(webhook_url, json=payload)
        
        PublishLog.objects.create(
            schedule=schedule,
            response_data=response.text,
            success=response.status_code == 200
        )
        
        return f"Webhook triggered for schedule {schedule_id}. Status: {response.status_code}"
    except Schedule.DoesNotExist:
        return f"Schedule {schedule_id} not found"
    except Exception as e:
        return f"Error triggering webhook: {str(e)}"
