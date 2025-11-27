# whisone/avatars/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ----------------------------
    # PUBLIC ACCESS ROUTE (MUST be first to catch unauthenticated, public traffic)
    # ----------------------------
    path("<slug:handle>/public/", views.AvatarRetrievePublicView.as_view(), name="avatar-retrieve-public"),
    
    # ----------------------------
    # HANDLE-BASED CONVENIENCE ROUTES (For UI components - Owner/Authenticated traffic)
    # ----------------------------
    
    # Avatar Detail, Settings, Analytics by Handle
    # This route is now implicitly for authenticated users only (AvatarRetrieveByHandleView)
    path("<slug:handle>/", views.AvatarRetrieveByHandleView.as_view(), name="avatar-retrieve-by-handle"),
    path("<slug:handle>/settings/", views.AvatarSettingsByHandleView.as_view(), name="avatar-settings-by-handle"),
    path("<slug:handle>/analytics/", views.AvatarAnalyticsByHandleView.as_view(), name="avatar-analytics-by-handle"),
    
    # Training, Chat, and History by Handle
    path("<slug:handle>/train/", views.AvatarTrainView.as_view(), name="avatar-train"),
    path("<slug:handle>/chat/", views.AvatarChatView.as_view(), name="avatar-chat"),
    path("<slug:handle>/history/", views.AvatarConversationHistoryView.as_view(), name="avatar-conversation-history"),
    
    # Sources by Handle
    path("<slug:handle>/sources/", views.AvatarSourceListCreateByHandleView.as_view(), name="avatar-source-list-create-by-handle"),
    
    # ----------------------------
    # Feature Endpoints
    # ----------------------------
    
    # Job Status (using 'id' as lookup_field in the view, not 'pk')
    path("training-jobs/<uuid:id>/status/", views.AvatarTrainingJobStatusView.as_view(), name="avatar-trainingjob-status"),
    
    # Owner Takeover (by conversation UUID)
    path("conversations/<uuid:pk>/takeover/", views.AvatarConversationTakeoverView.as_view(), name="avatar-conversation-takeover"),
    
    # ----------------------------
    # Core UUID Endpoints (Standard CRUD)
    # ----------------------------
    
    path("", views.AvatarListCreateView.as_view(), name="avatar-list-create"),
    path("<uuid:pk>/", views.AvatarRetrieveUpdateDestroyView.as_view(), name="avatar-detail"),

    path("sources/", views.AvatarSourceListCreateView.as_view(), name="avatar-source-list-create"),
    path("sources/<uuid:pk>/", views.AvatarSourceRetrieveUpdateDestroyView.as_view(), name="avatar-source-detail"),

    path("training-jobs/", views.AvatarTrainingJobListView.as_view(), name="avatar-trainingjob-list"),
    path("training-jobs/<uuid:pk>/", views.AvatarTrainingJobDetailView.as_view(), name="avatar-trainingjob-detail"),

    path("memory-chunks/", views.AvatarMemoryChunkListView.as_view(), name="avatar-memorychunk-list"),
    path("memory-chunks/<uuid:pk>/", views.AvatarMemoryChunkDetailView.as_view(), name="avatar-memorychunk-detail"),

    path("conversations/", views.AvatarConversationListCreateView.as_view(), name="avatar-conversation-list-create"),
    path("conversations/<uuid:pk>/", views.AvatarConversationRetrieveDestroyView.as_view(), name="avatar-conversation-detail"),

    path("messages/", views.AvatarMessageListCreateView.as_view(), name="avatar-message-list-create"),
    path("messages/<uuid:pk>/", views.AvatarMessageRetrieveView.as_view(), name="avatar-message-detail"),

    path("analytics/", views.AvatarAnalyticsListView.as_view(), name="avatar-analytics-list"),
    path("analytics/<uuid:pk>/", views.AvatarAnalyticsDetailView.as_view(), name="avatar-analytics-detail"),

    path("settings/<uuid:pk>/", views.AvatarSettingsRetrieveUpdateView.as_view(), name="avatar-settings-detail"),
]