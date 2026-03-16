from celery import shared_task
from django.utils import timezone
from .models import ContentStrategy
from scheduling.models import Schedule
from .services import generate_and_save_content
import datetime
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def run_single_strategy(self, strategy_id):
    """
    Executes a single strategy immediately.
    Used for manual triggers via UI.
    """
    logger.info(f"Task received with strategy_id: {strategy_id}, type: {type(strategy_id)}")

    try:
        # Ensure strategy_id is an integer if it's passed as a string
        if isinstance(strategy_id, str):
            try:
                strategy_id = int(strategy_id)
            except (ValueError, TypeError):
                logger.warning(f"strategy_id {strategy_id} could not be converted to int")
                return f"Error: Invalid strategy_id: {strategy_id}"

        # Fetch strategy without using .get() to avoid raising DoesNotExist here
        strategy = ContentStrategy.objects.filter(id=strategy_id).first()

        if not strategy:
            logger.error(f"Strategy id {strategy_id} not found in database.")
            return f"Strategy {strategy_id} not found"
        
        # Verify user exists before proceeding (ForeignKey access could theoretically raise if broken)
        try:
            strategy_user = strategy.user
            if not strategy_user:
                 logger.error(f"Strategy {strategy_id} has no associated user.")
                 return "Error: Strategy has no associated user."
        except Exception as user_err:
            logger.error(f"Could not access user for strategy {strategy_id}: {str(user_err)}")
            return f"Error: Strategy user is inaccessible: {str(user_err)}"

        now = timezone.now()

        logger.info(f"Manual trigger: Starting AI Pipeline for strategy: {strategy.title} (ID: {strategy.id})")

        # 1. GENERATE CONTENT
        try:
            content = generate_and_save_content(
                user=strategy.user,
                concept_prompt=strategy.concept_prompt,
                content_type=strategy.content_type
            )
        except Exception as gen_err:
            logger.error(f"Content generation failed for strategy {strategy_id}: {str(gen_err)}")
            return f"Error generating content: {str(gen_err)}"

        # 2. SCHEDULE IT (Immediately + 1 mins to avoid past errors in worker)
        scheduled_dt = now + datetime.timedelta(minutes=1)

        try:
            Schedule.objects.create(
                user=strategy.user,
                content=content,
                platform=strategy.platform,
                scheduled_time=scheduled_dt,
                status='pending'
            )
        except Exception as sched_err:
            logger.error(f"Scheduling failed for strategy {strategy_id}: {str(sched_err)}")
            return f"Error scheduling content: {str(sched_err)}"

        # 3. UPDATE STRATEGY
        try:
            strategy.is_active = True
            strategy.last_run_at = now
            strategy.save()
        except Exception as save_err:
            logger.error(f"Final strategy update failed for strategy {strategy_id}: {str(save_err)}")
            # Even if update fails, content was generated and scheduled
            return f"Success: Strategy {strategy.title} executed (but failed to update last_run_at)."

        return f"Success: Strategy {strategy.title} executed."
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error in manual strategy run: {str(e)}\n{error_details}")
        raise e

@shared_task
def run_content_strategies():
    """
    Checks active strategies and generates/schedules content if needed.
    Runs periodically via Celery Beat.
    """
    now = timezone.now()
    active_strategies = ContentStrategy.objects.filter(is_active=True)
    
    results = []
    
    for strategy in active_strategies:
        should_run = False
        
        preferred_time = strategy.time_of_day
        scheduled_dt_today = timezone.datetime.combine(now.date(), preferred_time)
        scheduled_dt_today = timezone.make_aware(scheduled_dt_today)
        
        if not strategy.last_run_at:
            should_run = True
        else:
            last_run_local = timezone.localtime(strategy.last_run_at)
            
            # Check if it should run today based on frequency
            if strategy.frequency == 'daily':
                # Run if it hasn't run today, OR if the last run was yesterday and today's preferred time has passed
                if last_run_local.date() < now.date() and now >= scheduled_dt_today:
                     should_run = True
            elif strategy.frequency == 'weekly':
                days_since_last = (now.date() - last_run_local.date()).days
                if days_since_last >= 7 and now >= scheduled_dt_today:
                     should_run = True

        if should_run:
            try:
                # Check for duplicates scheduled for today
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Verify user exists before proceeding
                try:
                    strategy_user = strategy.user
                except Exception as user_err:
                    logger.error(f"Could not access user for strategy {strategy.id}: {str(user_err)}")
                    results.append(f"Error in {strategy.title}: User inaccessible")
                    continue

                already_scheduled = Schedule.objects.filter(
                    user=strategy.user,
                    content__title__startswith=f"Auto: {strategy.concept_prompt[:40]}",
                    scheduled_time__gte=today_start
                ).exists()

                if already_scheduled:
                    # Update last_run_at anyway so we don't keep trying
                    strategy.last_run_at = now
                    strategy.save()
                    continue

                # 1. GENERATE CONTENT
                content = generate_and_save_content(
                    user=strategy.user,
                    concept_prompt=strategy.concept_prompt,
                    content_type=strategy.content_type
                )
                
                # 2. SCHEDULE IT
                scheduled_dt = timezone.datetime.combine(now.date(), preferred_time)
                scheduled_dt = timezone.make_aware(scheduled_dt)
                
                if scheduled_dt < now:
                     # If the time passed while generating, schedule very soon
                     scheduled_dt = now + datetime.timedelta(minutes=1)

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
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Error in automated strategy {strategy.id}: {str(e)}\n{error_details}")
                results.append(f"Error in {strategy.title}: {str(e)}")
                
    return results
