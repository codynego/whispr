from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction # Import for database safety
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
from .file_command_handler import handle_file_command
# Assuming AvatarConversation and AvatarMessage are available (from your context)
from avatars.models import Avatar, AvatarConversation, AvatarMessage
# Assuming this is the existing async task for Avatar replies (from your context)
from avatars.services.chat_engine import generate_avatar_reply 
from .models import Integration
from assistant.models import AssistantMessage # I assume this is for general assistant chat

User = get_user_model()

# --- Utility Function to get/create Avatar Conversation (for re-use) ---
def get_or_create_avatar_conversation(user, avatar):
    """Fetches or creates an active conversation for a user and an Avatar."""
    # Note: Using the user's ID as a reliable visitor_id for logged-in users.
    conversation, created = AvatarConversation.objects.get_or_create(
        avatar=avatar,
        visitor_id=str(user.id),
        ended_at=None,
        defaults={"user": user, 'prompted_login': False}
    )
    return conversation

@shared_task
def process_user_message(user_id: int, message: str):
    print(f"📩 Processing message for user {user_id}: {message}")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        print(f"User with ID {user_id} not found.")
        return

    # -----------------------------
    # 0️⃣ COMMAND & CONTEXT CHECK
    # -----------------------------

    # --- A. SWITCH COMMAND ---
    if message.startswith("switch"):
        # Format: /switch [handle]
        try:
            # Extract the avatar handle from the message (e.g., from "/switch genius_avatar")
            handle = message.split()[1].lower()
            avatar = Avatar.objects.filter(handle=handle).first()

            if avatar:
                # 1. Update the user's current chat context
                user.current_avatar = avatar
                user.save(update_fields=['current_avatar'])
                
                # 2. Get/Create the conversation record
                get_or_create_avatar_conversation(user, avatar)

                response_text = f"You are now chatting with **{avatar.name}**."
                
                # Send the response back to the user via AssistantMessage
                AssistantMessage.objects.create(
                    user=user,
                    role="assistant",
                    content=response_text
                )
                print(f"✨ Switched user to chat with Avatar: {avatar.name}")
                return response_text # Exit the task after handling the command
            else:
                response_text = f"Avatar with handle '{handle}' not found or is inaccessible."
                AssistantMessage.objects.create(user=user, role="assistant", content=response_text)
                return response_text
        except IndexError:
            response_text = "Usage: /switch [avatar_handle]"
            AssistantMessage.objects.create(user=user, role="assistant", content=response_text)
            return response_text
            
    # --- B. CHAT WITH AVATAR CONTEXT ---
    if user.current_avatar != "whisone":
        avatar_handle = user.current_avatar
        avatar = Avatar.objects.filter(handle=avatar_handle).first()
        if not avatar:
            response_text = f"Avatar with handle '{avatar_handle}' not found or is inaccessible."
            AssistantMessage.objects.create(user=user, role="assistant", content=response_text)
            return response_text
        print(f"💬 User is currently chatting with Avatar: {avatar.name}")
        
        try:
            conversation = get_or_create_avatar_conversation(user, avatar)

            # 1. Save visitor message (user's message)
            visitor_message = AvatarMessage.objects.create(
                conversation=conversation, 
                role="visitor", 
                content=message
            )

            # 2. Trigger async response generation for the Avatar
            task_id = generate_avatar_reply.delay(
                conversation_id=str(conversation.id),
                user_message_id=str(visitor_message.id),
                whatsapp_mode=False  # Set to True if this is from WhatsApp
            )
            return f"Avatar processing (Task ID: {task_id})"

        except Exception as e:
            print(f"Error processing Avatar message: {e}")
            AssistantMessage.objects.create(
                user=user, 
                role="assistant", 
                content=f"An error occurred while chatting with {avatar.name}: {e}"
            )
            return f"Avatar error."


    # -------------------------------------------------------------------------
    # If the flow reaches here, it means the user is chatting with the default Assistant.
    # The original Assistant logic proceeds below.
    # -------------------------------------------------------------------------
    print("🤖 Processing message with default Assistant logic.")

    # -------------------------------------------------------------------------
    # 1️⃣ Load integrations
    # ... (Original logic remains the same)
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
    # ... (Original logic remains the same)
    # -------------------------------------------------------------------------
    extractor = MemoryExtractor(api_key=settings.OPENAI_API_KEY)
    extractor_output = extractor.extract(user=user, content=message, source_type="user_message")
    print("🧠 Memory Extractor Output:", extractor_output)

    # -------------------------------------------------------------------------
    # 3️⃣ MEMORY INGESTION
    # ... (Original logic remains the same)
    # -------------------------------------------------------------------------
    ingestor = MemoryIngestor(user=user)
    ingestor.ingest(extractor_output)
    print("✅ Memory ingested into KV.")
    
    # -------------------------------------------------------------------------
    # 4️⃣ TASK PLANNER & FRAME BUILDER
    # ... (Original logic remains the same)
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
    # ... (Original logic remains the same)
    # -------------------------------------------------------------------------
    executor = Executor(user=user, gmail_creds=google_creds, calendar_creds=google_creds)
    print("⚙️ Executing ready tasks...")
    executor_results = executor.execute_task_frames(ready_tasks)
    print("✔️ Executor Results:", executor_results)

    # -------------------------------------------------------------------------
    # 6️⃣ QUERY MEMORY
    # ... (Original logic remains the same)
    # -------------------------------------------------------------------------
    querier = KVQueryManager(user=user)
    kv_context = querier.query(keyword=message, limit=5)
    print("📖 KV Query Context:", kv_context)

    # -------------------------------------------------------------------------
    # 7️⃣ RESPONSE GENERATOR
    # ... (Original logic remains the same)
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

    # 8️⃣ Save Assistant Response (Added for completeness of default flow)
    AssistantMessage.objects.create(
        user=user,
        role="assistant",
        content=response_text
    )

    return response_text