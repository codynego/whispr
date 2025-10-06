from celery import shared_task
from django.conf import settings
from django.utils import timezone
import openai
import logging
import time
from .models import AssistantTask

logger = logging.getLogger(__name__)


@shared_task
def process_assistant_task(task_id):
    """
    Process assistant tasks using OpenAI
    """
    try:
        task = AssistantTask.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        start_time = time.time()
        
        if not settings.OPENAI_API_KEY:
            raise ValueError('OpenAI API key not configured')
        
        openai.api_key = settings.OPENAI_API_KEY
        
        # Prepare prompt based on task type
        if task.task_type == 'reply':
            system_prompt = "You are a helpful email assistant. Generate a professional reply to the following email."
            user_prompt = f"Email content:\n{task.input_text}\n\nGenerate a professional reply:"
        
        elif task.task_type == 'summarize':
            system_prompt = "You are a helpful assistant. Summarize the following content concisely."
            user_prompt = f"Content to summarize:\n{task.input_text}"
        
        elif task.task_type == 'translate':
            target_language = task.context.get('target_language', 'English') if task.context else 'English'
            system_prompt = f"You are a professional translator. Translate the following text to {target_language}."
            user_prompt = task.input_text
        
        elif task.task_type == 'analyze':
            system_prompt = "You are an analytical assistant. Analyze the following content and provide insights."
            user_prompt = f"Content to analyze:\n{task.input_text}"
        
        else:
            raise ValueError(f'Unknown task type: {task.task_type}')
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        output = response.choices[0].message.content
        processing_time = time.time() - start_time
        
        # Update task
        task.output_text = output
        task.status = 'completed'
        task.processing_time = processing_time
        task.completed_at = timezone.now()
        task.save()
        
        logger.info(f'Assistant task {task_id} completed in {processing_time:.2f}s')
        return {
            'status': 'success',
            'task_id': task_id,
            'processing_time': processing_time
        }
        
    except AssistantTask.DoesNotExist:
        logger.error(f'Assistant task {task_id} not found')
        return {'status': 'error', 'message': 'Task not found'}
    
    except Exception as e:
        logger.error(f'Error processing assistant task {task_id}: {str(e)}')
        if 'task' in locals():
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
        return {'status': 'error', 'message': str(e)}
