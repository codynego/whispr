from rest_framework import serializers
from .models import Note, Reminder, Todo, Integration

# ----------------------
# Note
# ----------------------
class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'user', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

# ----------------------
# Reminder
# ----------------------
class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = ['id', 'user', 'text', 'remind_at', 'completed', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

# ----------------------
# Todo
# ----------------------
class TodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Todo
        fields = ['id', 'user', 'task', 'done', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']



class IntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Integration
        fields = "__all__"


from whisone.models import DailySummary


class DailySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySummary
        fields = [
            "id",
            "summary_date",
            "summary_text",
            "raw_data",
            "created_at",
        ]
