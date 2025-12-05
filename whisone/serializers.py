from rest_framework import serializers
from .models import Note, Reminder, Todo, Integration

# ----------------------
# Note
# ----------------------
from rest_framework import serializers
from .models import Note, Reminder, Todo, Integration, UploadedFile

# ----------------------
# Note
# ----------------------
class NoteSerializer(serializers.ModelSerializer):
    # 1. Define the dynamic field for the output
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        # 2. Return the Note's primary content field (content)
        # We truncate it slightly so the title isn't a massive blob of text
        if obj.title:
            return obj.title
        return obj.content[:100] if obj.content else "Untitled Note"

    class Meta:
        model = Note
        # FIX: The field 'title' must be explicitly listed in 'fields' 
        # when using SerializerMethodField.
        fields = ['id', 'user', 'content', 'created_at', 'updated_at', 'title']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'title']

# ----------------------
# Reminder
# ----------------------
class ReminderSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        # 2. Return the Reminder's primary content field (text)
        return obj.text

    class Meta:
        model = Reminder
        fields = ['id', 'user', 'text', 'remind_at', 'completed', 'created_at', 'updated_at', 'title']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'title']

# ----------------------
# Todo
# ----------------------
class TodoSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        # 2. Return the Todo's primary content field (task)
        return obj.task

    class Meta:
        model = Todo
        fields = ['id', 'user', 'task', 'done', 'created_at', 'updated_at', 'title']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'title']

# ----------------------
# UploadedFile
# ----------------------
class UploadedFileSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    
    def get_title(self, obj):
        # 2. Return the UploadedFile's primary identifier (original_filename)
        return obj.original_filename

    class Meta:
        model = UploadedFile
        fields = [
            "id",
            "file",
            "original_filename",
            "file_type",
            "size",
            "uploaded_at",
            "processed",
            "content",
            "title", # Must be included here
        ]
        read_only_fields = ["id", "original_filename", "file_type", "size", "uploaded_at", "processed", "content", "title"]


# --- Other serializers (Integration, DailySummary, FileChat) remain unchanged as they don't affect this issue ---


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




class FileChatSerializer(serializers.Serializer):
    query = serializers.CharField(
        max_length=2000,
        required=True,
        help_text="The question or message to ask about this file."
    )