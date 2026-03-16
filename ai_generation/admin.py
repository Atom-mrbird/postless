from django.contrib import admin
from .models import AIPrompt, AutomationStrategy

@admin.register(AIPrompt)
class AIPromptAdmin(admin.ModelAdmin):
    list_display = ('user', 'prompt_text_short', 'created_at')
    
    def prompt_text_short(self, obj):
        return obj.prompt_text[:50]
    prompt_text_short.short_description = 'Prompt'

@admin.register(AutomationStrategy)
class AutomationStrategyAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'platform', 'content_type', 'frequency', 'time_of_day', 'is_active', 'last_run_at')
    list_filter = ('platform', 'content_type', 'frequency', 'is_active')
    search_fields = ('title', 'user__username', 'concept_prompt')
    ordering = ('-created_at',)
    readonly_fields = ('last_run_at', 'created_at', 'updated_at')
