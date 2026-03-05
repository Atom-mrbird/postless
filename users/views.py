from rest_framework import viewsets

from postless.settings import INSTAGRAM_APP_ID, INSTAGRAM_CLIENT_SECRET, INSTAGRAM_REDIRECT_URI
from .models import User, SocialAccount
from .serializers import UserSerializer, SocialAccountSerializer
from django.shortcuts import redirect, render
import requests
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import json
import base64
import os


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class SocialAccountViewSet(viewsets.ModelViewSet):
    queryset = SocialAccount.objects.all()
    serializer_class = SocialAccountSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def instagram_login(self, request):
        """
        Instagram Platform OAuth — instagram_business_* scope'ları için
        api.instagram.com/oauth/authorize kullanılmalı.
        """
        APP_ID = getattr(settings, 'INSTAGRAM_APP_ID', '1640423764050164')
        REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI',
                               'https://clementine-unlegalized-nichole.ngrok-free.dev/api/social-accounts/instagram_callback/')

        SCOPE = ','.join([
            'instagram_business_basic',
            'instagram_business_content_publish',
            'instagram_business_manage_messages',
            'instagram_business_manage_comments',
            'instagram_business_manage_insights',
        ])

        # Encode user ID into state to persist across redirect
        state_data = {'user_id': request.user.id, 'nonce': 'postless_auth_state'}
        state_json = json.dumps(state_data)
        state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()

        # ✅ Instagram Platform için doğru URL: api.instagram.com
        auth_url = (
            f"https://api.instagram.com/oauth/authorize"
            f"?client_id={APP_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&scope={SCOPE}"
            f"&response_type=code"
            f"&state={state_encoded}"
        )

        return redirect(auth_url)

    @action(detail=False, methods=['get', 'post'], permission_classes=[AllowAny], authentication_classes=[])
    def instagram_callback(self, request):
        """
        İki amaçla kullanılır:
        1. Meta Webhook doğrulama (hub.mode=subscribe)
        2. OAuth callback (code → access_token)
        """
        # --- Webhook doğrulama ---
        if request.method == "GET" and request.GET.get("hub.mode"):
            mode = request.GET.get("hub.mode")
            token = request.GET.get("hub.verify_token") or request.GET.get("hub_verify_token")
            challenge = request.GET.get("hub.challenge")

            VERIFY_TOKEN = getattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "postless_webhook_verify_7fA9kL2026")
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return HttpResponse(challenge, content_type="text/plain")
            return HttpResponseForbidden("Verify token eşleşmedi")

        # --- OAuth callback: code → access_token ---
        if request.method == "GET" and request.GET.get("code"):
            code = request.GET.get("code")
            state_encoded = request.GET.get("state")
            
            user = request.user
            
            # If session auth failed, try to recover user from state
            if not user.is_authenticated and state_encoded:
                try:
                    state_json = base64.urlsafe_b64decode(state_encoded).decode()
                    state_data = json.loads(state_json)
                    user_id = state_data.get('user_id')
                    if user_id:
                        user = User.objects.get(id=user_id)
                        print(f"DEBUG: Recovered user from state: {user.username}")
                except Exception as e:
                    print(f"DEBUG: Failed to decode state: {e}")

            if not user or not user.is_authenticated:
                print("DEBUG: User could not be authenticated even with state recovery.")
                return redirect('/accounts/login/?next=/connections/')

            APP_ID = getattr(settings, 'INSTAGRAM_APP_ID', '1640423764050164')
            APP_SECRET = getattr(settings, 'INSTAGRAM_CLIENT_SECRET', '')
            REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI',
                                   'https://clementine-unlegalized-nichole.ngrok-free.dev/api/social-accounts/instagram_callback/')

            # Kısa ömürlü token al
            token_response = requests.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": INSTAGRAM_APP_ID,
                    "client_secret": INSTAGRAM_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": REDIRECT_URI,
                    "code": code,
                }
            )
            token_data = token_response.json()

            if "error_message" in token_data:
                print(f"DEBUG: Error getting short token: {token_data}")
                return JsonResponse({"error": token_data}, status=400)

            short_token = token_data.get("access_token")
            ig_user_id = token_data.get("user_id")

            # Uzun ömürlü token al (60 gün geçerli)
            long_token_response = requests.get(
                "https://graph.instagram.com/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": INSTAGRAM_CLIENT_SECRET,
                    "access_token": short_token,
                }
            )
            long_token_data = long_token_response.json()
            long_token = long_token_data.get("access_token", short_token)

            # Kullanıcı adını al
            profile_response = requests.get(
                f"https://graph.instagram.com/v18.0/{ig_user_id}",
                params={
                    "fields": "name,username",
                    "access_token": long_token,
                }
            )
            profile = profile_response.json()
            username = profile.get("username") or profile.get("name", "Instagram User")

            print(f"DEBUG: Saving Instagram account for user {user.username}: {username} ({ig_user_id})")

            # Veritabanına kaydet
            obj, created = SocialAccount.objects.update_or_create(
                user=user, # Use the recovered user object
                platform='Instagram',
                account_id=str(ig_user_id),
                defaults={
                    'account_name': username,
                    'access_token': long_token,
                }
            )
            print(f"DEBUG: Account saved. Created: {created}")

            return redirect('/connections/')

        # --- Webhook POST eventleri ---
        if request.method == "POST":
            return HttpResponse("OK")

        return HttpResponseForbidden("Geçersiz istek")

    @action(detail=False, methods=['get'])
    def youtube_login(self, request):
        """
        Redirects the user to Google's OAuth authorization page for YouTube.
        """
        CLIENT_ID = getattr(settings, 'YOUTUBE_CLIENT_ID', '')
        REDIRECT_URI = getattr(settings, 'YOUTUBE_REDIRECT_URI', '')

        SCOPES = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.readonly'
        ]

        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            {
                "web": {
                    "client_id": CLIENT_ID,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            },
            scopes=SCOPES
        )

        flow.redirect_uri = REDIRECT_URI
        
        # Encode user ID into state
        state_data = {'user_id': request.user.id, 'nonce': os.urandom(8).hex()}
        state_json = json.dumps(state_data)
        state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state_encoded
        )

        # Still try to save to session as backup
        request.session['youtube_oauth_state'] = state
        return redirect(authorization_url)

    @action(detail=False, methods=['get'])
    def youtube_callback(self, request):
        """
        Handles the callback from Google/YouTube.
        """
        # Try to get state from URL first
        state = request.GET.get('state')
        
        # Fallback to session if URL state is missing (unlikely in callback)
        if not state:
            state = request.session.get('youtube_oauth_state')
            
        if not state:
            return JsonResponse({'error': 'Missing state parameter'}, status=400)

        # Recover User from State
        user = request.user
        if not user.is_authenticated:
            try:
                state_json = base64.urlsafe_b64decode(state).decode()
                state_data = json.loads(state_json)
                user_id = state_data.get('user_id')
                if user_id:
                    user = User.objects.get(id=user_id)
                    print(f"DEBUG: Recovered YouTube user from state: {user.username}")
            except Exception as e:
                print(f"DEBUG: Failed to decode YouTube state: {e}")
        
        if not user or not user.is_authenticated:
             return redirect('/accounts/login/?next=/connections/')

        CLIENT_ID = getattr(settings, 'YOUTUBE_CLIENT_ID', '')
        CLIENT_SECRET = getattr(settings, 'YOUTUBE_CLIENT_SECRET', '')
        REDIRECT_URI = getattr(settings, 'YOUTUBE_REDIRECT_URI', '')

        SCOPES = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.readonly'
        ]

        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                {
                    "web": {
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [REDIRECT_URI],
                    }
                },
                scopes=SCOPES,
                state=state
            )

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

                SocialAccount.objects.update_or_create(
                    user=user, # Use recovered user
                    platform='YouTube',
                    account_id=channel_id,
                    defaults={
                        'account_name': channel_title,
                        'access_token': credentials.token,
                        'refresh_token': credentials.refresh_token,
                        'expires_at': credentials.expiry
                    }
                )
                return redirect('/connections/')
            else:
                return JsonResponse({'error': 'No YouTube channel found for this account.'}, status=400)

        except Exception as e:
            print(f"DEBUG: YouTube Callback Error: {str(e)}")
            return JsonResponse({'error': 'YouTube Auth Error', 'details': str(e)}, status=500)


@login_required
def connections_page(request):
    instagram_account = SocialAccount.objects.filter(user=request.user, platform='Instagram').first()
    youtube_account = SocialAccount.objects.filter(user=request.user, platform='YouTube').first()
    
    print(f"DEBUG: Connections page for {request.user.username}")
    print(f"DEBUG: Instagram Account: {instagram_account}")
    print(f"DEBUG: YouTube Account: {youtube_account}")

    return render(request, 'connections.html', {
        'instagram_account': instagram_account,
        'youtube_account': youtube_account
    })


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