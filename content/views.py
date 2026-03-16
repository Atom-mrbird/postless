from rest_framework import viewsets
from .models import Content
from .serializers import ContentSerializer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from scheduling.models import Schedule
from users.models import SocialAccount, Subscription
from django.utils import timezone
import datetime
from users.decorators import subscription_required
import stripe
from django.conf import settings

stripe.api_key = settings.IYZICO_SECRET_KEY

class ContentViewSet(viewsets.ModelViewSet):
    queryset = Content.objects.all()
    serializer_class = ContentSerializer

@login_required
@subscription_required
def content_page(request):
    # Handle File Upload
    if request.method == 'POST':
        if 'file' in request.FILES:
            try:
                file = request.FILES['file']
                title = request.POST.get('title', file.name)
                description = request.POST.get('description', '')
                
                # Determine content type based on file extension
                content_type = 'image'
                if file.content_type.startswith('video'):
                    content_type = 'video'
                elif file.content_type.startswith('text'):
                    content_type = 'text'
                
                Content.objects.create(
                    user=request.user,
                    title=title,
                    description=description,
                    file=file,
                    content_type=content_type
                )
                messages.success(request, 'İçerik başarıyla yüklendi!')
            except Exception as e:
                messages.error(request, f'Yükleme başarısız: {str(e)}')
        return redirect('content')

    # Handle Filtering
    filter_type = request.GET.get('type', 'all')
    contents = Content.objects.filter(user=request.user).order_by('-created_at')

    if filter_type == 'images':
        contents = contents.filter(content_type='image')
    elif filter_type == 'videos':
        contents = contents.filter(content_type='video')
    elif filter_type == 'ai':
        contents = contents.filter(title__startswith='Auto:') | contents.filter(title__startswith='AI Generated')

    return render(request, 'content.html', {
        'contents': contents,
        'active_filter': filter_type
    })

@login_required
@subscription_required
def delete_content(request, id):
    if request.method == 'POST':
        content = get_object_or_404(Content, id=id, user=request.user)
        try:
            content.file.delete(save=False) # Delete the actual file from storage
            content.delete() # Delete the db record
            messages.success(request, 'İçerik başarıyla silindi.')
        except Exception as e:
            messages.error(request, f'İçerik silinirken hata oluştu: {str(e)}')
    return redirect('content')

@login_required
@subscription_required
def dashboard_view(request):
    user = request.user
    
    # --- Check for Stripe Success Session ---
    session_id = request.GET.get('session_id')
    if session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            if checkout_session.payment_status == 'paid':
                # Update subscription status immediately
                sub = user.subscription
                sub.stripe_subscription_id = checkout_session.subscription
                sub.stripe_customer_id = checkout_session.customer
                sub.status = 'active'
                
                stripe_sub = stripe.Subscription.retrieve(checkout_session.subscription)
                sub.current_period_end = datetime.datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
                sub.trial_end = None # Trial is over
                sub.save()
                
                messages.success(request, "Welcome to Postless! Your subscription is now active.")
                return redirect('dashboard') # Redirect to remove session_id from URL
        except stripe.error.StripeError as e:
            messages.error(request, f"There was an issue verifying your payment: {e}")

    # --- METRICS ---
    scheduled_count = Schedule.objects.filter(user=user, status='pending').count()
    published_count = Schedule.objects.filter(user=user, status='published').count()
    total_contents = Content.objects.filter(user=user).count()
    
    # --- UPCOMING SCHEDULE ---
    upcoming_schedules = Schedule.objects.filter(
        user=user, 
        status='pending',
        scheduled_time__gte=timezone.now()
    ).order_by('scheduled_time')[:5]
    
    # --- RECENT ACTIVITY ---
    recent_uploads = Content.objects.filter(user=user).order_by('-created_at')[:3]
    recent_published = Schedule.objects.filter(user=user, status='published').order_by('-scheduled_time')[:3]
    
    activities = []
    for upload in recent_uploads:
        activities.append({
            'type': 'upload',
            'title': 'New media uploaded',
            'detail': 'Library',
            'time': upload.created_at
        })
    for pub in recent_published:
        activities.append({
            'type': 'publish',
            'title': 'Post published successfully',
            'detail': pub.platform,
            'time': pub.scheduled_time
        })
    
    activities.sort(key=lambda x: x['time'], reverse=True)
    activities = activities[:5]
    
    context = {
        'scheduled_count': scheduled_count,
        'published_count': published_count,
        'total_contents': total_contents,
        'ai_credits': 850,
        'upcoming_schedules': upcoming_schedules,
        'activities': activities,
    }
    
    return render(request, 'dashboard.html', context)
