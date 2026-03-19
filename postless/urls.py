from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from content.views import content_page, delete_content, dashboard_view
from scheduling.views import schedule_page, edit_schedule
from users.views import connections_page, disconnect_account, settings_page, pricing_page, iyzico_payment_init, iyzico_payment_callback, instagram_webhook, feedback_page
from ai_generation.views import ai_generator_page, automation_page, delete_strategy, run_strategy_now, generate_content, save_generated_content
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    
    # UI Routes
    path('', dashboard_view, name='dashboard'),
    path('schedule/', schedule_page, name='schedule'),
    path('schedule/edit/<int:id>/', edit_schedule, name='edit_schedule'),
    path('content/', content_page, name='content'),
    path('content/delete/<int:id>/', delete_content, name='delete_content'),
    path('connections/', connections_page, name='connections'),
    path('connections/disconnect/<str:platform>/', disconnect_account, name='disconnect_account'),
    path('settings/', settings_page, name='settings'),
    path('pricing/', pricing_page, name='pricing'),
    path('ai/', ai_generator_page, name='ai_generator'),
    path('automation/', automation_page, name='automation'),
    path('automation/delete/<uuid:id>/', delete_strategy, name='delete_strategy'),
    path('automation/run/<uuid:id>/', run_strategy_now, name='run_strategy_now'),
    path('feedback/', feedback_page, name='feedback'),
    
    # AI API Routes
    path('api/generate-content/', generate_content, name='generate_content'),
    path('api/save-generated-content/', save_generated_content, name='save_generated_content'),
    
    # Iyzico Routes
    path('users/payment/init/', iyzico_payment_init, name='iyzico_payment_init'),
    path('users/payment/callback/', iyzico_payment_callback, name='iyzico_payment_callback'),

    # Meta/Instagram Webhook
    path('webhooks/instagram/', instagram_webhook, name='instagram_webhook'),

    # Auth
    path('accounts/', include('django.contrib.auth.urls')),
    
    path('privacy-policy/', TemplateView.as_view(template_name='privacy_policy.html'), name='privacy_policy'),
]

# When using S3, we usually don't need this, but it doesn't hurt for local dev
if settings.DEBUG or not getattr(settings, 'USE_S3', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
