from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .models import Subscription, Payment
from .serializers import SubscriptionSerializer, PaymentSerializer, InitializePaymentSerializer
from .services import PaystackService
import json


class SubscriptionDetailView(generics.RetrieveAPIView):
    """Get user subscription details"""
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        subscription, created = Subscription.objects.get_or_create(user=self.request.user)
        return subscription


class PaymentListView(generics.ListAPIView):
    """List all payments for the authenticated user"""
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def initialize_payment(request):
    """Initialize a payment with Paystack"""
    serializer = InitializePaymentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    plan = serializer.validated_data['plan']
    email = serializer.validated_data.get('email', request.user.email)
    
    # Get plan pricing
    plan_prices = {
        'basic': 5000,  # NGN
        'premium': 15000,
        'enterprise': 50000
    }
    
    amount = plan_prices.get(plan, 0)
    
    # Initialize payment
    paystack_service = PaystackService()
    result = paystack_service.initialize_payment(
        email=email,
        amount=amount,
        metadata={
            'user_id': request.user.id,
            'plan': plan
        }
    )
    
    if result['status']:
        # Create payment record
        payment = Payment.objects.create(
            user=request.user,
            reference=result['data']['reference'],
            authorization_url=result['data']['authorization_url'],
            access_code=result['data']['access_code'],
            amount=amount / 100,  # Convert from kobo to naira
            plan=plan,
            description=f'{plan.capitalize()} plan subscription'
        )
        
        return Response({
            'payment': PaymentSerializer(payment).data,
            'authorization_url': result['data']['authorization_url']
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'error': result.get('message', 'Payment initialization failed')
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def verify_payment(request, reference):
    """Verify a payment"""
    try:
        payment = Payment.objects.get(reference=reference, user=request.user)
    except Payment.DoesNotExist:
        return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
    
    paystack_service = PaystackService()
    result = paystack_service.verify_payment(reference)
    
    if result['status'] and result['data']['status'] == 'success':
        # Update payment status
        from .tasks import process_successful_payment
        process_successful_payment.delay(payment.id)
        
        return Response({
            'message': 'Payment verified successfully',
            'payment': PaymentSerializer(payment).data
        })
    else:
        return Response({
            'error': 'Payment verification failed'
        }, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
def webhook(request):
    """Paystack webhook endpoint"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            event = data.get('event')
            
            # TODO: Verify webhook signature
            
            if event == 'charge.success':
                reference = data['data']['reference']
                try:
                    payment = Payment.objects.get(reference=reference)
                    from .tasks import process_successful_payment
                    process_successful_payment.delay(payment.id)
                except Payment.DoesNotExist:
                    pass
            
            return HttpResponse('OK', status=200)
        except Exception as e:
            return HttpResponse(f'Error: {str(e)}', status=400)
    
    return HttpResponse('Method not allowed', status=405)
