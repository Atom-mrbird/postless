from django.contrib import admin
from .models import AIPrompt

@admin.register(AIPrompt)
class AIPromptAdmin(admin.ModelAdmin):
    list_display = ('user', 'prompt_text_short', 'created_at')
    
    def prompt_text_short(self, obj):
        return obj.prompt_text[:50]
    prompt_text_short.short_description = 'Prompt'
