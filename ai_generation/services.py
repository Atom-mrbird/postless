import openai
from django.conf import settings
from django.core.files.base import ContentFile
from content.models import Content
import requests
import os
import time

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_and_save_content(user, concept_prompt, content_type='image'):
    """
    AI Content Factory Pipeline:
    Converts a raw concept into a ready-to-publish Content object.
    Uses GPT-4 to refine the prompt, generates media (DALL-E 3 / RunwayML), and creates a caption.
    """
    try:
        # --- 1. Concept to Prompt Pipeline (Refinement) ---
        prompt_enhancer = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert prompt engineer for AI image and video generation models. Convert the user's raw concept into a highly detailed, descriptive, and visually striking prompt. To ensure uniqueness, add a unique artistic style or a specific creative perspective that changes every time, even for the same concept."
                },
                {
                    "role": "user", 
                    "content": f"Create a unique visual prompt for a {'video' if content_type == 'video' else 'photorealistic image'} based on this concept: {concept_prompt}. Ensure this version is distinct from previous ones by focusing on a specific random artistic detail or lighting condition. Timestamp: {time.time()}"
                }
            ]
        )
        refined_visual_prompt = prompt_enhancer.choices[0].message.content

        # --- 2. Generate Media ---
        media_url = None
        
        if content_type == 'image':
            # Generate Image using DALL-E 3
            image_response = client.images.generate(
                model="dall-e-3",
                prompt=f"{refined_visual_prompt}. High quality, cinematic lighting, 8k resolution. No text overlays.",
                size="1024x1024",
                quality="standard",
                n=1,
            )
            media_url = image_response.data[0].url
            
        elif content_type == 'video':
            # Generate Video using RunwayML Gen-3 Alpha Turbo
            base_url = "https://api.dev.runwayml.com/v1"
            headers = {
                "Authorization": f"Bearer {settings.RUNWAYML_API_KEY}",
                "Content-Type": "application/json",
                "X-Runway-Version": "2024-09-13"
            }
            payload = {
                "taskType": "gen3a_turbo", 
                "promptText": refined_visual_prompt,
                "model": "gen3a_turbo", 
                "ratio": "16:9"
            }
            
            start_response = requests.post(f"{base_url}/image_to_video", json=payload, headers=headers)
            if start_response.status_code != 200:
                raise Exception(f"Video Generation Start Failed: {start_response.text}")

            task_id = start_response.json()['id']
            
            # Polling for task completion
            for _ in range(60): # Max 5 minutes
                time.sleep(5)
                status_response = requests.get(f"{base_url}/tasks/{task_id}", headers=headers).json()
                status = status_response.get('status')
                
                if status == 'SUCCEEDED': 
                    output = status_response.get('output', [])
                    if output:
                         media_url = output[0]
                    break
                elif status == 'FAILED':
                    raise Exception(f"Video generation task failed: {status_response.get('failure')}")
            
            if not media_url:
                raise Exception("Video generation timed out.")

        # --- 3. Generate Platform-Specific Caption & Hashtags ---
        caption_response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a top-tier Social Media Manager. Write a highly engaging caption and separate hashtags. Format your response exactly like this: \nCAPTION: [your caption here]\nHASHTAGS: [your hashtags here]"
                },
                {
                    "role": "user", 
                    "content": f"The post concept is: {concept_prompt}"
                }
            ]
        )
        full_text = caption_response.choices[0].message.content
        
        caption = ""
        hashtags = ""
        
        if "CAPTION:" in full_text and "HASHTAGS:" in full_text:
            parts = full_text.split("HASHTAGS:")
            caption = parts[0].replace("CAPTION:", "").strip()
            hashtags = parts[1].strip()
        else:
            caption = full_text

        # --- 4. Download and Save to Library ---
        response = requests.get(media_url, stream=True)
        if response.status_code != 200:
            raise Exception("Failed to download generated media from provider.")

        # Create title from concept
        safe_title = f"Auto: {concept_prompt[:40]}"
        
        content = Content(
            user=user,
            title=safe_title,
            description=caption,
            hashtags=hashtags,
            content_type=content_type
        )
        
        ext = 'mp4' if content_type == 'video' else 'png'
        file_name = f"factory_{user.id}_{os.urandom(4).hex()}.{ext}"
        content.file.save(file_name, ContentFile(response.content), save=True)
        
        return content
        
    except Exception as e:
        print(f"Error in AI Content Factory Pipeline: {str(e)}")
        raise e
