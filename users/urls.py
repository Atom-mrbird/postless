from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, SocialAccountViewSet, register, activate, 
    iyzico_payment_init, iyzico_payment_callback, cancel_subscription
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'social-accounts', SocialAccountViewSet, basename='socialaccount')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', register, name='register'),
    path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('payment/init/', iyzico_payment_init, name='iyzico_payment_init'),
    path('payment/callback/', iyzico_payment_callback, name='iyzico_payment_callback'),
    path('subscription/cancel/', cancel_subscription, name='cancel_subscription'),
]
