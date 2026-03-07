from rest_framework import viewsets
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
from urllib.parse import urlencode

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
        Redirects to Facebook Login to authorize Instagram Business permissions.
        REQUIRED for publishing content.
        """
        # We use FACEBOOK_APP_ID for Instagram Graph API login
        APP_ID = getattr(settings, 'FACEBOOK_APP_ID', '') 
        REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI', '')
        
        # Minimal Scopes to test connection
        # If this works, the issue is specifically with Instagram permissions
        SCOPES = [
            'instagram_content_publish',
            'pages_show_list',
            'pages_read_engagement',
            'public_profile'
        ]
        SCOPE_STR = ','.join(SCOPES)
        
        # Encode user ID into state
        state_data = {'user_id': request.user.id, 'nonce': 'postless_auth'}
        state_json = json.dumps(state_data)
        state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        auth_url = (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={APP_ID}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"scope={SCOPE_STR}&"
            f"response_type=code&"
            f"state={state_encoded}"
        )
        
        return redirect(auth_url)

    @action(detail=False, methods=['get', 'post'], permission_classes=[AllowAny], authentication_classes=[])
    def instagram_callback(self, request):
        """
        Handles callback from Facebook Login, finds the connected Instagram Business Account.
        """
        # --- Webhook Verification ---
        if request.method == "GET" and request.GET.get("hub.mode"):
            mode = request.GET.get("hub.mode")
            token = request.GET.get("hub.verify_token")
            challenge = request.GET.get("hub.challenge")
            VERIFY_TOKEN = getattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "postless_webhook_verify_7fA9kL2026")
            if mode == "subscribe" and token == VERIFY_TOKEN:
                return HttpResponse(challenge, content_type="text/plain")
            return HttpResponseForbidden("Verify token mismatch")

        # --- Error Handling ---
        if request.method == "GET" and (request.GET.get("error_code") or request.GET.get("error")):
            error_msg = request.GET.get("error_message") or request.GET.get("error_description") or "Unknown error"
            print(f"DEBUG: OAuth Error: {error_msg}")
            return redirect(f'/connections/?error={urlencode({"msg": error_msg})}')

        # --- OAuth Callback ---
        if request.method == "GET" and request.GET.get("code"):
            code = request.GET.get("code")
            state_encoded = request.GET.get("state")
            
            # Recover User from State
            user = request.user
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
                return redirect('/accounts/login/?next=/connections/')

            # Use Facebook Credentials
            APP_ID = getattr(settings, 'FACEBOOK_APP_ID', '')
            APP_SECRET = getattr(settings, 'FACEBOOK_APP_SECRET', '')
            REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI', '')

            # 1. Exchange Code for Short-Lived Token
            token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
            params = {
                'client_id': APP_ID,
                'redirect_uri': REDIRECT_URI,
                'client_secret': APP_SECRET,
                'code': code
            }
            
            try:
                resp = requests.get(token_url, params=params)
                data = resp.json()
                
                if 'error' in data:
                    return JsonResponse({'error': 'Token Exchange Failed', 'details': data}, status=400)
                
                short_token = data['access_token']

                # 2. Exchange for Long-Lived Token (60 days)
                long_token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
                long_params = {
                    'grant_type': 'fb_exchange_token',
                    'client_id': APP_ID,
                    'client_secret': APP_SECRET,
                    'fb_exchange_token': short_token
                }
                long_resp = requests.get(long_token_url, params=long_params)
                long_data = long_resp.json()
                access_token = long_data.get('access_token', short_token)

                # 3. Find Connected Instagram Business Account
                # First, get user's pages
                pages_url = "https://graph.facebook.com/v18.0/me/accounts"
                pages_resp = requests.get(pages_url, params={'access_token': access_token})
                pages_data = pages_resp.json()
                
                connected = False
                
                if 'data' in pages_data:
                    for page in pages_data['data']:
                        page_id = page['id']
                        # Check for IG Business Account on this page
                        ig_url = f"https://graph.facebook.com/v18.0/{page_id}"
                        ig_params = {
                            'fields': 'instagram_business_account',
                            'access_token': access_token
                        }
                        ig_resp = requests.get(ig_url, params=ig_params)
                        ig_data = ig_resp.json()
                        
                        if 'instagram_business_account' in ig_data:
                            ig_account_id = ig_data['instagram_business_account']['id']
                            
                            # Get IG Username
                            user_url = f"https://graph.facebook.com/v18.0/{ig_account_id}"
                            user_resp = requests.get(user_url, params={'fields': 'username', 'access_token': access_token})
                            user_data = user_resp.json()
                            username = user_data.get('username', 'Unknown')
                            
                            # Save to DB
                            SocialAccount.objects.update_or_create(
                                user=user,
                                platform='Instagram',
                                account_id=ig_account_id, # This is the correct ID for publishing
                                defaults={
                                    'account_name': username,
                                    'access_token': access_token,
                                }
                            )
                            connected = True
                            print(f"DEBUG: Connected Instagram Business Account: {username} ({ig_account_id})")
                            break # Connect the first one found
                
                if connected:
                    return redirect('/connections/')
                else:
                    # Fallback: If no IG account found, save the FB User ID just to show "Connected"
                    # This confirms OAuth worked, even if permissions were missing for IG
                    fb_me_url = "https://graph.facebook.com/v18.0/me"
                    fb_me_resp = requests.get(fb_me_url, params={'fields': 'name,id', 'access_token': access_token})
                    fb_data = fb_me_resp.json()
                    
                    SocialAccount.objects.update_or_create(
                        user=user,
                        platform='Instagram', # Labeling as IG for now to show in UI
                        account_id=fb_data.get('id'),
                        defaults={
                            'account_name': f"FB: {fb_data.get('name')}",
                            'access_token': access_token,
                        }
                    )
                    return redirect('/connections/?warning=No+Instagram+Business+Account+Found')

            except Exception as e:
                return JsonResponse({'error': 'Internal Server Error', 'details': str(e)}, status=500)

        if request.method == "POST":
            return HttpResponse("OK")

        return HttpResponseForbidden("Invalid request")

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
        state_data = {'user_id': request.user.id, 'nonce': 'youtube_auth'}
        state_json = json.dumps(state_data)
        state_encoded = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state_encoded
        )
        
        return redirect(authorization_url)

    @action(detail=False, methods=['get'])
    def youtube_callback(self, request):
        """
        Handles the callback from Google/YouTube.
        """
        state_encoded = request.GET.get('state')
        
        # Recover User
        user = request.user
        if not user.is_authenticated and state_encoded:
            try:
                state_json = base64.urlsafe_b64decode(state_encoded).decode()
                state_data = json.loads(state_json)
                user_id = state_data.get('user_id')
                if user_id:
                    user = User.objects.get(id=user_id)
            except:
                pass
        
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
                state=state_encoded
            )
            
            flow.redirect_uri = REDIRECT_URI
            
            authorization_response = request.build_absolute_uri()
            if 'http:' in authorization_response and not settings.DEBUG:
                 authorization_response = authorization_response.replace('http:', 'https:')

            flow.fetch_token(authorization_response=authorization_response)
            credentials = flow.credentials
            
            youtube = googleapiclient.discovery.build('youtube', 'v3', credentials=credentials)
            channels_response = youtube.channels().list(
                mine=True,
                part='snippet,contentDetails,statistics'
            ).execute()
            
            if 'items' in channels_response:
                channel = channels_response['items'][0]
                channel_id = channel['id']
                channel_title = channel['snippet']['title']
                
                SocialAccount.objects.update_or_create(
                    user=user,
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
                return JsonResponse({'error': 'No YouTube channel found.'}, status=400)

        except Exception as e:
            return JsonResponse({'error': 'YouTube Auth Error', 'details': str(e)}, status=500)

@login_required
def connections_page(request):
    instagram_account = SocialAccount.objects.filter(user=request.user, platform='Instagram').first()
    youtube_account = SocialAccount.objects.filter(user=request.user, platform='YouTube').first()
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
