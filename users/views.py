from rest_framework import viewsets
from .models import User, SocialAccount
from .serializers import UserSerializer, SocialAccountSerializer
from django.shortcuts import redirect, render
from django.conf import settings
from django.http import JsonResponse
import requests
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required

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
        Redirects the user to Instagram's OAuth authorization page.
        """
        # Replace these with your actual App ID and Redirect URI from Meta Developer Portal
        INSTAGRAM_APP_ID = getattr(settings, 'INSTAGRAM_APP_ID', 'YOUR_APP_ID')
        REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI', 'https://yourdomain.com/api/social-accounts/instagram_callback/')
        
        # Scopes required for basic display and publishing (adjust as needed)
        # For Instagram Basic Display: user_profile, user_media
        # For Instagram Graph API (Business): instagram_basic, instagram_content_publish, pages_show_list
        SCOPE = 'instagram_basic,instagram_content_publish,pages_show_list'
        
        auth_url = (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={INSTAGRAM_APP_ID}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"scope={SCOPE}&"
            f"response_type=code&"
            f"state=some_random_state_string" # Should be randomized for security
        )
        
        return redirect(auth_url)

    @action(detail=False, methods=['get'])
    def instagram_callback(self, request):
        """
        Handles the callback from Instagram after user authorization.
        Exchanges the authorization code for an access token.
        """
        code = request.GET.get('code')
        error = request.GET.get('error')
        
        if error:
            return Response({'error': error, 'description': request.GET.get('error_description')}, status=400)
            
        if not code:
            return Response({'error': 'No code provided'}, status=400)

        INSTAGRAM_APP_ID = getattr(settings, 'INSTAGRAM_APP_ID', 'YOUR_APP_ID')
        INSTAGRAM_CLIENT_SECRET = getattr(settings, 'INSTAGRAM_CLIENT_SECRET', 'YOUR_APP_SECRET')
        REDIRECT_URI = getattr(settings, 'INSTAGRAM_REDIRECT_URI', 'https://yourdomain.com/api/social-accounts/instagram_callback/')

        # Exchange code for access token
        token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        params = {
            'client_id': INSTAGRAM_APP_ID,
            'redirect_uri': REDIRECT_URI,
            'client_secret': INSTAGRAM_CLIENT_SECRET,
            'code': code
        }
        
        try:
            response = requests.get(token_url, params=params)
            data = response.json()
            
            if 'access_token' in data:
                access_token = data['access_token']
                # Ideally, you would now fetch the user's profile info to get their ID
                # and then save/update the SocialAccount model.
                
                # Example: Fetch User Info (This part depends on whether you use Basic Display or Graph API)
                # user_info_url = f"https://graph.instagram.com/me?fields=id,username&access_token={access_token}"
                # user_info = requests.get(user_info_url).json()
                
                # Save to DB (Simplified)
                # SocialAccount.objects.create(
                #     user=request.user,
                #     platform='Instagram',
                #     access_token=access_token,
                #     # ... other fields
                # )
                
                return Response({'message': 'Instagram connected successfully!', 'data': data})
            else:
                return Response({'error': 'Failed to retrieve access token', 'details': data}, status=400)
                
        except Exception as e:
            return Response({'error': str(e)}, status=500)

@login_required
def connections_page(request):
    instagram_connected = SocialAccount.objects.filter(user=request.user, platform='Instagram').exists()
    return render(request, 'connections.html', {'instagram_connected': instagram_connected})
