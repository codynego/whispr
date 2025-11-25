# urls.py
from django.urls import path
from avatars import views

urlpatterns = [
    # Dashboard
    path("api/avatars/", views.AvatarListCreateView.as_view(), name="avatar-list"),
    path("api/avatars/<uuid:id>/", views.AvatarDetailView.as_view(), name="avatar-detail"),

    # Public page
    path("api/public/@<str:handle>/", views.AvatarPublicDetailView.as_view(), name="avatar-public"),

    # Conversations & training
    path("api/avatars/<uuid:avatar_id>/conversations/", views.AvatarConversationListView.as_view()),
    path("api/avatars/<uuid:avatar_id>/training/", views.AvatarTrainingJobListView.as_view()),
    # path("api/avatars/<uuid:avatar_id>/retrain/", views.TriggerRetrainView.as_view()),
]