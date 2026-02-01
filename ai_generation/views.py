from rest_framework import viewsets
from .models import AIPrompt
from .serializers import AIPromptSerializer

class AIPromptViewSet(viewsets.ModelViewSet):
    queryset = AIPrompt.objects.all()
    serializer_class = AIPromptSerializer
