# email_views.py
from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from google_auth_oauthlib.flow import Flow
import jwt, json

from unified.models import ChannelAccount
from unified.serializers import ChannelAccountSerializer


# === CONFIG ===
# REDIRECT_URI = "http://localhost:3000/dashboard/settings/integrations/callbacks"
REDIRECT_URI = "https://www.whisone.app/dashboard/settings/integrations/callbacks"
CLIENT_SECRET_FILE = "unified/credentials/client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
    "https://www.googleapis.com/auth/calendar.events",
]

# === Gmail OAuth ===
class GmailOAuthInitView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        state_data = {"uid": urlsafe_base64_encode(force_bytes(request.user.id))}
        state_str = json.dumps(state_data)

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state_str
        )
        return JsonResponse({"url": auth_url})


class GmailOAuthCallbackView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return JsonResponse({"error": "Missing authorization code"}, status=400)

        user = request.user

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        try:
            flow.fetch_token(code=code)
        except Exception as e:
            return JsonResponse({"error": f"Token exchange failed: {str(e)}"}, status=400)

        creds = flow.credentials
        decoded_token = jwt.decode(creds.id_token, options={"verify_signature": False})
        email_address = decoded_token.get("email")
        if not email_address:
            return JsonResponse({"error": "Could not extract email from token"}, status=400)

        # Save/update unified ChannelAccount
        account, created = ChannelAccount.objects.update_or_create(
            user=user,
            channel="email",
            provider="gmail",
            address_or_id=email_address,
            defaults={
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_expires_at": creds.expiry,
                "is_active": True
            }
        )

        return JsonResponse({
            "message": "Gmail connected successfully!",
            "account_id": account.id,
            "email": email_address
        })
