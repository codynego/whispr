from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import EmailAccount, Email
from .serializers import EmailAccountSerializer, EmailSerializer, EmailSyncSerializer
from .tasks import sync_email_account, analyze_email_importance_task


class EmailAccountListView(generics.ListAPIView):
    """List all email accounts for the authenticated user"""
    serializer_class = EmailAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)


class EmailAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an email account"""
    serializer_class = EmailAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)


class EmailListView(generics.ListAPIView):
    """List all emails for the authenticated user"""
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Email.objects.filter(account__user=self.request.user)
        
        # Filter by importance
        importance = self.request.query_params.get('importance')
        if importance:
            queryset = queryset.filter(importance=importance)
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        return queryset


class EmailDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update an email"""
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Email.objects.filter(account__user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sync_emails(request):
    """Trigger email sync for user's accounts"""
    serializer = EmailSyncSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    provider = serializer.validated_data['provider']
    authorization_code = serializer.validated_data['authorization_code']
    
    # Trigger async task to sync emails
    task = sync_email_account.delay(request.user.id, provider, authorization_code)
    
    return Response({
        'message': 'Email sync initiated',
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def analyze_importance(request, email_id):
    """Trigger importance analysis for a specific email"""
    try:
        email = Email.objects.get(id=email_id, account__user=request.user)
    except Email.DoesNotExist:
        return Response({'error': 'Email not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Trigger async task to analyze importance
    task = analyze_email_importance_task.delay(email_id)
    
    return Response({
        'message': 'Importance analysis initiated',
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)
