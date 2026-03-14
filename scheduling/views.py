from rest_framework import viewsets
from .models import Schedule
from .serializers import ScheduleSerializer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import SocialAccount
from content.models import Content
from django.utils import timezone
from datetime import datetime
from users.decorators import subscription_required

class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer

@login_required
@subscription_required
def schedule_page(request):
    if request.method == 'POST':
        # Formdan verileri al
        content_id = request.POST.get('content_id')
        platform = request.POST.get('platform') # 'Instagram' or 'YouTube'
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        
        if content_id and platform and date_str and time_str:
            try:
                # Tarih ve saati birleştir
                scheduled_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                # Timezone aware yap (Django settings'e göre)
                scheduled_datetime = timezone.make_aware(scheduled_datetime)
                
                content = Content.objects.get(id=content_id, user=request.user)
                
                # Kaydet
                Schedule.objects.create(
                    user=request.user,
                    content=content,
                    platform=platform,
                    scheduled_time=scheduled_datetime,
                    status='pending'
                )
                messages.success(request, 'Post scheduled successfully!')
            except Exception as e:
                messages.error(request, f'Error scheduling post: {str(e)}')
        else:
            messages.error(request, 'Please fill all fields.')
            
        return redirect('schedule')

    # GET isteği: Verileri hazırla
    schedules = Schedule.objects.filter(user=request.user).order_by('scheduled_time')
    
    # Sadece bağlı olan hesapları getir (Connections ile bağlantı burada)
    connected_accounts = SocialAccount.objects.filter(user=request.user)
    platforms = [acc.platform for acc in connected_accounts] # ['Instagram', 'YouTube']
    
    # Kullanıcının içeriklerini getir
    contents = Content.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'schedule.html', {
        'schedules': schedules,
        'platforms': platforms,
        'contents': contents,
        'today': timezone.now().date()
    })

@login_required
@subscription_required
def edit_schedule(request, id):
    schedule = get_object_or_404(Schedule, id=id, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'delete':
            schedule.delete()
            messages.success(request, 'Scheduled post deleted successfully.')
            return redirect('schedule')
            
        # For update
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        platform = request.POST.get('platform')
        
        if date_str and time_str and platform:
            try:
                scheduled_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                scheduled_datetime = timezone.make_aware(scheduled_datetime)
                
                schedule.scheduled_time = scheduled_datetime
                schedule.platform = platform
                schedule.save()
                
                messages.success(request, 'Schedule updated successfully!')
                return redirect('schedule')
            except Exception as e:
                messages.error(request, f'Error updating schedule: {str(e)}')
        else:
            messages.error(request, 'Please fill all required fields.')

    # Prepare data for GET request (modal rendering or standalone page)
    connected_accounts = SocialAccount.objects.filter(user=request.user)
    platforms = [acc.platform for acc in connected_accounts]
    
    # Extract date and time for the form
    local_time = timezone.localtime(schedule.scheduled_time)
    current_date = local_time.date().isoformat()
    current_time = local_time.time().strftime('%H:%M')

    return render(request, 'edit_schedule.html', {
        'schedule': schedule,
        'platforms': platforms,
        'current_date': current_date,
        'current_time': current_time,
        'today': timezone.now().date()
    })
