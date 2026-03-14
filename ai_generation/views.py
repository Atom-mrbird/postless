from rest_framework import viewsets
from .models import AIPrompt, ContentStrategy
from .serializers import AIPromptSerializer
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from content.models import Content
from django.contrib import messages
from .tasks import run_content_strategies, run_single_strategy
from scheduling.models import Schedule
from .services import generate_and_save_content
from django.utils import timezone
import datetime
import json
import openai
import requests
import os
import time
from users.decorators import subscription_required

# OpenAI Client
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

class AIPromptViewSet(viewsets.ModelViewSet):
    queryset = AIPrompt.objects.all()
    serializer_class = AIPromptSerializer

@login_required
@subscription_required
def ai_generator_page(request):
    return render(request, 'ai_generator.html')

@login_required
@subscription_required
def automation_page(request):
    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        
        if action == 'create':
            ContentStrategy.objects.create(
                user=request.user,
                title=request.POST.get('title'),
                concept_prompt=request.POST.get('concept_prompt'),
                platform=request.POST.get('platform'),
                content_type=request.POST.get('content_type'),
                frequency=request.POST.get('frequency'),
                time_of_day=request.POST.get('time_of_day'),
                is_active=True
            )
            messages.success(request, 'Strateji başarıyla oluşturuldu ve aktif edildi!')
        
        elif action == 'toggle':
            strategy_id = request.POST.get('strategy_id')
            strategy = get_object_or_404(ContentStrategy, id=strategy_id, user=request.user)
            strategy.is_active = not strategy.is_active
            strategy.save()
            status = "aktif edildi" if strategy.is_active else "durduruldu"
            messages.success(request, f'Strateji {status}.')
            
        return redirect('automation') 
        
    strategies = ContentStrategy.objects.filter(user=request.user)
    return render(request, 'automation.html', {'strategies': strategies})

@login_required
@subscription_required
def delete_strategy(request, id):
    strategy = get_object_or_404(ContentStrategy, id=id, user=request.user)
    strategy.delete()
    messages.success(request, 'Strateji silindi.')
    return redirect('automation')

@login_required
@subscription_required
def run_strategy_now(request, id):
    """
    Manually triggers a specific strategy via Celery background task.
    Ensures the UI stays responsive while heavy AI generation happens.
    """
    strategy = get_object_or_404(ContentStrategy, id=id, user=request.user)
    
    # Trigger the AI generation and scheduling pipeline in the background
    run_single_strategy.delay(strategy.id)
    
    messages.success(request, f'"{strategy.title}" stratejisi arka planda başlatıldı. Yapay zeka içeriği üretecek ve paylaşımı otomatik olarak planlayacaktır. Bu işlem birkaç dakika sürebilir.')
    return redirect('automation')

@csrf_exempt
@login_required
@subscription_required
def generate_content(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt')
            content_type = data.get('content_type', 'image') # 'image' or 'video'
            style = data.get('style', 'vivid')
            
            if not prompt:
                return JsonResponse({'error': 'Prompt is required'}, status=400)

            # --- IMAGE GENERATION (DALL-E 3) ---
            if content_type == 'image':
                image_response = client.images.generate(
                    model="dall-e-3",
                    prompt=f"{prompt}, {style} style",
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                media_url = image_response.data[0].url
                
                # Generate Caption
                caption_response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a social media expert. Write a catchy, engaging caption for an Instagram post based on the user's image description. Include relevant hashtags."},
                        {"role": "user", "content": f"Write a caption for this image: {prompt}"}
                    ]
                )
                caption = caption_response.choices[0].message.content

                return JsonResponse({
                    'media_url': media_url,
                    'caption': caption,
                    'type': 'image'
                })

            # --- VIDEO GENERATION (RunwayML) ---
            elif content_type == 'video':
                base_url = "https://api.dev.runwayml.com/v1"
                
                headers = {
                    "Authorization": f"Bearer {settings.RUNWAYML_API_KEY}",
                    "Content-Type": "application/json",
                    "X-Runway-Version": "2024-09-13"
                }
                
                # Payload for Gen-3 Alpha Turbo
                payload = {
                    "taskType": "gen3a_turbo", 
                    "promptText": prompt,
                    "model": "gen3a_turbo", 
                    "ratio": "16:9"
                }
                
                # 1. Start the generation task
                start_response = requests.post(f"{base_url}/image_to_video", json=payload, headers=headers)
                
                if start_response.status_code != 200:
                    error_msg = start_response.text
                    raise Exception(f"RunwayML Start Failed: {error_msg}")

                task_id = start_response.json()['id']
                
                # 2. Poll for the result
                media_url = None
                for _ in range(60): # Poll for up to 5 minutes
                    time.sleep(5)
                    status_response = requests.get(f"{base_url}/tasks/{task_id}", headers=headers).json()
                    status = status_response.get('status')
                    
                    if status == 'SUCCEEDED': 
                        output = status_response.get('output', [])
                        if output and len(output) > 0:
                             media_url = output[0]
                        break
                    elif status == 'FAILED':
                        raise Exception(f"RunwayML task failed: {status_response.get('failure', 'Unknown error')}")
                
                if not media_url:
                    raise Exception("RunwayML video generation timed out.")

                # Generate Video Description/Title for YouTube
                caption_response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a YouTube expert. Write a catchy Video Title and Description."},
                        {"role": "user", "content": f"Write a YouTube title and description for a video about: {prompt}"}
                    ]
                )
                caption = caption_response.choices[0].message.content

                return JsonResponse({
                    'media_url': media_url,
                    'caption': caption,
                    'type': 'video'
                })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
@subscription_required
def save_generated_content(request):
    """
    Saves the AI generated content (Image or Video) to the Content library.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            media_url = data.get('media_url')
            caption = data.get('caption')
            content_type = data.get('content_type', 'image')
            
            if not media_url:
                return JsonResponse({'error': 'Media URL is required'}, status=400)
                
            # Download the file
            response = requests.get(media_url, stream=True)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to download media'}, status=400)
                
            # Create Content object
            content = Content(
                user=request.user,
                title=f"AI Generated {content_type.title()} - {caption[:20]}...",
                description=caption,
                content_type=content_type
            )
            
            # Save file
            ext = 'mp4' if content_type == 'video' else 'png'
            file_name = f"ai_gen_{request.user.id}_{os.urandom(4).hex()}.{ext}"
            
            content.file.save(file_name, ContentFile(response.content), save=True)
            
            return JsonResponse({'success': True, 'content_id': content.id})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid method'}, status=405)
