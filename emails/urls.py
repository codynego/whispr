from django.urls import path
from .views import (
    EmailAccountListView, EmailAccountDetailView,
    EmailListView, EmailDetailView,
    sync_emails, analyze_importance,
    get_oauth_url, oauth_callback,
    UserEmailRuleListCreateView, UserEmailRuleDetailView,
)

urlpatterns = [
    path('accounts/', EmailAccountListView.as_view(), name='email-account-list'),
    path('accounts/<int:pk>/', EmailAccountDetailView.as_view(), name='email-account-detail'),
    path('messages/', EmailListView.as_view(), name='email-list'),
    path('messages/<int:pk>/', EmailDetailView.as_view(), name='email-detail'),
    path('sync/', sync_emails, name='email-sync'),
    path('messages/<int:email_id>/analyze/', analyze_importance, name='email-analyze'),

    path("oauth-url/<str:provider>/", get_oauth_url, name="get-oauth-url"),
    path("oauth-callback/", oauth_callback, name="oauth-callback"),

    path("user-rules/", UserEmailRuleListCreateView.as_view(), name="user-rules-list"),
    path("user-rules/<int:pk>/", UserEmailRuleDetailView.as_view(), name="user-rule-detail"),
]
