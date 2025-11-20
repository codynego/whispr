from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Note, Todo, Reminder
from .utils.embedding_utils import generate_embedding

@receiver(pre_save, sender=Note)
def update_note_embedding(sender, instance, **kwargs):
    if instance.content and (instance.embedding is None or instance.pk is None):
        instance.embedding = generate_embedding(instance.content)

@receiver(pre_save, sender=Todo)
def update_todo_embedding(sender, instance, **kwargs):
    if instance.task and (instance.embedding is None or instance.pk is None):
        instance.embedding = generate_embedding(instance.task)

@receiver(pre_save, sender=Reminder)
def update_reminder_embedding(sender, instance, **kwargs):
    if instance.text and (instance.embedding is None or instance.pk is None):
        instance.embedding = generate_embedding(instance.text)
