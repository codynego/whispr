from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from .executor import Executor
from .task_planner import TaskPlanner
from .task_frame_builder import TaskFrameBuilder
from .response_generator import ResponseGenerator
from .memory_extractor import MemoryExtractor
from .memory_ingestor import MemoryIngestor
from .natural_resolver import NaturalResolver
from .services.calendar_service import GoogleCalendarService
from .memory_querier import MemoryQueryManager
from assistant.models import AssistantMessage
from .models import Integration
from whatsapp.tasks import send_whatsapp_text

User = get_user_model()


@shared_task
def handle_memory(user_id: int, message: str):
    """
    Async memory ingestion task.
    Extracts memory from user message and saves it as a Memory object.
    """
    try:
        user = User.objects.get(id=user_id)
        previous_messages_qs = (
            AssistantMessage.objects
            .filter(user=user, role="user")
            .order_by("-created_at")[:2]
        )
        # Reverse to maintain chronological order (oldest first)
        previous_contents = [msg.content for msg in reversed(previous_messages_qs)]
        previous_content_text = "\n".join(previous_contents) if previous_contents else None

    except User.DoesNotExist:
        print(f"[handle_memory] User {user_id} not found.")
        return

    extractor = MemoryExtractor(api_key=settings.OPENAI_API_KEY)
    ingestor = MemoryIngestor(user=user)

    extractor_output = extractor.extract(content=message, previous_content=previous_content_text)
    print("[handle_memory] Extracted memory:", extractor_output)

    # Ensure we have a dict, not a list
    if not isinstance(extractor_output, dict):
        print("[handle_memory] Extractor output not a dict, skipping ingestion.")
        return

    # Build memory dict
    memory_data = {
        "raw_text": extractor_output.get("raw_text") or extractor_output.get("summary") or message,
        "summary": extractor_output.get("summary") or extractor_output.get("raw_text") or message,
        "memory_type": extractor_output.get("memory_type", "general"),
        "emotion": extractor_output.get("emotion"),
        "sentiment": extractor_output.get("sentiment"),
        "importance": extractor_output.get("importance", 0.5),
        "context": extractor_output.get("context", {"source_type": "user_message"}),
    }

    # Ingest single memory dict
    ingestor.ingest(memory_data)
    print("[handle_memory] Memory ingested successfully.")



@shared_task
def process_user_message(user_id: int, message: str, whatsapp_mode: bool = False) -> str:
    """
    Main user message processing.
    Memory ingestion is handled asynchronously.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        print(f"[process_user_message] User {user_id} not found.")
        return

    # --- Calendar & Resolver Setup ---
    integration = Integration.objects.filter(user=user, provider="gmail").first()
    google_creds = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": integration.refresh_token if integration else None,
        "access_token": integration.access_token if integration else None,
    }
    calendar_service = GoogleCalendarService(**google_creds)
    resolver = NaturalResolver(user=user, api_key=settings.OPENAI_API_KEY, calendar_service=calendar_service)

    # --- Trigger async memory ingestion ---
    handle_memory.delay(user_id=user.id, message=message)

    # --- Task Planning & Frame Building ---
    planner = TaskPlanner(api_key=settings.OPENAI_API_KEY)
    raw_task_plan = planner.plan_tasks(user=user, user_message=message)
    print("[process_user_message] Planned tasks:", raw_task_plan)

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

    # --- Execute Tasks ---
    executor = Executor(user=user, gmail_creds=google_creds, calendar_creds=google_creds)
    executor_results = executor.execute_task_frames(ready_tasks)

    # --- Query Memory (can now include already ingested memories) ---
    querier = MemoryQueryManager(user=user)
    kv_context = querier.query(
    keyword=message,
    task_plan=raw_task_plan,  # Pass the planned tasks
    limit=5
)

    # --- Generate Response ---
    response_gen = ResponseGenerator(api_key=settings.OPENAI_API_KEY)
    response_text = response_gen.generate_response(
        user=user,
        user_message=message,
        executor_results=executor_results,
        vault_context=kv_context,
        missing_fields=[tf.get("missing_fields") for tf in skipped_tasks if tf.get("missing_fields")]
    )

    # --- Save Assistant Response ---
    AssistantMessage.objects.create(
        user=user,
        role="assistant",
        content=response_text
    )

    # --- WhatsApp Delivery ---
    if whatsapp_mode:
        send_whatsapp_text.delay(user_id=user.id, text=response_text)

    return response_text
