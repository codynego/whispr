from django.contrib import admin
from django.utils import timezone
from .models import EmailAccount, Email, UserEmailRule
from .utils import is_email_important  # your importance analyzer


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


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = (
        'subject', 
        'sender', 
        'importance', 
        'importance_score',
        'is_read', 
        'received_at', 
        'embedding_generated',
        'message_id',
    )
    list_filter = ('importance', 'is_read', 'is_starred', 'embedding_generated')
    search_fields = ('subject', 'sender', 'recipient', 'body')
    readonly_fields = ('message_id', 'created_at', 'updated_at', 'analyzed_at')
    date_hierarchy = 'received_at'
    actions = ['analyze_importance']

    @admin.action(description="Analyze importance and generate embeddings")
    def analyze_importance(self, request, queryset):
        """
        Generates importance scores, sets importance level,
        stores analysis text, and embeds selected emails.
        """
        count = 0
        for email in queryset:
            text = f"{email.subject}\n\n{email.body}"
            embedding, is_important, score = is_email_important(text)

            # Map score → importance level
            if score >= 0.85:
                importance_level = "critical"
            elif score >= 0.7:
                importance_level = "high"
            elif score >= 0.5:
                importance_level = "medium"
            else:
                importance_level = "low"

            email.embedding = embedding.tolist() if hasattr(embedding, "tolist") else embedding
            email.importance = importance_level
            email.importance_score = round(score, 3)
            email.importance_analysis = (
                f"Importance determined as {importance_level} "
                f"(score={score:.2f}, important={is_important})"
            )
            email.embedding_generated = True
            email.analyzed_at = timezone.now()
            email.save(update_fields=[
                "embedding", "importance", "importance_score",
                "importance_analysis", "embedding_generated", "analyzed_at"
            ])
            count += 1

        self.message_user(request, f"✅ Analyzed {count} emails for importance and embeddings.")
