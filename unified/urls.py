# urls.py
from django.urls import path
from .views import AllAccountsView, UnifiedMessagesView

urlpatterns = [
    path('accounts/all/', AllAccountsView.as_view(), name='all_accounts'),
    path('messages/', UnifiedMessagesView.as_view(), name='unified-messages'),
]
