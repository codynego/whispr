from celery import shared_task
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model

from .executor import Executor
from .task_planner import TaskPlanner
from .response_generator import ResponseGenerator
from .memory_extractor import MemoryExtractor
from .knowledge_vault_manager import KnowledgeVaultManager
from .memory_integrator import MemoryIntegrator

from .models import Integration
from assistant.models import AssistantMessage

User = get_user_model()


@shared_task
def process_user_message(user_id: int, message: str):
    print("📩 Processing message for user:", user_id)

    # -------------------------------------------------------------------------
    # 0️⃣ Load user + integration
    # -------------------------------------------------------------------------
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="gmail").first()

    google_creds = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": integration.refresh_token if integration else None,
        "access_token": integration.access_token if integration else None,
    }
    print("🔐 Google credentials loaded:", google_creds)

    # -------------------------------------------------------------------------
    # 1️⃣ MEMORY EXTRACTION — understand the user's message
    # -------------------------------------------------------------------------
    extractor = MemoryExtractor(api_key=settings.OPENAI_API_KEY)
    extractor_output = extractor.extract(user, message)
    print("🧠 Memory Extractor Output:", extractor_output)

    # -------------------------------------------------------------------------
    # 2️⃣ KNOWLEDGE VAULT — find context + decide needed external data
    # -------------------------------------------------------------------------
    vault = KnowledgeVaultManager()
    vault_result = vault.query(
        intent=extractor_output.get("intent"),
        entities=extractor_output.get("entities", {})
    )
    print("📚 Knowledge Vault Result:", vault_result)

    # -------------------------------------------------------------------------
    # 3️⃣ TASK PLANNER — determine actions
    # -------------------------------------------------------------------------
    planner = TaskPlanner(api_key=settings.OPENAI_API_KEY)
    task_plan = planner.create_plan(
        extractor_output=extractor_output,
        vault_output=vault_result,
        user=user
    )
    print("🗂️ Task Plan:", task_plan)

    # -------------------------------------------------------------------------
    # 4️⃣ EXECUTOR — perform the tasks
    # -------------------------------------------------------------------------
    executor = Executor(
        user=user,
        gmail_creds=google_creds,
        calendar_creds=google_creds
    )

    print("⚙️ Executing tasks...")
    executor_results = executor.execute_tasks(task_plan)
    print("✔️ Executor Results:", executor_results)

    # -------------------------------------------------------------------------
    # 5️⃣ RESPONSE GENERATOR — craft natural reply
    # -------------------------------------------------------------------------
    response_gen = ResponseGenerator(api_key=settings.OPENAI_API_KEY)
    print("💬 Generating response...")
    response_text = response_gen.generate(
        user=user,
        user_message=message,
        executor_results=executor_results,
        vault_context=vault_result
    )
    print("📝 Final Response:", response_text)

    # -------------------------------------------------------------------------
    # 6️⃣ MEMORY INTEGRATOR — store new memories
    # -------------------------------------------------------------------------
    if extractor_output.get("should_store_memory"):
        mem_integrator = MemoryIntegrator()
        mem_integrator.store(
            user=user,
            memory_data=extractor_output.get("memory_data", {})
        )
        print("💾 Memory stored:", extractor_output.get("memory_data"))

    # -------------------------------------------------------------------------
    # 7️⃣ Save assistant reply
    # -------------------------------------------------------------------------
    AssistantMessage.objects.create(
        user=user,
        role="assistant",
        content=response_text
    )

    print("🎉 Done processing message.")
    return response_text
