from django.urls import path
from .views import (
    EmailAccountListView, EmailAccountDetailView,
    EmailListView, EmailDetailView,
    sync_emails, analyze_importance
)

urlpatterns = [
    path('accounts/', EmailAccountListView.as_view(), name='email-account-list'),
    path('accounts/<int:pk>/', EmailAccountDetailView.as_view(), name='email-account-detail'),
    path('messages/', EmailListView.as_view(), name='email-list'),
    path('messages/<int:pk>/', EmailDetailView.as_view(), name='email-detail'),
    path('sync/', sync_emails, name='email-sync'),
    path('messages/<int:email_id>/analyze/', analyze_importance, name='email-analyze'),
]
