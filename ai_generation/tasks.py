from celery import shared_task
from .models import AIPrompt

@shared_task
def generate_ai_content_task(prompt_id):
    try:
        prompt = AIPrompt.objects.get(id=prompt_id)
        # Simulate AI generation
        # In a real scenario, you would call OpenAI or Stability AI API here
        prompt.generated_content = f"Generated content for: {prompt.prompt_text}"
        prompt.save()
        return f"Content generated for prompt {prompt_id}"
    except AIPrompt.DoesNotExist:
        return f"Prompt {prompt_id} not found"
