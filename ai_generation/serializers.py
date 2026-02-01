from rest_framework import serializers
from .models import AIPrompt

class AIPromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIPrompt
        fields = '__all__'
