from django.urls import path
from .views import AssistantTaskListCreateView, AssistantTaskDetailView, AssistantDueTaskView, AssistantConfigView
from .views import AssistantChatView, AutomationListCreateView, AutomationDetailView, AutomationTriggerView, AutomationToggleView

urlpatterns = [
    path("tasks/", AssistantTaskListCreateView.as_view(), name="assistant-task-list-create"),
    path("tasks/<int:pk>/", AssistantTaskDetailView.as_view(), name="assistant-task-detail"),
    path("tasks/due/", AssistantDueTaskView.as_view(), name="assistant-task-due"),

    path('chat/', AssistantChatView.as_view(), name='assistant-chat'),

    path('config/', AssistantConfigView.as_view(), name='assistant-config'),

    path("automations/", AutomationListCreateView.as_view(), name="automation-list-create"),
    path("automations/<int:pk>/", AutomationDetailView.as_view(), name="automation-detail"),
    path("automations/<int:pk>/trigger/", AutomationTriggerView.as_view(), name="automation-trigger"),
    path("automations/<int:pk>/toggle/", AutomationToggleView.as_view(), name="automation-toggle"),

    
]
