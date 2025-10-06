from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import EmailAccount, Email
from .serializers import EmailAccountSerializer, EmailSerializer, EmailSyncSerializer
from .tasks import sync_email_account, analyze_email_importance_task
from rest_framework.permissions import IsAuthenticated
from urllib.parse import urlencode, parse_qs
from django.conf import settings
import requests
from django.http import JsonResponse

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OUTLOOK_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
OUTLOOK_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
REDIRECT_URI_GMAIL = "http://localhost:3000/dashboard/settings/integrations/callbacks/"
REDIRECT_URI_OUTLOOK = "http://localhost:3000/dashboard/settings/integrations/callbacks/"  # Standardize to frontend

def get_oauth_url(request, provider):
    """Return OAuth URL for frontend to redirect the user"""
    if provider == "gmail":
        params = {
            "client_id": settings.GMAIL_CLIENT_ID,
            "redirect_uri": REDIRECT_URI_GMAIL,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": "provider=gmail",
        }
        url = f"{GMAIL_AUTH_URL}?{urlencode(params)}"
    elif provider == "outlook":
        params = {
            "client_id": settings.OUTLOOK_CLIENT_ID,
            "redirect_uri": REDIRECT_URI_OUTLOOK,  # Fixed: Use frontend URL
            "response_type": "code",
            "scope": "https://graph.microsoft.com/Mail.Read",
            "response_mode": "query",
            "state": "provider=outlook",
        }
        url = f"{OUTLOOK_AUTH_URL}?{urlencode(params)}"
    else:
        return JsonResponse({"error": "Invalid provider"}, status=400)
    
    return JsonResponse({"url": url})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def oauth_callback(request):
    """Handle OAuth redirect and save tokens"""
    code = request.query_params.get("code")
    state = request.query_params.get("state", "")
    provider = request.query_params.get("provider")  # From frontend forward

    # Fallback: Parse provider from state if not provided
    if not provider and state:
        parsed_state = parse_qs(state)
        provider = parsed_state.get("provider", [None])[0]

    if settings.DEBUG:
        print("provider:", provider)
        print("code:", code[:20] + "..." if code else None)  # Truncate for security
        print("secret:", settings.GMAIL_CLIENT_SECRET[:10] + "..." if settings.GMAIL_CLIENT_SECRET else None)

    if not code or not provider:
        return Response({"error": "Missing parameters"}, status=400)
    
    access_token = refresh_token = email_address = None
    
    try:
        if provider == "gmail":
            data = {
                "code": code,
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI_GMAIL,
                "grant_type": "authorization_code",
            }
            if settings.DEBUG:
                print("Data for token exchange:", {k: v[:20] + "..." if k in ["code", "client_secret"] else v for k, v in data.items()})
            r = requests.post(GMAIL_TOKEN_URL, data=data)
            if settings.DEBUG:
                print("Response status:", r.status_code, "Response from token exchange:", r.text)
            r.raise_for_status()
            tokens = r.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            
            # Get user's Gmail address
            headers = {"Authorization": f"Bearer {access_token}"}
            profile = requests.get("https://www.googleapis.com/gmail/v1/users/me/profile", headers=headers).json()  # Fixed: Use /me/profile
            email_address = profile.get("emailAddress")
        
        elif provider == "outlook":
            data = {
                "code": code,
                "client_id": settings.OUTLOOK_CLIENT_ID,
                "client_secret": settings.OUTLOOK_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI_OUTLOOK,
                "grant_type": "authorization_code",
            }
            if settings.DEBUG:
                print("Data for token exchange:", {k: v[:20] + "..." if k in ["code", "client_secret"] else v for k, v in data.items()})
            r = requests.post(OUTLOOK_TOKEN_URL, data=data)
            if settings.DEBUG:
                print("Response status:", r.status_code, "Response from token exchange:", r.text)
            r.raise_for_status()
            tokens = r.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            
            # Get user's Outlook email
            headers = {"Authorization": f"Bearer {access_token}"}
            profile = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers).json()
            email_address = profile.get("mail") or profile.get("userPrincipalName")
        else:
            return Response({"error": "Invalid provider"}, status=400)
        
        if not access_token:
            return Response({"error": "Failed to obtain access token"}, status=400)
        
        if not email_address:
            return Response({"error": "Unable to fetch email address"}, status=400)
        
        # Save or update EmailAccount
        account, created = EmailAccount.objects.update_or_create(
            user=request.user,
            email_address=email_address,
            defaults={
                "provider": provider,
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )
        
        return Response({
            "message": "Account connected successfully",
            "email": email_address,
            "provider": provider
        })
    
    except requests.exceptions.HTTPError as e:
        return Response({"error": f"Token exchange HTTP error: {e.response.status_code} - {e.response.text}"}, status=400)
    except requests.RequestException as e:
        return Response({"error": f"Token exchange failed: {str(e)}"}, status=400)
    except Exception as e:
        return Response({"error": f"Unexpected error: {str(e)}"}, status=500)


# Rest of the views remain unchanged...
class EmailAccountListView(generics.ListAPIView):
    """List all email accounts for the authenticated user"""
    serializer_class = EmailAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)


class EmailAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an email account"""
    serializer_class = EmailAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)


class EmailListView(generics.ListAPIView):
    """List all emails for the authenticated user"""
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Email.objects.filter(account__user=self.request.user)
        
        # Filter by importance
        importance = self.request.query_params.get('importance')
        if importance:
            queryset = queryset.filter(importance=importance)
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        return queryset


class EmailDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update an email"""
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Email.objects.filter(account__user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sync_emails(request):
    """Trigger email sync for user's accounts"""
    serializer = EmailSyncSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    provider = serializer.validated_data['provider']
    authorization_code = serializer.validated_data['authorization_code']
    
    # Trigger async task to sync emails
    task = sync_email_account.delay(request.user.id, provider, authorization_code)
    
    return Response({
        'message': 'Email sync initiated',
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def analyze_importance(request, email_id):
    """Trigger importance analysis for a specific email"""
    try:
        email = Email.objects.get(id=email_id, account__user=request.user)
    except Email.DoesNotExist:
        return Response({'error': 'Email not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Trigger async task to analyze importance
    task = analyze_email_importance_task.delay(email_id)
    
    return Response({
        'message': 'Importance analysis initiated',
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)