from rest_framework import viewsets
from .models import AIPrompt
from .serializers import AIPromptSerializer
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from content.models import Content
import json
import openai
import requests
import os

# OpenAI Client
client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

class AIPromptViewSet(viewsets.ModelViewSet):
    queryset = AIPrompt.objects.all()
    serializer_class = AIPromptSerializer

@login_required
def ai_generator_page(request):
    return render(request, 'ai_generator.html')

@csrf_exempt
@login_required
def generate_content(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt')
            style = data.get('style', 'vivid')
            
            if not prompt:
                return JsonResponse({'error': 'Prompt is required'}, status=400)

            # 1. Generate Image with DALL-E 3
            image_response = client.images.generate(
                model="dall-e-3",
                prompt=f"{prompt}, {style} style",
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = image_response.data[0].url

            # 2. Generate Caption with GPT-4
            caption_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a social media expert. Write a catchy, engaging caption for an Instagram post based on the user's image description. Include relevant hashtags."},
                    {"role": "user", "content": f"Write a caption for this image description: {prompt}"}
                ]
            )
            caption = caption_response.choices[0].message.content

            return JsonResponse({
                'image_url': image_url,
                'caption': caption
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid method'}, status=405)

@csrf_exempt
@login_required
def save_generated_content(request):
    """
    Saves the AI generated image and caption to the Content library.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_url = data.get('image_url')
            caption = data.get('caption')
            
            if not image_url:
                return JsonResponse({'error': 'Image URL is required'}, status=400)
                
            # Download the image
            response = requests.get(image_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to download image'}, status=400)
                
            # Create Content object
            content = Content(
                user=request.user,
                title=f"AI Generated - {caption[:30]}...",
                description=caption,
                content_type='image'
            )
            
            # Save image file
            file_name = f"ai_gen_{request.user.id}_{os.urandom(4).hex()}.png"
            content.file.save(file_name, ContentFile(response.content), save=True)
            
            return JsonResponse({'success': True, 'content_id': content.id})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid method'}, status=405)
