from celery import shared_task
from django.utils import timezone
from scheduling.models import Schedule
from users.models import SocialAccount
from .models import PublishLog
import requests
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
import json
import logging
from django.conf import settings
import mimetypes

logger = logging.getLogger(__name__)

@shared_task
def process_scheduled_posts():
    """
    Publisher Worker:
    Finds all pending schedules where the scheduled_time has passed
    and attempts to publish them via the appropriate platform API.
    """
    now = timezone.now()
    # Find posts scheduled for now or in the past that haven't been published yet
    due_schedules = Schedule.objects.filter(
        status='pending',
        scheduled_time__lte=now
    )

    results = []

    for schedule in due_schedules:
        logger.info(f"Attempting to publish Schedule ID: {schedule.id} to {schedule.platform}")
        
        try:
            if schedule.platform == 'Instagram':
                success, response_data = publish_to_instagram(schedule)
            elif schedule.platform == 'YouTube':
                success, response_data = publish_to_youtube(schedule)
            else:
                success, response_data = False, {"error": "Unsupported platform"}

            # Log the attempt
            PublishLog.objects.create(
                schedule=schedule,
                success=success,
                response_data=json.dumps(response_data)
            )

            # Update schedule status
            if success:
                schedule.status = 'published'
                schedule.save()
                results.append(f"Successfully published {schedule.id} to {schedule.platform}")
            else:
                schedule.status = 'failed'
                schedule.save()
                results.append(f"Failed to publish {schedule.id} to {schedule.platform}: {response_data}")

        except Exception as e:
            logger.error(f"Critical error publishing schedule {schedule.id}: {str(e)}")
            schedule.status = 'failed'
            schedule.save()
            
            PublishLog.objects.create(
                schedule=schedule,
                success=False,
                response_data=json.dumps({"exception": str(e)})
            )
            results.append(f"Critical failure on {schedule.id}: {str(e)}")

    return results


def publish_to_instagram(schedule):
    """
    Publishes to Instagram using the Instagram Graph API.
    Handles both images and reels (videos).
    """
    user = schedule.user
    content = schedule.content
    
    # 1. Get the connected SocialAccount
    account = SocialAccount.objects.filter(user=user, platform='Instagram').first()
    
    access_token = getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', None)
    if not access_token and account:
        access_token = account.access_token
        
    ig_user_id = getattr(settings, 'INSTAGRAM_ACCOUNT_ID', None)
    if not ig_user_id and account:
        ig_user_id = account.account_id
        
    if not access_token:
        return False, {"error": "Instagram Access Token missing. Connect account."}
    if not ig_user_id:
        return False, {"error": "Instagram Account ID missing. Connect account."}
        
    # Resolve public URL for the media
    # If the URL already starts with http (like an S3 bucket URL), use it directly.
    # Otherwise, prepend the base domain.
    if content.file.url.startswith('http://') or content.file.url.startswith('https://'):
        media_url = content.file.url
    else:
        base_url = settings.CSRF_TRUSTED_ORIGINS[0] if getattr(settings, 'CSRF_TRUSTED_ORIGINS', None) else "http://localhost:8000"
        if not base_url.startswith('http'):
             base_url = f"https://{base_url}"
             
        if content.file.url.startswith('/'):
             media_url = f"{base_url}{content.file.url}"
        else:
             media_url = f"{base_url}/{content.file.url}"
         
    caption = content.description

    base_url_graph = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"
    
    # Determine type dynamically based on file extension
    mime_type, _ = mimetypes.guess_type(content.file.name)
    
    is_video = False
    if mime_type and mime_type.startswith('video'):
        is_video = True
    elif content.content_type == 'video':
        is_video = True
    elif content.file.name.lower().endswith(('.mp4', '.mov', '.avi')):
        is_video = True

    is_image = False
    if mime_type and mime_type.startswith('image'):
        is_image = True
    elif content.content_type == 'image':
        is_image = True
    elif content.file.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        is_image = True
    
    # 2. Step 1: Upload Media Container
    if is_video:
        payload = {
            'media_type': 'REELS',
            'video_url': media_url,
            'caption': caption,
            'access_token': access_token
        }
    elif is_image:
        payload = {
            'image_url': media_url,
            'caption': caption,
            'access_token': access_token
        }
    else:
        # Fallback based on content_type field if extension logic fails
        if content.content_type == 'video':
             payload = {
                'media_type': 'REELS',
                'video_url': media_url,
                'caption': caption,
                'access_token': access_token
             }
        else:
             payload = {
                'image_url': media_url,
                'caption': caption,
                'access_token': access_token
             }

    # Log payload for debugging
    logger.info(f"Sending payload to Instagram: {payload}")

    creation_res = requests.post(base_url_graph, data=payload)
    creation_data = creation_res.json()

    if 'id' not in creation_data:
        return False, {"error": "Container creation failed", "details": creation_data, "media_url": media_url, "payload_used": "video" if is_video else "image"}

    creation_id = creation_data['id']

    # For videos, you might need to poll until status is 'FINISHED' before publishing
    # Here we attempt immediate publish for simplicity. In a robust setup, add a sleep/poll here.

    # 3. Step 2: Publish the Media Container
    publish_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
    publish_payload = {
        'creation_id': creation_id,
        'access_token': access_token
    }

    publish_res = requests.post(publish_url, data=publish_payload)
    publish_data = publish_res.json()

    if 'id' in publish_data:
        return True, publish_data
    else:
        return False, {"error": "Publish failed", "details": publish_data}


def publish_to_youtube(schedule):
    """
    Publishes to YouTube using the YouTube Data API v3.
    """
    user = schedule.user
    content = schedule.content
    
    mime_type, _ = mimetypes.guess_type(content.file.name)
    is_video = mime_type and mime_type.startswith('video')
    
    if not is_video and content.content_type != 'video':
        return False, {"error": "YouTube only accepts video content"}
        
    account = SocialAccount.objects.filter(user=user, platform='YouTube').first()
    if not account:
        return False, {"error": "No YouTube account connected"}
        
    # Set up credentials
    credentials = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=getattr(settings, 'YOUTUBE_CLIENT_ID', '935602501203-vfpajcescc17kg3nbei7ck8nrulf33k7.apps.googleusercontent.com'),
        client_secret=getattr(settings, 'YOUTUBE_CLIENT_SECRET', '')
    )
    
    youtube = googleapiclient.discovery.build('youtube', 'v3', credentials=credentials)
    
    description = content.description
    tags = ['AI', 'Generated', 'Postless']

    body = {
        'snippet': {
            'title': content.title,
            'description': description,
            'tags': tags,
            'categoryId': '22' # People & Blogs
        },
        'status': {
            'privacyStatus': 'public', # or 'private' for testing
            'selfDeclaredMadeForKids': False, 
        }
    }
    
    # Must provide the actual file path on disk, not a URL for googleapiclient
    media_file = googleapiclient.http.MediaFileUpload(content.file.path, chunksize=-1, resumable=True)
    
    try:
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media_file
        )
        response = request.execute()
        return True, response
    except Exception as e:
        return False, {"error": str(e)}