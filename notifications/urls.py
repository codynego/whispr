from django.urls import path
from .views import (
    NotificationListView, NotificationDetailView,
    mark_as_read, mark_all_as_read, unread_count,
    NotificationPreferenceView
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('<int:pk>/read/', mark_as_read, name='notification-mark-read'),
    path('mark-all-read/', mark_all_as_read, name='notification-mark-all-read'),
    path('unread-count/', unread_count, name='notification-unread-count'),

    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences')
]
