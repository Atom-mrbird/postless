from celery import shared_task
from django.utils import timezone
from .models import ContentStrategy
from scheduling.models import Schedule
from .services import generate_and_save_content
import datetime
import logging

logger = logging.getLogger(__name__)

@shared_task
def run_content_strategies():
    """
    Checks active strategies and generates/schedules content if needed.
    Runs periodically (e.g., every hour) via Celery Beat.
    
    This is the core of the "AI Content Factory" architecture.
    """
    now = timezone.now()
    active_strategies = ContentStrategy.objects.filter(is_active=True)
    
    results = []
    
    for strategy in active_strategies:
        # Determine if we should run today
        should_run = False
        
        if not strategy.last_run_at:
            should_run = True
        else:
            days_since_last = (now.date() - strategy.last_run_at.date()).days
            if strategy.frequency == 'daily' and days_since_last >= 1:
                should_run = True
            elif strategy.frequency == 'weekly' and days_since_last >= 7:
                should_run = True
        
        if should_run:
            try:
                # Check if we already scheduled a post for today for this strategy to avoid duplicates
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                already_scheduled = Schedule.objects.filter(
                    user=strategy.user,
                    content__title__startswith=f"Auto: {strategy.concept_prompt[:40]}",
                    scheduled_time__gte=today_start
                ).exists()

                if already_scheduled:
                    logger.info(f"Content already scheduled for strategy '{strategy.title}' today. Skipping.")
                    continue

                logger.info(f"Starting AI Pipeline for strategy: {strategy.title}")
                
                # 1. GENERATE CONTENT (AI Pipeline)
                content = generate_and_save_content(
                    user=strategy.user,
                    concept_prompt=strategy.concept_prompt,
                    content_type=strategy.content_type
                )
                
                # 2. SCHEDULE IT
                preferred_time = strategy.time_of_day
                scheduled_dt = timezone.datetime.combine(now.date(), preferred_time)
                scheduled_dt = timezone.make_aware(scheduled_dt)
                
                # If preferred time has passed today, schedule for tomorrow
                if scheduled_dt < now:
                    scheduled_dt += datetime.timedelta(days=1)
                
                Schedule.objects.create(
                    user=strategy.user,
                    content=content,
                    platform=strategy.platform,
                    scheduled_time=scheduled_dt,
                    status='pending'
                )
                
                # 3. UPDATE STRATEGY
                strategy.last_run_at = now
                strategy.save()
                
                msg = f"Strategy '{strategy.title}': Content generated and scheduled for {scheduled_dt}"
                logger.info(msg)
                results.append(msg)
                
            except Exception as e:
                err_msg = f"Strategy '{strategy.title}' FAILED: {str(e)}"
                logger.error(err_msg)
                results.append(err_msg)
                
    return results
