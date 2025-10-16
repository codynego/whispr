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
from django.db.models import Q




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
            combined = email_normalized  # , whatsapp_normalized)
        if channel == 'email':
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
