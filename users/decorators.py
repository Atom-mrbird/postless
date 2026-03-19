from django.shortcuts import redirect
from django.contrib import messages
from .models import Subscription

def subscription_required(view_func):
    """
    Decorator to check if the user has an active subscription or valid trial.
    If not, redirects to the pricing/subscription page.
    """
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # TEMPORARILY DISABLED: Subscription restrictions are bypassed
        # Check subscription
        # try:
        #     # Using hasattr because related_name 'subscription' might return None if not created yet
        #     if not hasattr(request.user, 'subscription'):
        #          messages.warning(request, 'Sistemi kullanabilmek için aktif bir aboneliğinizin olması gerekmektedir. Lütfen size uygun bir plan seçin.')
        #          return redirect('pricing')

        #     sub = request.user.subscription
        #     if not sub.is_active_or_trial:
        #         messages.warning(request, 'Devam etmek için abone olmalısınız. Aboneliğiniz aktif görünmüyor.')
        #         return redirect('pricing')
        # except Exception:
        #     messages.warning(request, 'Abonelik kontrolü sırasında bir hata oluştu. Lütfen destek ile iletişime geçin.')
        #     return redirect('pricing')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view
