from django.urls import path
from .views import AssistantTaskListView, AssistantTaskDetailView, create_task, AssistantConfigView
from .views import AssistantChatView

urlpatterns = [
    path('tasks/', AssistantTaskListView.as_view(), name='assistant-task-list'),
    path('tasks/<int:pk>/', AssistantTaskDetailView.as_view(), name='assistant-task-detail'),
    path('tasks/create/', create_task, name='assistant-task-create'),

    path('chat/', AssistantChatView.as_view(), name='assistant-chat'),

    path('config/', AssistantConfigView.as_view(), name='assistant-config'),
    
]
