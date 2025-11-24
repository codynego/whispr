# tasks.py
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from users.models import User
from whatsapp.tasks import send_whatsapp_text

# -----------------------
# Day 0: Welcome Message
# -----------------------
@shared_task
def send_welcome_message(user_id):
    user = User.objects.get(id=user_id)
    message = (
        f"Hi {user.first_name}! 👋\n"
        "Welcome to Whisone — your AI memory and assistant on WhatsApp.\n"
        "You can send me tasks, notes, reminders, or emails — and I’ll remember them for you.\n\n"
        "Try sending your first note or reminder now!\n"
        "Example: 'Remind me to call John tomorrow at 10am'"
    )
    send_whatsapp_text(user_id=user.id, text=message)
    # Schedule Day 1 follow-up
    schedule_day1_followup.delay(user_id)

# -----------------------
# Day 1: Follow-Up
# -----------------------
@shared_task
def schedule_day1_followup(user_id):
    user = User.objects.get(id=user_id)
    # Check if user already interacted
    if user.first_interaction_time:
        # User engaged; skip to Day 3 invite
        schedule_day3_invite.delay(user_id)
        return

    message = (
        f"Hey {user.first_name}! 👋 Have you tried sending your first task or note to Whisone yet?\n"
        "Example: 'Remind me to call John tomorrow at 10am'."
    )
    send_whatsapp_text(user_id=user.id, text=message)
    # Schedule Day 2 follow-up 24 hours later
    schedule_day2_followup.apply_async((user_id,), eta=timezone.now() + timedelta(hours=24))

# -----------------------
# Day 2: Follow-Up
# -----------------------
@shared_task
def schedule_day2_followup(user_id):
    user = User.objects.get(id=user_id)
    if user.first_interaction_time:
        # User engaged; skip Day 2 & go to Day 3 invite
        schedule_day3_invite.delay(user_id)
        return

    message = (
        f"Hi {user.name}! 👋 Just a reminder — Whisone can also summarize your emails and reminders.\n"
        "Send me one thing today — a task, note, or email — and I’ll show you instantly how it works!"
    )
    send_whatsapp_text(user_id=user.id, text=message)
    # Schedule Day 3 invite 24 hours later
    schedule_day3_invite.apply_async((user_id,), eta=timezone.now() + timedelta(hours=24))

# -----------------------
# Day 3: Founders Circle Invite
# -----------------------
@shared_task
def schedule_day3_invite(user_id):
    user = User.objects.get(id=user_id)
    # Only send invite if user has at least one interaction
    if not user.first_interaction_time:
        # Optional: could send a “last chance” nudge or skip
        return

    message = (
        f"Congratulations {user.first_name}! 🎉\n"
        "You’ve sent your first task/note and experienced your first win with Whisone.\n"
        "I’m inviting you to our exclusive Founders Circle — a private group where you’ll:\n"
        "✔️ Influence features\n"
        "✔️ Get early updates\n"
        "✔️ Access premium perks\n\n"
        "Reply YES to join!"
    )
    send_whatsapp_text(user_id=user.id, text=message)

# -----------------------
# Utility function to trigger welcome on signup
# -----------------------
def trigger_welcome(user_id):
    # Call this function immediately after user signs up
    send_welcome_message.delay(user_id)
