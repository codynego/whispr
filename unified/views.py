# views.py
from rest_framework import generics, permissions
from rest_framework.response import Response
from emails.models import EmailAccount, Email
# from whatsapp.models import WhatsAppAccount


from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from itertools import chain
from django.core.paginator import Paginator

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from assistant.models import AssistantTask




@method_decorator(csrf_exempt, name='dispatch')
class UnifiedMessagesView(View):
    def get(self, request):
        # --- GET QUERY PARAMS ---
        channel = request.GET.get('channel', 'all')
        account = request.GET.get('account')
        importance = request.GET.get('importance')
        is_read = request.GET.get('is_read')
        search = request.GET.get('search', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))

        # --- EMAILS QUERY ---
        emails = Email.objects.all()
        if account:
            emails = emails.filter(account_id=account)
        if importance:
            emails = emails.filter(importance=importance)
        if is_read is not None and is_read.lower() in ['true', 'false']:
            emails = emails.filter(is_read=is_read.lower() == 'true')
        if search:
            emails = emails.filter(
                Q(subject__icontains=search) |
                Q(body__icontains=search) |
                Q(sender__icontains=search)
            )

        emails = emails.values(
            'id', 'sender', 'subject', 'body', 'received_at', 'importance', 'is_read'
        )

        # # --- WHATSAPP QUERY ---
        # whatsapp_msgs = WhatsAppMessage.objects.all()
        # if account:
        #     whatsapp_msgs = whatsapp_msgs.filter(account_id=account)
        # if importance:
        #     whatsapp_msgs = whatsapp_msgs.filter(importance=importance)
        # if is_read is not None and is_read.lower() in ['true', 'false']:
        #     whatsapp_msgs = whatsapp_msgs.filter(is_read=is_read.lower() == 'true')
        # if search:
        #     whatsapp_msgs = whatsapp_msgs.filter(
        #         Q(message__icontains=search) | Q(sender__icontains=search)
        #     )

        # whatsapp_msgs = whatsapp_msgs.values(
        #     'id', 'sender', 'message', 'received_at', 'importance', 'is_read'
        # )

        # --- NORMALIZE STRUCTURE ---
        email_normalized = [
            {
                'id': e['id'],
                'sender': e['sender'],
                'subject': e['subject'],
                'body': e['body'],
                'received_at': e['received_at'],
                'importance': e['importance'],
                'is_read': e['is_read'],
                'channel': 'email'
            } for e in emails
        ]

        # whatsapp_normalized = [
        #     {
        #         'id': w['id'],
        #         'sender': w['sender'],
        #         'subject': '(WhatsApp)',
        #         'body': w['message'],
        #         'received_at': w['received_at'],
        #         'importance': w['importance'],
        #         'is_read': w['is_read'],
        #         'channel': 'whatsapp'
        #     } for w in whatsapp_msgs
        # ]

        # --- APPLY CHANNEL FILTER ---

        if channel == 'all':
            combined = email_normalized
        elif channel == 'email':
            combined = email_normalized
        else:
            combined = list()
        # --- SORT & PAGINATE ---
        combined_sorted = sorted(combined, key=lambda x: x['received_at'], reverse=True)

        paginator = Paginator(combined_sorted, page_size)
        page_obj = paginator.get_page(page)

        response = {
            'results': list(page_obj),
            'page': page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count
        }

        return JsonResponse(response)


class AllAccountsView(generics.ListAPIView):
    """
    Unified view that returns all connected communication accounts
    (Email + WhatsApp) for the current user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        email_accounts = EmailAccount.objects.filter(user=request.user)
        # whatsapp_accounts = WhatsAppAccount.objects.filter(user=request.user)

        data = []

        # Collect email accounts
        for acc in email_accounts:
            data.append({
                "id": f"email-{acc.id}",
                "name": acc.provider or acc.email_address,
                "channel": "email",
                "address": acc.email_address,
                "connected": getattr(acc, "connected", True),
            })

        # # Collect WhatsApp accounts
        # for acc in whatsapp_accounts:
        #     data.append({
        #         "id": f"whatsapp-{acc.id}",
        #         "name": acc.name or acc.phone_number,
        #         "channel": "whatsapp",
        #         "address": acc.phone_number,
        #         "connected": getattr(acc, "connected", True),
        #     })

        return Response(data)






class DashboardOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        # --- EMAIL STATS ---
        email_today = Email.objects.filter(account__user=user, created_at__date=today)
        total_emails = email_today.count()
        unread_emails = email_today.filter(is_read=False).count()
        important_emails = email_today.filter(importance_score__gte=0.5).count()

        # # --- WHATSAPP STATS ---
        # whatsapp_today = WhatsAppMessage.objects.filter(user=user, created_at__date=today)
        # total_whatsapp = whatsapp_today.count()
        # unread_whatsapp = whatsapp_today.filter(is_read=False).count()

        total_whatsapp = 0
        unread_whatsapp = 0

        # --- COMBINED STATS ---
        total_messages = total_emails + total_whatsapp
        unread_messages = unread_emails + unread_whatsapp


        # --- AI SUMMARY ---
        ai_summary = {
            "greeting": f"Good {self.get_time_of_day()}, {user.first_name or 'there'} 👋",
            "summary_text": (
                f"You’ve received {total_messages} messages today "
                f"({total_emails} emails, {total_whatsapp} WhatsApp). "
                f"{unread_messages} are still unread, and {important_emails} are important."
            ),
            "suggestions": [
                "Reply to important messages",
                "Review unread messages",
                "Generate AI summary of today's inbox"
            ]
        }

        # --- AI TASKS (Real from DB) ---
        tasks_qs = AssistantTask.objects.filter(user=user).order_by('-created_at')[:5]
        ai_tasks = [
            {
                "id": t.id,
                "task_type": t.task_type,
                "status": t.status,
                "input_text": t.input_text[:120] + ("..." if len(t.input_text) > 120 else ""),
                "due_datetime": t.due_datetime,
                "is_completed": t.is_completed,
                "created_at": t.created_at,
            }
            for t in tasks_qs
        ]

        # --- PERFORMANCE (Sample / Mock for now) ---
        performance = {
            "response_time_avg": "12m",
            "ai_replies_sent": AssistantTask.objects.filter(user=user, task_type='reply', status='completed').count(),
            "important_threads": important_emails,
            "missed_messages": unread_messages,
            "trend": "+9%",
        }

        data = {
            "summary": ai_summary,
            "stats": {
                "total_messages": total_messages,
                "unread_messages": unread_messages,
                "important_emails": important_emails,
                "channel_breakdown": {
                    "email": total_emails,
                    "whatsapp": total_whatsapp,
                }
            },
            "tasks": ai_tasks,
            "performance": performance,
        }

        return Response(data)

    def get_time_of_day(self):
        hour = timezone.now().hour
        if hour < 12:
            return "morning"
        elif hour < 18:
            return "afternoon"
        return "evening"
