from django.urls import path
from .views import AssistantTaskListView, AssistantTaskDetailView, create_task

urlpatterns = [
    path('tasks/', AssistantTaskListView.as_view(), name='assistant-task-list'),
    path('tasks/<int:pk>/', AssistantTaskDetailView.as_view(), name='assistant-task-detail'),
    path('tasks/create/', create_task, name='assistant-task-create'),
]
