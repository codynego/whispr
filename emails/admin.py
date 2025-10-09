from django.contrib import admin
from .models import EmailAccount, Email, UserEmailRule
from whisprai.ai.embeddings import generate_email_embedding



@admin.register(UserEmailRule)
class UserEmailRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'rule_type', 'importance', 'is_active', 'created_at')
    list_filter = ('rule_type', 'importance', 'is_active')
    search_fields = ('name', 'value')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ('email_address', 'provider', 'user', 'is_active', 'last_synced', 'created_at')
    list_filter = ('provider', 'is_active')
    search_fields = ('email_address', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


# @admin.register(Email)
# class EmailAdmin(admin.ModelAdmin):
#     list_display = ('subject', 'sender', 'recipient', 'importance', 'is_read', 'received_at')
#     list_filter = ('importance', 'is_read', 'is_starred')
#     search_fields = ('subject', 'sender', 'recipient', 'body')
#     readonly_fields = ('message_id', 'created_at', 'updated_at', 'analyzed_at')
#     date_hierarchy = 'received_at'


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'importance', 'received_at', 'embedding_generated')
    list_filter = ('importance', 'is_read', 'is_starred', 'embedding_generated')
    search_fields = ('subject', 'sender', 'body')
    actions = ['generate_embeddings']

    @admin.action(description="Generate embeddings for selected emails")
    def generate_embeddings(self, request, queryset):
        count = 0
        for email in queryset:
            if not email.embedding_generated:
                embedding = generate_email_embedding(email)
                if embedding:
                    email.embedding = embedding
                    email.embedding_generated = True
                    email.save(update_fields=["embedding", "embedding_generated"])
                    count += 1
        self.message_user(request, f"✅ Generated embeddings for {count} emails.")

