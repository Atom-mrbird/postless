from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserViewSet, SocialAccountViewSet, connections_page, instagram_webhook
from content.views import ContentViewSet
from ai_generation.views import AIPromptViewSet
from scheduling.views import ScheduleViewSet
from analytics.views import AnalyticsDataViewSet
from django.views.generic import TemplateView

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
    path('api/social-accounts/instagram_callback/', instagram_webhook, name='instagram_webhook'), # Added webhook URL
    path('accounts/', include('django.contrib.auth.urls')),
    path('', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('schedule/', TemplateView.as_view(template_name='schedule.html'), name='schedule'),
    path('content/', TemplateView.as_view(template_name='content.html'), name='content'),
    path('ai/', TemplateView.as_view(template_name='ai_generator.html'), name='ai_generator'),
    path('analytics/', TemplateView.as_view(template_name='analytics.html'), name='analytics'),
    path('connections/', connections_page, name='connections'),
    path('privacy-policy/', TemplateView.as_view(template_name='privacy_policy.html'), name='privacy_policy'),
]
