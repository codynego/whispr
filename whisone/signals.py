from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Note, Todo, Reminder
from .utils.embedding_utils import generate_embedding


def record_user_interaction(instance):
    """
    Records the first time a user interacts with the system.
    Works for Notes, Todos, and Reminders.
    """
    user = instance.user  # all models must have a user FK

    if user and not user.first_interaction_time:
        user.first_interaction_time = timezone.now()
        user.save(update_fields=['first_interaction_time'])


# -------------------------
# NOTE Embedding + Interaction
# -------------------------
@receiver(pre_save, sender=Note)
def update_note_embedding(sender, instance, **kwargs):
    # generate embedding
    if instance.content and (instance.embedding is None or instance.pk is None):
        instance.embedding = generate_embedding(instance.content)

    # record first interaction
    record_user_interaction(instance)


# -------------------------
# TODO Embedding + Interaction
# -------------------------
@receiver(pre_save, sender=Todo)
def update_todo_embedding(sender, instance, **kwargs):
    # embedding generation
    if instance.task and (instance.embedding is None or instance.pk is None):
        instance.embedding = generate_embedding(instance.task)

    # record first interaction
    record_user_interaction(instance)


# -------------------------
# REMINDER Embedding + Interaction
# -------------------------
@receiver(pre_save, sender=Reminder)
def update_reminder_embedding(sender, instance, **kwargs):
    # embedding generation
    if instance.text and (instance.embedding is None or instance.pk is None):
        instance.embedding = generate_embedding(instance.text)

    # record first interaction
    record_user_interaction(instance)
