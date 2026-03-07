from rest_framework import viewsets
from .models import Schedule
from .serializers import ScheduleSerializer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import SocialAccount
from content.models import Content
from django.utils import timezone
from datetime import datetime

class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer

@login_required
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
