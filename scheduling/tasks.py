from celery import shared_task
from .models import Schedule
from users.models import SocialAccount
from django.utils import timezone
import requests
import json
import os
from django.conf import settings
import google.oauth2.credentials
import googleapiclient.discovery
import logging

logger = logging.getLogger(__name__)

@shared_task
def schedule_post_task():
    """
    Checks for pending schedules and publishes them to the respective platforms.
    Runs periodically (e.g., every minute) via Celery Beat.
    """
    now = timezone.now()
    # Find posts that are pending and scheduled for now or in the past
    pending_schedules = Schedule.objects.filter(status='pending', scheduled_time__lte=now)

    results = []

    for schedule in pending_schedules:
        try:
            logger.info(f"Publishing schedule {schedule.id} for {schedule.platform}...")
            
            if schedule.platform == 'Instagram':
                result = publish_to_instagram(schedule)
            elif schedule.platform == 'YouTube':
                result = publish_to_youtube(schedule)
            else:
                result = "Unknown platform"

            results.append(f"Schedule {schedule.id}: {result}")

        except Exception as e:
            schedule.status = 'failed'
            schedule.save()
            err_msg = f"Schedule {schedule.id} Failed: {str(e)}"
            logger.error(err_msg)
            results.append(err_msg)

    return results

def publish_to_instagram(schedule):
    """
    Publishes content to Instagram Graph API.
    Flow: Create Container -> Publish Container
    """
    try:
        account = SocialAccount.objects.filter(user=schedule.user, platform='Instagram').first()
        
        access_token = getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', None)
        if not access_token and account:
            access_token = account.access_token
            
        ig_user_id = getattr(settings, 'INSTAGRAM_ACCOUNT_ID', None)
        if not ig_user_id and account:
            ig_user_id = account.account_id
            
        if not access_token:
            raise Exception("Instagram Access Token missing. Connect account.")
        if not ig_user_id:
            raise Exception("Instagram Account ID missing. Connect account.")
        
        # 1. Create Media Container
        media_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"

        # Determine media type
        is_video = schedule.content.file.name.lower().endswith(('.mp4', '.mov'))

        params = {
            'access_token': access_token,
            'caption': schedule.content.description or schedule.content.title
        }

        # Resolve public URL for the media
        base_url = settings.CSRF_TRUSTED_ORIGINS[0] if getattr(settings, 'CSRF_TRUSTED_ORIGINS', None) else "http://localhost:8000"
        if not base_url.startswith('http'):
             base_url = f"https://{base_url}"
             
        if schedule.content.file.url.startswith('/'):
             file_url = f"{base_url}{schedule.content.file.url}"
        else:
             file_url = f"{base_url}/{schedule.content.file.url}"

        if is_video:
            params['media_type'] = 'REELS'
            params['video_url'] = file_url
        else:
            params['image_url'] = file_url

        response = requests.post(media_url, params=params)
        data = response.json()

        if 'id' not in data:
            raise Exception(f"Container creation failed: {data}")

        creation_id = data['id']

        # 2. Publish Media
        publish_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
        publish_params = {
            'creation_id': creation_id,
            'access_token': access_token
        }

        pub_response = requests.post(publish_url, params=publish_params)
        pub_data = pub_response.json()

        if 'id' in pub_data:
            schedule.status = 'published'
            schedule.save()
            return "Published successfully"
        else:
            raise Exception(f"Publishing failed: {pub_data}")

    except SocialAccount.DoesNotExist:
        raise Exception("Instagram account not connected")

def publish_to_youtube(schedule):
    """
    Publishes video to YouTube Data API.
    """
    try:
        account = SocialAccount.objects.get(user=schedule.user, platform='YouTube')

        # Reconstruct credentials
        credentials = google.oauth2.credentials.Credentials(
            token=account.access_token,
            refresh_token=account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.YOUTUBE_CLIENT_ID,
            client_secret=settings.YOUTUBE_CLIENT_SECRET,
        )

        youtube = googleapiclient.discovery.build('youtube', 'v3', credentials=credentials)

        # Prepare metadata
        body = {
            'snippet': {
                'title': schedule.content.title,
                'description': schedule.content.description,
                'tags': ['postless', 'automation'],
                'categoryId': '22' # People & Blogs
            },
            'status': {
                'privacyStatus': 'public' # or 'private' for testing
            }
        }

        # File path (Local file upload)
        file_path = schedule.content.file.path

        media = googleapiclient.http.MediaFileUpload(
            file_path,
            chunksize=-1,
            resumable=True
        )

        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Uploaded {int(status.progress() * 100)}%")

        if 'id' in response:
            schedule.status = 'published'
            schedule.save()
            return f"Published to YouTube: {response['id']}"
        else:
            raise Exception(f"YouTube upload failed: {response}")

    except SocialAccount.DoesNotExist:
        raise Exception("YouTube account not connected")
