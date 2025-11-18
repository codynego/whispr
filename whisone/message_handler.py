from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from .executor import Executor
from .task_planner import TaskPlanner
from .task_frame_builder import TaskFrameBuilder
from .response_generator import ResponseGenerator
from .memory_extractor import MemoryExtractor
from .knowledge_vault_manager import KnowledgeVaultManager
from .memory_integrator import MemoryIntegrator

from .models import Integration
from assistant.models import AssistantMessage

User = get_user_model()


@shared_task
def process_user_message(user_id: int, message: str):
    print(f"📩 Processing message for user {user_id}: {message}")

    # -------------------------------------------------------------------------
    # 0️⃣ Load user + integrations
    # -------------------------------------------------------------------------
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="gmail").first()

    google_creds = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": integration.refresh_token if integration else None,
        "access_token": integration.access_token if integration else None,
    }

    # -------------------------------------------------------------------------
    # 1️⃣ MEMORY EXTRACTION — parse user message
    # -------------------------------------------------------------------------
    extractor = MemoryExtractor(api_key=settings.OPENAI_API_KEY)
    extractor_output = extractor.extract(content=message, source_type="user_message")
    print("🧠 Memory Extractor Output:", extractor_output)

    # -------------------------------------------------------------------------
    # 2️⃣ KNOWLEDGE VAULT — ingest memory
    # -------------------------------------------------------------------------
    vault = KnowledgeVaultManager(user=user)
    vault.ingest_memory(
        content=message,
        entities=extractor_output.get("entities", []),
        summary=extractor_output.get("summary", ""),
        prefs=extractor_output.get("preferences", {})
    )

    # -------------------------------------------------------------------------
    # 3️⃣ TASK PLANNER — determine actions
    # -------------------------------------------------------------------------
    planner = TaskPlanner(api_key=settings.OPENAI_API_KEY)
    raw_task_plan = planner.plan_tasks(user=user, user_message=message)
    print("🗂️ Raw Task Plan:", raw_task_plan)

    # -------------------------------------------------------------------------
    # 3.1️⃣ TASK FRAME BUILDER — validate & detect missing fields
    # -------------------------------------------------------------------------
    frame_builder = TaskFrameBuilder()
    task_frames = [
        frame_builder.build(
            intent=step.get("intent", ""),
            action=step.get("action"),
            parameters=step.get("params", {})
        )
        for step in raw_task_plan
    ]
    print("🗂️ Task Frames:", task_frames)

    ready_tasks = [tf for tf in task_frames if tf["ready"]]
    skipped_tasks = [tf for tf in task_frames if not tf["ready"]]
    if skipped_tasks:
        print("⚠️ Tasks skipped due to missing fields:", skipped_tasks)

    # -------------------------------------------------------------------------
    # 4️⃣ EXECUTOR — execute ready tasks
    # -------------------------------------------------------------------------
    executor = Executor(user=user, gmail_creds=google_creds, calendar_creds=google_creds)
    print("⚙️ Executing ready tasks...")
    executor_results = executor.execute_task_frames(ready_tasks)
    print("✔️ Executor Results:", executor_results)

    # -------------------------------------------------------------------------
    # 4.1️⃣ Collect general_query results
    # -------------------------------------------------------------------------
    general_query_results = []
    for frame in ready_tasks:
        if frame.get("action") == "general_query":
            # Executor already runs it; fetch result from executor_results
            result = next((r["result"] for r in executor_results if r["action"] == "general_query"), None)
            if result:
                general_query_results.append(result)
    print("📖 General Query Results:", general_query_results)

    # -------------------------------------------------------------------------
    # 5️⃣ RESPONSE GENERATOR — craft reply
    # -------------------------------------------------------------------------
    response_gen = ResponseGenerator(api_key=settings.OPENAI_API_KEY)
    response_text = response_gen.generate_response(
        user=user,
        user_message=message,
        executor_results=executor_results,
        vault_context=general_query_results or vault.query(
            keyword=message,
            entities=extractor_output.get("entities", [])
        ),
        missing_fields=[tf["missing_fields"] for tf in skipped_tasks if tf["missing_fields"]]
    )
    print("📝 Final Response:", response_text)


    # 7️⃣ Save assistant reply
    # -------------------------------------------------------------------------
    AssistantMessage.objects.create(
        user=user,
        role="assistant",
        content=response_text
    )
    print("🎉 Done processing message.")

    return response_text
