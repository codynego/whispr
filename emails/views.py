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
from rest_framework import generics, permissions
from .models import UserEmailRule
from .serializers import UserEmailRuleSerializer


import json
import jwt
from django.views import View
from django.http import JsonResponse
from django.conf import settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth import get_user_model
from google_auth_oauthlib.flow import Flow
from rest_framework import generics, permissions, filters
from rest_framework.pagination import PageNumberPagination







# === CONFIG ===
REDIRECT_URI = "http://localhost:3000/dashboard/settings/integrations/callbacks"
CLIENT_SECRET_FILE = "emails/credentials/client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


class GmailOAuthInitView(generics.GenericAPIView):
    """Step 1: Start OAuth flow and return Google Auth URL."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, provider):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "User not authenticated"}, status=401)

        # Encode user ID into the state parameter
        state_data = {"uid": urlsafe_base64_encode(force_bytes(request.user.id))}
        state_str = json.dumps(state_data)

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state_str,
        )

        return JsonResponse({"url": auth_url})


class GmailOAuthCallbackView(generics.GenericAPIView):
    """Step 2: Handle Google's redirect and store tokens."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")

        if not code:
            return JsonResponse({"error": "Missing authorization code"}, status=400)

        # Decode state → user ID
        try:
            user = request.user
        except Exception as e:
            return JsonResponse({"error": f"Invalid state: {str(e)}"}, status=400)

        # Recreate the OAuth flow to fetch token
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

        try:
            flow.fetch_token(code=code)
        except Exception as e:
            return JsonResponse({"error": f"Token exchange failed: {str(e)}"}, status=400)

        creds = flow.credentials

        # Decode ID token to extract Gmail email
        decoded_token = jwt.decode(creds.id_token, options={"verify_signature": False})
        email = decoded_token.get("email")

        if not email:
            return JsonResponse({"error": "Could not extract email from token"}, status=400)

        # Save or update Gmail account
        EmailAccount.objects.update_or_create(
            user=user,
            provider="gmail",
            email_address=email,
            defaults={
                "email_address": email,
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_expires_at": creds.expiry,
            },
        )

        return JsonResponse({
            "message": "Gmail account connected successfully!",
            "email": email
        })


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



class EmailPagination(PageNumberPagination):
    page_size = 10  # default per page
    page_size_query_param = 'page_size'
    max_page_size = 100


class EmailListView(generics.ListAPIView):
    """
    List all emails for the authenticated user with filtering and pagination.
    Filters:
      - ?account=<account_id>
      - ?importance=high|medium|low
      - ?is_read=true|false
    Pagination:
      - ?page=<number>
      - ?page_size=<number>
    """
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EmailPagination

    def get_queryset(self):
        user = self.request.user
        queryset = Email.objects.filter(account__user=user)

        # Filter by email account
        account_id = self.request.query_params.get('account')
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        # Filter by importance
        importance = self.request.query_params.get('importance')
        if importance:
            queryset = queryset.filter(importance__iexact=importance)

        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')

        # Optional: order by most recent
        queryset = queryset.order_by('-received_at')

        return queryset



class EmailDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update an email"""
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Email.objects.filter(account__user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_read:
            instance.is_read = True
            instance.save(update_fields=["is_read"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    


from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from .tasks import sync_email_account
from .serializers import EmailSyncSerializer


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sync_emails(request):
    """
    Trigger email sync for the authenticated user's accounts.
    """
    serializer = EmailSyncSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    account_id = serializer.validated_data['account_id']

    # Optional: confirm user actually has an account for this provider
    from .models import EmailAccount
    try:
        account = EmailAccount.objects.get(user=request.user, id=account_id, is_active=True)
    except EmailAccount.DoesNotExist:
        return Response(
            {"error": f"No active account found for user."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Trigger async Celery task (no need for authorization_code)
    task = sync_email_account.delay(account.id)

    return Response(
        {
            "message": f"Email sync started successfully.",

        },
        status=status.HTTP_202_ACCEPTED,
    )

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



class UserEmailRuleListCreateView(generics.ListCreateAPIView):
    """List all rules for the current user or create a new one."""
    serializer_class = UserEmailRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserEmailRule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserEmailRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific rule."""
    serializer_class = UserEmailRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserEmailRule.objects.filter(user=self.request.user)



class DeactivateEmailAccountView(generics.UpdateAPIView):
    """
    PATCH /api/emails/deactivate/<int:pk>/
    Deactivates a connected email account.
    """
    queryset = EmailAccount.objects.all()
    serializer_class = EmailAccountSerializer
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        account = self.get_object()

        # Optional: only allow the owner to deactivate their own account
        if hasattr(account, "user") and account.user != request.user:
            return Response(
                {"detail": "You are not authorized to deactivate this account."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Deactivate the account
        account.is_active = False
        account.save(update_fields=["is_active"])

        return Response(
            {"detail": f"Email account '{account.email}' has been deactivated."},
            status=status.HTTP_200_OK
        )