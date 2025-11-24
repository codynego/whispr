# from django.urls import path, include
# from unified.views import email_views, common_views

# urlpatterns = [
#     # Email connections
#     path("emails/oauth/init/", email_views.GmailOAuthInitView.as_view(), name="gmail-oauth-init"),
#     path("emails/oauth/callback/", email_views.GmailOAuthCallbackView.as_view(), name="gmail-oauth-callback"),

#     # WhatsApp connections
#     # path("whatsapp/connect/", whatsapp_views.WhatsAppConnectView.as_view(), name="whatsapp-connect"),
#     # path("whatsapp/callback/", whatsapp_views.WhatsAppCallbackView.as_view(), name="whatsapp-callback"),


#     # Channel accounts
#     path("accounts/", common_views.ChannelAccountListView.as_view(), name="channel-account-list"),
#     path("accounts/<int:pk>/", common_views.ChannelAccountDetailView.as_view(), name="channel-account-detail"),
#     path("accounts/<int:pk>/deactivate/", common_views.DeactivateChannelAccountView.as_view(), name="channel-account-deactivate"),

#     # Messages (unified for all channels)
#     path("messages/", common_views.MessageListView.as_view(), name="message-list"),
#     path("messages/<int:pk>/", common_views.MessageDetailView.as_view(), name="message-detail"),
#     path("messages/sync/", common_views.sync_messages, name="sync-messages"),

#     # Conversations
#     path("conversations/", common_views.ConversationListView.as_view(), name="conversation-list"),
#     path("conversations/<int:pk>/", common_views.ConversationDetailView.as_view(), name="conversation-detail"),

#     # Rules
#     path("rules/", common_views.UserMessageRuleListCreateView.as_view(), name="rule-list-create"),
#     path("rules/<int:pk>/", common_views.UserMessageRuleDetailView.as_view(), name="rule-detail"),

#     path("overview/", common_views.DashboardOverviewAPIView.as_view(), name="overview"),

#     path("send/", common_views.SendMessageView.as_view(), name="send_message")
# ]
