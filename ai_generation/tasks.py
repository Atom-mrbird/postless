from celery import shared_task
from django.utils import timezone
from .models import ContentStrategy
from scheduling.models import Schedule
from .services import generate_and_save_content
import datetime
import logging

logger = logging.getLogger(__name__)

@shared_task
def run_single_strategy(strategy_id):
    """
    Executes a single strategy immediately.
    Used for manual triggers via UI.
    """
    try:
        # We catch the broad Exception from the previous iteration that was returning the string
        # 'ContentStrategy matching query does not exist.' as a successful result string.
        strategy = ContentStrategy.objects.get(id=strategy_id)
        now = timezone.now()
        
        logger.info(f"Manual trigger: Starting AI Pipeline for strategy: {strategy.title}")
        
        # 1. GENERATE CONTENT
        content = generate_and_save_content(
            user=strategy.user,
            concept_prompt=strategy.concept_prompt,
            content_type=strategy.content_type
        )
        
        # 2. SCHEDULE IT (Immediately + 2 mins)
        scheduled_dt = now + datetime.timedelta(minutes=2)
        
        Schedule.objects.create(
            user=strategy.user,
            content=content,
            platform=strategy.platform,
            scheduled_time=scheduled_dt,
            status='pending'
        )
        
        # 3. UPDATE STRATEGY
        strategy.is_active = True
        strategy.last_run_at = now
        strategy.save()
        
        return f"Success: Strategy {strategy.title} executed."
    except ContentStrategy.DoesNotExist:
        err_msg = f"Error: ContentStrategy with ID {strategy_id} does not exist."
        logger.error(err_msg)
        # Raising the error so Celery actually marks the task as FAILED instead of SUCCESS
        raise ValueError(err_msg)
    except Exception as e:
        logger.error(f"Error in manual strategy run: {str(e)}")
        # Raising so it doesn't return a string and appear as "succeeded" in logs
        raise e

@shared_task
def run_content_strategies():
    """
    Checks active strategies and generates/schedules content if needed.
    Runs periodically (e.g., every hour) via Celery Beat.
    """
    now = timezone.now()
    active_strategies = ContentStrategy.objects.filter(is_active=True)
    
    results = []
    
    for strategy in active_strategies:
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
                # Check for duplicates
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                already_scheduled = Schedule.objects.filter(
                    user=strategy.user,
                    content__title__startswith=f"Auto: {strategy.concept_prompt[:40]}",
                    scheduled_time__gte=today_start
                ).exists()

                if already_scheduled:
                    continue

                # 1. GENERATE CONTENT
                content = generate_and_save_content(
                    user=strategy.user,
                    concept_prompt=strategy.concept_prompt,
                    content_type=strategy.content_type
                )
                
                # 2. SCHEDULE IT
                preferred_time = strategy.time_of_day
                scheduled_dt = timezone.datetime.combine(now.date(), preferred_time)
                scheduled_dt = timezone.make_aware(scheduled_dt)
                
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
                
                results.append(f"Strategy '{strategy.title}' scheduled.")
                
            except Exception as e:
                results.append(f"Error in {strategy.title}: {str(e)}")
                
    return results
