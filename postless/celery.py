import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'postless.settings')

app = Celery('postless')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Define periodic tasks
app.conf.beat_schedule = {
    # Publisher Worker: Checks every minute for posts whose time has come
    'publish-scheduled-posts-every-minute': {
        'task': 'publishing.tasks.process_scheduled_posts',
        'schedule': crontab(minute='*'), 
    },
    # Generator Worker: Checks every hour to see if active strategies need new content produced
    'check-automation-strategies-hourly': {
        'task': 'ai_generation.tasks.check_automation_strategies',
        'schedule': crontab(minute='0'), # Runs at the top of every hour
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
