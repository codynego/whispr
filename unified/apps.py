from django.apps import AppConfig


class UnifiedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "unified"

    def ready(self):
        import unified.signals

