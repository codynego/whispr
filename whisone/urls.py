# unified/urls.py
from django.urls import path


# Generic integration views
from .views import (
    IntegrationListView,
    IntegrationDeleteView,
    IntegrationDeactivateView,
    GmailOAuthInitView,
    GmailOAuthCallbackView,
)

urlpatterns = [
    # === Gmail OAuth ===
    path("integrations/gmail/init/", GmailOAuthInitView.as_view(), name="gmail-oauth-init"),
    path("integrations/gmail/callback/", GmailOAuthCallbackView.as_view(), name="gmail-oauth-callback"),

    # === Integration Management ===
    path("integrations/", IntegrationListView.as_view(), name="integrations-list"),
    path("integrations/<int:pk>/delete/", IntegrationDeleteView.as_view(), name="integration-delete"),
    path("integrations/<int:pk>/deactivate/", IntegrationDeactivateView.as_view(), name="integration-deactivate"),
]
