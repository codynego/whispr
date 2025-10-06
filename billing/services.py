from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)


class PaystackService:
    """Service class for Paystack API integration"""
    
    BASE_URL = 'https://api.paystack.co'
    
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
    def initialize_payment(self, email, amount, metadata=None):
        """
        Initialize a payment transaction
        
        Args:
            email: Customer email
            amount: Amount in kobo (multiply by 100 for naira)
            metadata: Additional metadata
        
        Returns:
            dict: Response data from Paystack
        """
        url = f'{self.BASE_URL}/transaction/initialize'
        
        data = {
            'email': email,
            'amount': int(amount * 100),  # Convert to kobo
        }
        
        if metadata:
            data['metadata'] = metadata
        
        try:
            response = requests.post(url, json=data, headers=self.headers)
            return response.json()
        except Exception as e:
            logger.error(f'Error initializing payment: {str(e)}')
            return {'status': False, 'message': str(e)}
    
    def verify_payment(self, reference):
        """
        Verify a payment transaction
        
        Args:
            reference: Payment reference
        
        Returns:
            dict: Response data from Paystack
        """
        url = f'{self.BASE_URL}/transaction/verify/{reference}'
        
        try:
            response = requests.get(url, headers=self.headers)
            return response.json()
        except Exception as e:
            logger.error(f'Error verifying payment: {str(e)}')
            return {'status': False, 'message': str(e)}
    
    def create_subscription(self, customer_code, plan_code):
        """
        Create a subscription
        
        Args:
            customer_code: Paystack customer code
            plan_code: Paystack plan code
        
        Returns:
            dict: Response data from Paystack
        """
        url = f'{self.BASE_URL}/subscription'
        
        data = {
            'customer': customer_code,
            'plan': plan_code
        }
        
        try:
            response = requests.post(url, json=data, headers=self.headers)
            return response.json()
        except Exception as e:
            logger.error(f'Error creating subscription: {str(e)}')
            return {'status': False, 'message': str(e)}
    
    def cancel_subscription(self, subscription_code):
        """
        Cancel a subscription
        
        Args:
            subscription_code: Paystack subscription code
        
        Returns:
            dict: Response data from Paystack
        """
        url = f'{self.BASE_URL}/subscription/disable'
        
        data = {
            'code': subscription_code,
            'token': self.secret_key
        }
        
        try:
            response = requests.post(url, json=data, headers=self.headers)
            return response.json()
        except Exception as e:
            logger.error(f'Error cancelling subscription: {str(e)}')
            return {'status': False, 'message': str(e)}
