# unified/urls.py

from django.urls import path
from .views import (
    # Notes
    NoteListCreateView,
    NoteDetailView,

    # Reminders
    ReminderListCreateView,
    ReminderDetailView,

    # Todos
    TodoListCreateView,
    TodoDetailView,

    # Whisone NLP Assistant
    WhisoneMessageView,

    # Integrations & OAuth
    GmailOAuthInitView,
    GmailOAuthCallbackView,
    IntegrationListView,
    IntegrationDeleteView,
    IntegrationDeactivateView,
    OverviewView,
    UnifiedSearchView,
    UploadedFileListCreateView, UploadedFileDetailView, UploadedFileReprocessView
)

urlpatterns = [


    path("overview/", OverviewView.as_view(), name="overview"),
    path("search/", UnifiedSearchView.as_view(), name="unified-search"),

    path('files/', UploadedFileListCreateView.as_view(), name='uploadedfile-list-create'),
    path('files/<int:pk>/', UploadedFileDetailView.as_view(), name='uploadedfile-detail'),
    path('files/<int:pk>/reprocess/', UploadedFileReprocessView.as_view(), name='uploadedfile-reprocess'),


    # ======================
    # Notes
    # ======================
    path("notes/", NoteListCreateView.as_view(), name="note-list-create"),
    path("notes/<int:pk>/", NoteDetailView.as_view(), name="note-detail"),

    # ======================
    # Reminders
    # ======================
    path("reminders/", ReminderListCreateView.as_view(), name="reminder-list-create"),
    path("reminders/<int:pk>/", ReminderDetailView.as_view(), name="reminder-detail"),

    # ======================
    # Todos
    # ======================
    path("todos/", TodoListCreateView.as_view(), name="todo-list-create"),
    path("todos/<int:pk>/", TodoDetailView.as_view(), name="todo-detail"),

    # ======================
    # Whisone AI Assistant
    # ======================
    path("assistant/message/", WhisoneMessageView.as_view(), name="whisone-message"),

    # ======================
    # Integrations - OAuth & Management
    # ======================
    # Gmail OAuth Flow
    path("integrations/gmail/init/", GmailOAuthInitView.as_view(), name="gmail-oauth-init"),
    path("integrations/gmail/callback/", GmailOAuthCallbackView.as_view(), name="gmail-oauth-callback"),

    # List all integrations
    path("integrations/", IntegrationListView.as_view(), name="integrations-list"),

    # Manage specific integration
    path("integrations/<int:pk>/delete/", IntegrationDeleteView.as_view(), name="integration-delete"),
    path("integrations/<int:pk>/deactivate/", IntegrationDeactivateView.as_view(), name="integration-deactivate"),
    
]