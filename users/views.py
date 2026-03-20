import google_auth_oauthlib
import googleapiclient
from rest_framework import viewsets
from .models import User, SocialAccount, Subscription
from .serializers import UserSerializer, SocialAccountSerializer
from django.shortcuts import redirect, render
import requests
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import json
import base64
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.utils import timezone
import datetime
from .forms import SignUpForm, UserUpdateForm
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode, urlencode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from .decorators import subscription_required
from .payments import create_checkout_form, retrieve_checkout_form_result

def register(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False # Deactivate until email verification
            user.save()
            
            # Start 30-Day Free Trial
            trial_end_date = timezone.now() + datetime.timedelta(days=30)
            Subscription.objects.create(
                user=user,
                status='trial',
                trial_end=trial_end_date
            )
            
            # Send Verification Email
            current_site = get_current_site(request)
            subject = 'Activate Your Postless Account'
            message = render_to_string('registration/account_activation_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            
            user.email_user(subject, message)
            
            messages.success(request, 'Please confirm your email address to complete the registration.')
            return redirect('login')
    else:
        form = SignUpForm()
    return render(request, 'registration/register.html', {'form': form})

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        messages.success(request, 'Your account has been activated successfully!')
        return redirect('dashboard')
    else:
        messages.error(request, 'Activation link is invalid!')
        return redirect('login')

@login_required
def settings_page(request):
    user_form = UserUpdateForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            user_form = UserUpdateForm(request.POST, instance=request.user)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, 'Profil başarıyla güncellendi.')
                return redirect('settings')
        
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Şifreniz başarıyla güncellendi.')
                return redirect('settings')
            else:
                messages.error(request, 'Lütfen aşağıdaki hataları düzeltin.')

        elif 'delete_account' in request.POST:
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, 'Hesabınız başarıyla silindi. Sizi tekrar görmek dileğiyle!')
            return redirect('login')

    return render(request, 'settings.html', {
        'user_form': user_form, 
        'password_form': password_form
    })

@login_required
def pricing_page(request):
    try:
        sub = request.user.subscription
        is_active = sub.status == 'active'
        is_trial = sub.status == 'trial' and sub.trial_end and sub.trial_end > timezone.now()
        days_left = (sub.trial_end - timezone.now()).days if is_trial else 0
        
        subscription_details = {
            'plan_name': 'Postless Pro Edition',
            'status': sub.get_status_display(),
            'next_billing_date': sub.current_period_end,
            'trial_ends_at': sub.trial_end
        }
    except Subscription.DoesNotExist:
        is_active = False
        is_trial = False
        days_left = 0
        subscription_details = None
        
    return render(request, 'pricing.html', {
        'is_active': is_active,
        'is_trial': is_trial,
        'days_left': days_left,
        'subscription': subscription_details
    })

@login_required
def cancel_subscription(request):
    if request.method == 'POST':
        try:
            sub = request.user.subscription
            sub.status = 'canceled'
            sub.save()
            messages.success(request, 'Aboneliğiniz başarıyla iptal edildi. Mevcut dönem sonuna kadar erişiminiz devam edecek.')
        except Exception as e:
            messages.error(request, f'Abonelik iptali sırasında bir hata oluştu: {str(e)}')
    return redirect('pricing')

@login_required
def iyzico_payment_init(request):
    try:
        checkout_form_html = create_checkout_form(request.user, request)
        return render(request, 'users/iyzico_payment.html', {
            'checkout_form_html': checkout_form_html
        })
    except Exception as e:
        messages.error(request, f"Ödeme formu oluşturulurken bir hata oluştu: {str(e)}")
        return redirect('pricing')

@csrf_exempt
def iyzico_payment_callback(request):
    token = request.POST.get('token')
    if not token:
        messages.error(request, "Geçersiz ödeme isteği.")
        return redirect('pricing')
    
    try:
        result_json = retrieve_checkout_form_result(token)
        result = json.loads(result_json)
        
        if result.get('status') == 'success' and result.get('paymentStatus') == 'SUCCESS':
            # Get user from conversationId (conv_{user.id})
            conv_id = result.get('conversationId')
            user_id = conv_id.split('_')[1]
            user = User.objects.get(id=user_id)
            
            # Update subscription
            sub, created = Subscription.objects.get_or_create(user=user)
            sub.status = 'active'
            # Set period end to 30 days from now
            sub.current_period_end = timezone.now() + datetime.timedelta(days=30)
            sub.save()
            
            messages.success(request, "Ödemeniz başarıyla tamamlandı! Aboneliğiniz aktif edildi.")
            return redirect('pricing')
        else:
            error_msg = result.get('errorMessage', 'Ödeme işlemi başarısız oldu.')
            messages.error(request, f"Hata: {error_msg}")
            return redirect('pricing')
            
    except Exception as e:
        messages.error(request, f"Ödeme doğrulanırken bir hata oluştu: {str(e)}")
        return redirect('pricing')

@login_required
def feedback_page(request):
    if request.method == 'POST':
        feedback_type = request.POST.get('feedback_type')
        message = request.POST.get('message')
        
        # Here you would typically save it to a database or send an email.
        # For now, we'll just show a success message.
        messages.success(request, 'Geri bildiriminiz başarıyla alındı. Teşekkür ederiz!')
        return redirect('dashboard')
        
    return render(request, 'feedback.html')

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class SocialAccountViewSet(viewsets.ModelViewSet):
    queryset = SocialAccount.objects.all()
    serializer_class = SocialAccountSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def test_connection(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'error': 'User not logged in'}, status=401)
        account = SocialAccount.objects.filter(user=user, platform='Instagram').first()
        if not account:
            return JsonResponse({'error': 'No Instagram account connected.'}, status=404)
        access_token = account.access_token
        debug_info = {
            'account_id': account.account_id,
            'account_name': account.account_name,
            'token_preview': access_token[:10] + '...' if access_token else None
        }
        try:
            perm_url = "https://graph.facebook.com/v18.0/me/permissions"
            perm_resp = requests.get(perm_url, params={'access_token': access_token})
            debug_info['permissions_response'] = perm_resp.json()
            pages_url = "https://graph.facebook.com/v18.0/me/accounts"
            pages_params = {'access_token': access_token, 'fields': 'name,id,instagram_business_account,tasks'}
            pages_resp = requests.get(pages_url, params=pages_params)
            debug_info['pages_response'] = pages_resp.json()
            if 'data' in debug_info['pages_response']:
                for page in debug_info['pages_response']['data']:
                    if 'instagram_business_account' in page:
                        ig_id = page['instagram_business_account']['id']
                        ig_url = f"https://graph.facebook.com/v18.0/{ig_id}"
                        ig_resp = requests.get(ig_url, params={'fields': 'username,name', 'access_token': access_token})
                        debug_info[f'instagram_details_{ig_id}'] = ig_resp.json()
            return JsonResponse(debug_info)
        except Exception as e:
            return JsonResponse({'error': str(e), 'partial_data': debug_info}, status=500)

    @action(detail=False, methods=['get'])
    def instagram_login(self, request):
        APP_ID = getattr(settings, 'FACEBOOK_APP_ID', '') 
        REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI', '')
        SCOPES = ['instagram_content_publish', 'pages_show_list', 'instagram_basic', 'public_profile']
        SCOPE_STR = ','.join(SCOPES)
        state_data = {'user_id': request.user.id, 'nonce': 'postless_auth'}
        state_json = json.dumps(state_data)
        state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
        auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?client_id={APP_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPE_STR}&response_type=code&state={state_encoded}"
        return redirect(auth_url)

    @action(detail=False, methods=['get', 'post'], permission_classes=[AllowAny], authentication_classes=[])
    def instagram_callback(self, request):
        if request.method == "GET" and request.GET.get("hub.mode"):
            mode = request.GET.get("hub.mode")
            token = request.GET.get("hub.verify_token")
            challenge = request.GET.get("hub.challenge")
            VERIFY_TOKEN = getattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "postless_webhook_verify_7fA9kL2026")
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return HttpResponse(challenge, content_type="text/plain")
            return HttpResponseForbidden("Verify token mismatch")
        if request.method == "GET" and (request.GET.get("error_code") or request.GET.get("error")):
            error_msg = request.GET.get("error_message") or request.GET.get("error_description") or "Unknown error"
            return redirect(f'/connections/?error={urlencode({"msg": error_msg})}')
        if request.method == "GET" and request.GET.get("code"):
            code = request.GET.get("code")
            state_encoded = request.GET.get("state")
            user = request.user
            if not user.is_authenticated and state_encoded:
                try:
                    state_json = base64.urlsafe_b64decode(state_encoded).decode()
                    state_data = json.loads(state_json)
                    user_id = state_data.get('user_id')
                    if user_id:
                        user = User.objects.get(id=user_id)
                except Exception as e:
                    pass
            if not user or not user.is_authenticated:
                return redirect('/accounts/login/?next=/connections/')
            APP_ID = getattr(settings, 'FACEBOOK_APP_ID', '')
            APP_SECRET = getattr(settings, 'FACEBOOK_APP_SECRET', '')
            REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI', '')
            token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
            params = {'client_id': APP_ID, 'redirect_uri': REDIRECT_URI, 'client_secret': APP_SECRET, 'code': code}
            try:
                resp = requests.get(token_url, params=params)
                data = resp.json()
                if 'error' in data:
                    return JsonResponse({'error': 'Token Exchange Failed', 'details': data}, status=400)
                short_token = data['access_token']
                long_token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
                long_params = {'grant_type': 'fb_exchange_token', 'client_id': APP_ID, 'client_secret': APP_SECRET, 'fb_exchange_token': short_token}
                long_resp = requests.get(long_token_url, params=long_params)
                long_data = long_resp.json()
                access_token = long_data.get('access_token', short_token)
                pages_url = "https://graph.facebook.com/v18.0/me/accounts"
                pages_params = {'access_token': access_token, 'fields': 'name,id,instagram_business_account{id,username}'}
                pages_resp = requests.get(pages_url, params=pages_params)
                pages_data = pages_resp.json()
                connected = False
                if 'data' in pages_data:
                    for page in pages_data['data']:
                        if 'instagram_business_account' in page:
                            ig_account = page['instagram_business_account']
                            ig_account_id = ig_account['id']
                            username = ig_account.get('username', 'Unknown')
                            SocialAccount.objects.update_or_create(user=user, platform='Instagram', account_id=ig_account_id, defaults={'account_name': username, 'access_token': access_token})
                            connected = True
                            break 
                if connected:
                    return redirect('/connections/')
                else:
                    return redirect('/connections/?warning=No+Instagram+Business+Account+Found.+Please+ensure+your+Instagram+is+connected+to+a+Facebook+Page.')
            except Exception as e:
                return JsonResponse({'error': 'Internal Server Error', 'details': str(e)}, status=500)
        if request.method == "POST":
            return HttpResponse("OK")
        return HttpResponseForbidden("Invalid request")

    @action(detail=False, methods=['get'])
    def youtube_login(self, request):
        CLIENT_ID = getattr(settings, 'YOUTUBE_CLIENT_ID', '')
        REDIRECT_URI = getattr(settings, 'YOUTUBE_REDIRECT_URI', '')
        SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
        flow = google_auth_oauthlib.flow.Flow.from_client_config({"web": {"client_id": CLIENT_ID, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [REDIRECT_URI]}}, scopes=SCOPES)
        flow.redirect_uri = REDIRECT_URI
        state_data = {'user_id': request.user.id, 'nonce': 'youtube_auth'}
        state_json = json.dumps(state_data)
        state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
        authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', state=state_encoded)
        return redirect(authorization_url)

    @action(detail=False, methods=['get'])
    def youtube_callback(self, request):
        state_encoded = request.GET.get('state')
        user = request.user
        # views.py içinde hem instagram_callback hem youtube_callback için:
        if not user.is_authenticated and state_encoded:
            try:
                # ... decode işlemleri ...
                user = User.objects.get(id=user)
                # KRİTİK EKSİK BURASI:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            except Exception:
                pass
        if not user or not user.is_authenticated:
             return redirect('/accounts/login/?next=/connections/')
        CLIENT_ID = getattr(settings, 'YOUTUBE_CLIENT_ID', '')
        CLIENT_SECRET = getattr(settings, 'YOUTUBE_CLIENT_SECRET', '')
        REDIRECT_URI = getattr(settings, 'YOUTUBE_REDIRECT_URI', '')
        SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config({"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [REDIRECT_URI]}}, scopes=SCOPES)
            flow.redirect_uri = REDIRECT_URI
            authorization_response = request.build_absolute_uri()
            if 'http:' in authorization_response and not settings.DEBUG:
                 authorization_response = authorization_response.replace('http:', 'https:')
            flow.fetch_token(authorization_response=authorization_response)
            credentials = flow.credentials
            youtube = googleapiclient.discovery.build('youtube', 'v3', credentials=credentials)
            channels_response = youtube.channels().list(mine=True, part='snippet,contentDetails,statistics').execute()
            if 'items' in channels_response:
                channel = channels_response['items'][0]
                channel_id = channel['id']
                channel_title = channel['snippet']['title']
                SocialAccount.objects.update_or_create(user=user, platform='YouTube', account_id=channel_id, defaults={'account_name': channel_title, 'access_token': credentials.token, 'refresh_token': credentials.refresh_token, 'expires_at': credentials.expiry})
                return redirect('/connections/')
            else:
                return JsonResponse({'error': 'No YouTube channel found.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': 'YouTube Auth Error', 'details': str(e)}, status=500)

@login_required
@subscription_required
def connections_page(request):
    instagram_account = SocialAccount.objects.filter(user=request.user, platform='Instagram').first()
    youtube_account = SocialAccount.objects.filter(user=request.user, platform='YouTube').first()
    return render(request, 'connections.html', {
        'instagram_account': instagram_account,
        'youtube_account': youtube_account
    })

@login_required
@subscription_required
def disconnect_account(request, platform):
    if request.method == 'POST':
        account = SocialAccount.objects.filter(user=request.user, platform=platform).first()
        if account:
            account.delete()
            messages.success(request, f'{platform} account has been disconnected.')
        else:
            messages.error(request, f'No {platform} account was found to disconnect.')
    return redirect('connections')

@csrf_exempt
def instagram_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == getattr(settings, 'META_WEBHOOK_VERIFY_TOKEN', 'postless_verify_token'):
            return HttpResponse(challenge, status=200)
        return HttpResponse("Invalid verify token", status=403)
    elif request.method == "POST":
        return HttpResponse("Event received", status=200)
    return HttpResponse("Method not allowed", status=405)
