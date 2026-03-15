from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class SubscriptionMiddleware:
    """
    Middleware that ensures users have an active subscription or trial 
    before accessing restricted parts of the system.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Define paths that are always accessible (Login, Signup, Admin, Static files)
        exempt_paths = [
            reverse('admin:index'),
            '/accounts/', # Covers login, logout, signup
            '/users/payment/', # Your payment/pricing page
            '/static/',
            '/uploads/',
        ]

        path = request.path
        if any(path.startswith(p) for p in exempt_paths):
            return self.get_response(request)

        # 2. Check subscription for authenticated users
        if request.user.is_authenticated:
            # Allow superusers full access
            if request.user.is_superuser:
                return self.get_response(request)

            # Check if user has a subscription and if it's valid
            subscription = getattr(request.user, 'subscription', None)
            if not subscription or not subscription.is_active_or_trial:
                messages.warning(request, "Sistemi kullanmak için aktif bir aboneliğiniz olmalıdır.")
                # Redirect to your payment or pricing view
                return redirect('/users/payment/')

        return self.get_response(request)