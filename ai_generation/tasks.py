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
        try:
            strategy_id = int(strategy_id)
        except (ValueError, TypeError):
            logger.warning(f"strategy_id {strategy_id} could not be converted to int")
            raise ContentStrategy.DoesNotExist(f"Invalid strategy_id: {strategy_id}")

        strategy = ContentStrategy.objects.filter(id=strategy_id).first()
        if not strategy:
            err_msg = f"Error: ContentStrategy with ID {strategy_id} does not exist."
            logger.error(err_msg)
            return err_msg
        now = timezone.now()

        logger.info(f"Manual trigger: Starting AI Pipeline for strategy: {strategy.title}")

        # 1. GENERATE CONTENT
        content = generate_and_save_content(
            user=strategy.user,
            concept_prompt=strategy.concept_prompt,
            content_type=strategy.content_type
        )

        # 2. SCHEDULE IT (Immediately + 1 mins to avoid past errors in worker)
        scheduled_dt = now + datetime.timedelta(minutes=1)

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
        return err_msg
    except Exception as e:
        logger.error(f"Error in manual strategy run: {str(e)}")
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
                results.append(f"Error in {strategy.title}: {str(e)}")
                
    return results
