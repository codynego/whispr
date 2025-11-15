from celery import shared_task
from datetime import datetime

from .task_planner import TaskPlanner
from .executor import Executor
from .response_generator import ResponseGenerator
from django.conf import settings
from .models import Integration
from django.contrib.auth import get_user_model


User = get_user_model()

@shared_task
def process_user_message(user_id: int, message: str):

    print("Processing message for user:", user_id)
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="gmail").first()

    google_creds= {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": integration.refresh_token if integration else None,
        "access_token": integration.access_token if integration else None,
    }

    print("Google credentials:", google_creds)

    # 1️⃣ Plan tasks
    planner = TaskPlanner(openai_api_key=settings.OPENAI_API_KEY)
    task_plan = planner.plan_tasks(message)
    print("Task plan:", task_plan)

    # 2️⃣ Execute tasks
    executor = Executor(user, gmail_creds=google_creds, calendar_creds=google_creds)
    print("Executing tasks...")
    executor_results = executor.execute_task(task_plan)
    print("Executor results:", executor_results)

    # 3️⃣ Generate response
    response_gen = ResponseGenerator(openai_api_key=settings.OPENAI_API_KEY)
    print("Generating response...")
    response_text = response_gen.generate_response(message, executor_results)
    print("Generated response:", response_text)

    # 4️⃣ Store or send response to user (example: save in DB or send via WebSocket/WhatsApp)
    # UserResponse.objects.create(user=user, original_message=message, response_text=response_text)

    return response_text
