from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from .executor import Executor
from .task_planner import TaskPlanner
from .task_frame_builder import TaskFrameBuilder
from .response_generator import ResponseGenerator
from .memory_extractor import MemoryExtractor
from .memory_integrator import MemoryIntegrator
from .natural_resolver import NaturalResolver
from .services.calendar_service import GoogleCalendarService
from .memory_ingestor import MemoryIngestor
from .memory_querier import KVQueryManager
from .file_command_handler import handle_file_command  # the handler from previous block

from .models import Integration
from assistant.models import AssistantMessage

User = get_user_model()

@shared_task
def process_user_message(user_id: int, message: str):
    print(f"📩 Processing message for user {user_id}: {message}")

    user = User.objects.get(id=user_id)

    # -----------------------------
    # 0️⃣ Check if message is a slash command
    # -----------------------------
    if message.startswith("/"):
        # Extract command type
        command = message.split()[0].lower()
        if command in ["/file", "/note", "/reminder", "/brain"]:
            # Remove the leading slash for the handler
            content = message[len(command):].strip()
            if command == "/file":
                response_text = handle_file_command(user, content)
            else:
                # Placeholder: you can implement handle_note_command etc.
                response_text = f"Command {command} received. (Handler not implemented yet.)"
            print(f"⚡ Slash command response: {response_text}")
            return response_text

    # -------------------------------------------------------------------------
    # 1️⃣ Load integrations
    # -------------------------------------------------------------------------
    integration = Integration.objects.filter(user=user, provider="gmail").first()
    google_creds = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": integration.refresh_token if integration else None,
        "access_token": integration.access_token if integration else None,
    }

    calendar_service = GoogleCalendarService(**google_creds)
    resolver = NaturalResolver(user=user, api_key=settings.OPENAI_API_KEY, calendar_service=calendar_service)

    # -------------------------------------------------------------------------
    # 2️⃣ MEMORY EXTRACTION — parse user message
    # -------------------------------------------------------------------------
    extractor = MemoryExtractor(api_key=settings.OPENAI_API_KEY)
    extractor_output = extractor.extract(user=user, content=message, source_type="user_message")
    print("🧠 Memory Extractor Output:", extractor_output)

    # -------------------------------------------------------------------------
    # 3️⃣ MEMORY INGESTION
    # -------------------------------------------------------------------------
    ingestor = MemoryIngestor(user=user)
    ingestor.ingest(extractor_output)
    print("✅ Memory ingested into KV.")

    # -------------------------------------------------------------------------
    # 4️⃣ TASK PLANNER & FRAME BUILDER
    # -------------------------------------------------------------------------
    planner = TaskPlanner(api_key=settings.OPENAI_API_KEY)
    raw_task_plan = planner.plan_tasks(user=user, user_message=message)
    frame_builder = TaskFrameBuilder(user=user, resolver=resolver, calendar_service=calendar_service)
    task_frames = [
        frame_builder.build(
            intent=step.get("intent", ""),
            action=step.get("action"),
            parameters=step.get("params", {})
        )
        for step in raw_task_plan
    ]
    ready_tasks = [tf for tf in task_frames if tf["ready"]]
    skipped_tasks = [tf for tf in task_frames if not tf["ready"]]
    if skipped_tasks:
        print("⚠️ Tasks skipped due to missing fields:", skipped_tasks)

    # -------------------------------------------------------------------------
    # 5️⃣ EXECUTOR
    # -------------------------------------------------------------------------
    executor = Executor(user=user, gmail_creds=google_creds, calendar_creds=google_creds)
    print("⚙️ Executing ready tasks...")
    executor_results = executor.execute_task_frames(ready_tasks)
    print("✔️ Executor Results:", executor_results)

    # -------------------------------------------------------------------------
    # 6️⃣ QUERY MEMORY
    # -------------------------------------------------------------------------
    querier = KVQueryManager(user=user)
    kv_context = querier.query(keyword=message, limit=5)
    print("📖 KV Query Context:", kv_context)

    # -------------------------------------------------------------------------
    # 7️⃣ RESPONSE GENERATOR
    # -------------------------------------------------------------------------
    response_gen = ResponseGenerator(api_key=settings.OPENAI_API_KEY)
    response_text = response_gen.generate_response(
        user=user,
        user_message=message,
        executor_results=executor_results,
        vault_context=kv_context,
        missing_fields=[tf["missing_fields"] for tf in skipped_tasks if tf["missing_fields"]]
    )
    print("📝 Final Response:", response_text)

    return response_text
