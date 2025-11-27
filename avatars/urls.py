# whisone/avatars/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # whisone/avatars/urls.py
    path("<slug:handle>/chat/", views.AvatarChatView.as_view(), name="avatar-chat"),
    path("<slug:handle>/train/", views.AvatarTrainView.as_view(), name="avatar-train"),
    path("training-jobs/<uuid:id>/status/", views.AvatarTrainingJobStatusView.as_view(), name="avatar-trainingjob-status"),


    # ----------------------------
    # Avatar endpoints
    # ----------------------------
    path("", views.AvatarListCreateView.as_view(), name="avatar-list-create"),
    path("<uuid:pk>/", views.AvatarRetrieveUpdateDestroyView.as_view(), name="avatar-detail"),

    # ----------------------------
    # AvatarSource endpoints
    # ----------------------------
    path("sources/", views.AvatarSourceListCreateView.as_view(), name="avatar-source-list-create"),
    path("sources/<uuid:pk>/", views.AvatarSourceRetrieveUpdateDestroyView.as_view(), name="avatar-source-detail"),

    # ----------------------------
    # AvatarTrainingJob endpoints
    # ----------------------------
    path("training-jobs/", views.AvatarTrainingJobListView.as_view(), name="avatar-trainingjob-list"),
    path("training-jobs/<uuid:pk>/", views.AvatarTrainingJobDetailView.as_view(), name="avatar-trainingjob-detail"),

    # ----------------------------
    # AvatarMemoryChunk endpoints
    # ----------------------------
    path("memory-chunks/", views.AvatarMemoryChunkListView.as_view(), name="avatar-memorychunk-list"),
    path("memory-chunks/<uuid:pk>/", views.AvatarMemoryChunkDetailView.as_view(), name="avatar-memorychunk-detail"),

    # ----------------------------
    # AvatarConversation endpoints
    # ----------------------------
    path("conversations/", views.AvatarConversationListCreateView.as_view(), name="avatar-conversation-list-create"),
    path("conversations/<uuid:pk>/", views.AvatarConversationRetrieveDestroyView.as_view(), name="avatar-conversation-detail"),

    # ----------------------------
    # AvatarMessage endpoints
    # ----------------------------
    path("messages/", views.AvatarMessageListCreateView.as_view(), name="avatar-message-list-create"),
    path("messages/<uuid:pk>/", views.AvatarMessageRetrieveView.as_view(), name="avatar-message-detail"),

    # ----------------------------
    # AvatarAnalytics endpoints
    # ----------------------------
    path("analytics/", views.AvatarAnalyticsListView.as_view(), name="avatar-analytics-list"),
    path("analytics/<uuid:pk>/", views.AvatarAnalyticsDetailView.as_view(), name="avatar-analytics-detail"),

    # ----------------------------
    # AvatarSettings endpoints
    # ----------------------------
    path("settings/<uuid:pk>/", views.AvatarSettingsRetrieveUpdateView.as_view(), name="avatar-settings-detail"),
]
