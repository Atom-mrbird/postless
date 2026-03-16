from celery import shared_task
from django.utils import timezone
from .models import AutomationStrategy
from scheduling.models import Schedule
from .services import generate_and_save_content
import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def run_single_strategy(self, strategy_id):
    """
    Executes a single automation strategy.
    Called manually from UI or by the hourly periodic task.
    """
    logger.info(f"[Automation] Task started for strategy_id: {strategy_id}")
    
    try:
        # Strategy fetching with error handling
        strategy = AutomationStrategy.objects.filter(id=strategy_id).first()
        if not strategy:
            logger.error(f"[Automation] Strategy {strategy_id} not found.")
            return f"Error: Strategy {strategy_id} not found."

        # User verification
        try:
            user = strategy.user
            if not user:
                 logger.error(f"[Automation] Strategy {strategy_id} has no user.")
                 return "Error: No user associated with strategy."
        except Exception as e:
            logger.error(f"[Automation] User access failed for strategy {strategy_id}: {str(e)}")
            return "Error: User access failed."

        now = timezone.now()
        logger.info(f"[Automation] Running: {strategy.title} for user {user.username}")

        # 1. GENERATE CONTENT
        try:
            content = generate_and_save_content(
                user=user,
                concept_prompt=strategy.concept_prompt,
                content_type=strategy.content_type
            )
        except Exception as gen_err:
            logger.error(f"[Automation] Generation failed for strategy {strategy_id}: {str(gen_err)}\n{traceback.format_exc()}")
            return f"Error: Generation failed: {str(gen_err)}"

        # 2. SCHEDULE IT
        # Determine scheduled time: if preferred time today is passed, schedule for today + 1 min
        # Actually, if manually triggered, we usually want it ASAP (e.g., now + 1 min)
        # If automated, we use the preferred time.
        
        # For simplicity in manual trigger:
        scheduled_dt = now + datetime.timedelta(minutes=1)

        try:
            Schedule.objects.create(
                user=user,
                content=content,
                platform=strategy.platform,
                scheduled_time=scheduled_dt,
                status='pending'
            )
        except Exception as sched_err:
            logger.error(f"[Automation] Scheduling failed for strategy {strategy_id}: {str(sched_err)}")
            return f"Error: Scheduling failed: {str(sched_err)}"

        # 3. UPDATE STRATEGY
        strategy.is_active = True
        strategy.last_run_at = now
        strategy.save()

        logger.info(f"[Automation] Successfully completed: {strategy.title}")
        return f"Success: {strategy.title} processed."

    except Exception as e:
        logger.error(f"[Automation] Critical error in task: {str(e)}\n{traceback.format_exc()}")
        raise self.retry(exc=e, countdown=60)

@shared_task
def check_automation_strategies():
    """
    Periodic task to check which strategies need to run.
    """
    now = timezone.now()
    active_strategies = AutomationStrategy.objects.filter(is_active=True)
    
    results = []
    for strategy in active_strategies:
        try:
            should_run = False
            preferred_time = strategy.time_of_day
            # Combine current date with preferred time
            scheduled_dt_today = timezone.make_aware(datetime.datetime.combine(now.date(), preferred_time))
            
            if not strategy.last_run_at:
                # Never run before, check if preferred time has passed today
                if now >= scheduled_dt_today:
                    should_run = True
            else:
                last_run_local = timezone.localtime(strategy.last_run_at)
                
                if strategy.frequency == 'daily':
                    # If last run was before today AND current time is >= preferred time
                    if last_run_local.date() < now.date() and now >= scheduled_dt_today:
                        should_run = True
                elif strategy.frequency == 'weekly':
                    days_since = (now.date() - last_run_local.date()).days
                    if days_since >= 7 and now >= scheduled_dt_today:
                        should_run = True
            
            if should_run:
                # Check for duplicates (safety)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                duplicate = Schedule.objects.filter(
                    user=strategy.user,
                    content__title__startswith=f"Auto: {strategy.concept_prompt[:40]}",
                    scheduled_time__gte=today_start
                ).exists()
                
                if not duplicate:
                    logger.info(f"[Automation] Triggering automated run for: {strategy.title}")
                    run_single_strategy.delay(str(strategy.id))
                    results.append(f"Triggered: {strategy.title}")
                else:
                    # Mark as run to avoid re-triggering today
                    strategy.last_run_at = now
                    strategy.save()
                    results.append(f"Skipped (Duplicate): {strategy.title}")
                    
        except Exception as e:
            logger.error(f"[Automation] Error checking strategy {strategy.id}: {str(e)}")
            results.append(f"Error ({strategy.title}): {str(e)}")
            
    return results
