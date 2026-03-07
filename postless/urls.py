from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserViewSet, SocialAccountViewSet, connections_page, instagram_webhook
from content.views import ContentViewSet
from ai_generation.views import AIPromptViewSet, ai_generator_page, generate_content, save_generated_content
from scheduling.views import ScheduleViewSet, schedule_page
from analytics.views import AnalyticsDataViewSet
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'social-accounts', SocialAccountViewSet)
router.register(r'content', ContentViewSet)
router.register(r'ai-prompts', AIPromptViewSet)
router.register(r'schedules', ScheduleViewSet)
router.register(r'analytics', AnalyticsDataViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/webhooks/instagram/', instagram_webhook, name='instagram_webhook'),
    path('api/generate-content/', generate_content, name='generate_content'),
    path('api/save-generated-content/', save_generated_content, name='save_generated_content'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('schedule/', schedule_page, name='schedule'),
    path('content/', TemplateView.as_view(template_name='content.html'), name='content'),
    path('ai/', ai_generator_page, name='ai_generator'),
    path('analytics/', TemplateView.as_view(template_name='analytics.html'), name='analytics'),
    path('connections/', connections_page, name='connections'),
    path('privacy-policy/', TemplateView.as_view(template_name='privacy_policy.html'), name='privacy_policy'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
