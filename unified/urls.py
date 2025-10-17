# urls.py
from django.urls import path
from .views import AllAccountsView, UnifiedMessagesView, DashboardOverviewAPIView

urlpatterns = [
    path('dashboard/overview/', DashboardOverviewAPIView.as_view(), name='dashboard-overview'),
    path('accounts/all/', AllAccountsView.as_view(), name='all_accounts'),
    path('messages/', UnifiedMessagesView.as_view(), name='unified-messages'),
]
