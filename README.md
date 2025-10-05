# WhisprAI

An AI-powered Django REST API platform for intelligent email and WhatsApp management with billing integration.

## Features

- **User Management**: Custom user model with JWT authentication
- **Email Integration**: Gmail and Outlook sync with AI-powered importance analysis
- **WhatsApp Alerts**: Cloud API integration for sending alerts
- **AI Assistant**: Automated email replies, summarization, translation, and analysis
- **Billing**: Paystack integration for subscription management
- **Notifications**: Real-time notification system
- **Async Tasks**: Celery-based background job processing
- **API Documentation**: Swagger/OpenAPI documentation

## Tech Stack

- **Framework**: Django 4.2 + Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis + Celery
- **Authentication**: JWT (djangorestframework-simplejwt)
- **AI**: OpenAI API
- **Payment**: Paystack API
- **Messaging**: WhatsApp Cloud API
- **Documentation**: drf-yasg (Swagger)
- **Containerization**: Docker + Docker Compose

## Project Structure

```
whisprai/
├── whisprai/           # Project settings
│   ├── settings.py     # Django settings
│   ├── celery.py       # Celery configuration
│   └── urls.py         # Main URL routing
├── users/              # User management app
│   ├── models.py       # Custom User model
│   ├── serializers.py  # User serializers
│   └── views.py        # Authentication endpoints
├── emails/             # Email management app
│   ├── models.py       # Email & EmailAccount models
│   ├── tasks.py        # Email sync & AI analysis tasks
│   └── views.py        # Email API endpoints
├── whatsapp/           # WhatsApp integration app
│   ├── models.py       # WhatsApp message models
│   ├── tasks.py        # WhatsApp sending tasks
│   └── views.py        # WhatsApp API & webhook
├── assistant/          # AI assistant app
│   ├── models.py       # Assistant task models
│   ├── tasks.py        # AI processing tasks
│   └── views.py        # Assistant API endpoints
├── billing/            # Payment & subscription app
│   ├── models.py       # Subscription & Payment models
│   ├── services.py     # Paystack integration
│   ├── tasks.py        # Payment processing tasks
│   └── views.py        # Billing API & webhook
├── notifications/      # Notification system app
│   ├── models.py       # Notification model
│   └── views.py        # Notification API endpoints
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose services
├── .env.example        # Environment variables template
└── README.md           # This file
```

## Setup Instructions

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ (for local development)
- Redis (for local development)

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd whispr
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys and secrets
   ```

3. **Build and start services**
   ```bash
   docker-compose up --build
   ```

4. **Run migrations**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

6. **Access the application**
   - API: http://localhost:8000/
   - Admin: http://localhost:8000/admin/
   - Swagger Docs: http://localhost:8000/swagger/
   - ReDoc: http://localhost:8000/redoc/

### Local Development Setup

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

4. **Setup PostgreSQL database**
   ```bash
   createdb whisprai_db
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

8. **Run Celery worker (in another terminal)**
   ```bash
   celery -A whisprai worker -l info
   ```

9. **Run Celery beat (in another terminal)**
   ```bash
   celery -A whisprai beat -l info
   ```

## API Endpoints

### Authentication
- `POST /api/users/register/` - User registration
- `POST /api/users/login/` - Login (get JWT tokens)
- `POST /api/users/token/refresh/` - Refresh JWT token
- `GET /api/users/profile/` - Get/Update user profile

### Emails
- `GET /api/emails/accounts/` - List email accounts
- `POST /api/emails/sync/` - Sync emails from provider
- `GET /api/emails/messages/` - List emails
- `GET /api/emails/messages/<id>/` - Get email details
- `POST /api/emails/messages/<id>/analyze/` - Analyze email importance

### WhatsApp
- `GET /api/whatsapp/messages/` - List sent messages
- `POST /api/whatsapp/send/` - Send WhatsApp message
- `POST /api/whatsapp/webhook/` - WhatsApp webhook (Cloud API)

### Assistant
- `GET /api/assistant/tasks/` - List assistant tasks
- `POST /api/assistant/tasks/create/` - Create AI task (reply, summarize, etc.)
- `GET /api/assistant/tasks/<id>/` - Get task result

### Billing
- `GET /api/billing/subscription/` - Get subscription details
- `GET /api/billing/payments/` - List payments
- `POST /api/billing/payments/initialize/` - Initialize payment
- `GET /api/billing/payments/verify/<reference>/` - Verify payment
- `POST /api/billing/webhook/` - Paystack webhook

### Notifications
- `GET /api/notifications/` - List notifications
- `GET /api/notifications/<id>/` - Get notification
- `POST /api/notifications/<id>/read/` - Mark as read
- `POST /api/notifications/mark-all-read/` - Mark all as read
- `GET /api/notifications/unread-count/` - Get unread count

## Environment Variables

Key environment variables to configure:

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,yourdomain.com

# Database
DB_NAME=whisprai_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=db
DB_PORT=5432

# Redis/Celery
REDIS_HOST=redis
REDIS_PORT=6379
CELERY_BROKER_URL=redis://redis:6379/0

# JWT
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440

# Email APIs
GMAIL_CLIENT_ID=your-client-id
GMAIL_CLIENT_SECRET=your-client-secret
OUTLOOK_CLIENT_ID=your-client-id
OUTLOOK_CLIENT_SECRET=your-client-secret

# WhatsApp Cloud API
WHATSAPP_API_URL=https://graph.facebook.com/v18.0
WHATSAPP_ACCESS_TOKEN=your-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-id
WHATSAPP_VERIFY_TOKEN=your-verify-token

# OpenAI
OPENAI_API_KEY=your-api-key

# Paystack
PAYSTACK_SECRET_KEY=your-secret-key
PAYSTACK_PUBLIC_KEY=your-public-key
```

## Subscription Plans

- **Free**: Basic features
- **Basic**: NGN 5,000/month - Enhanced email management
- **Premium**: NGN 15,000/month - AI features + WhatsApp alerts
- **Enterprise**: NGN 50,000/month - All features + priority support

## Celery Tasks

The application uses Celery for background processing:

### Periodic Tasks (Celery Beat)
- Email sync: Every 15 minutes
- Email importance analysis: Every 30 minutes
- Check expired subscriptions: Daily

### Async Tasks
- Email synchronization
- AI email importance analysis
- WhatsApp message sending
- AI assistant tasks (reply, summarize, translate, analyze)
- Payment processing

## Testing

```bash
# Run tests
python manage.py test

# With coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

## Deployment

### Production Checklist

1. Set `DEBUG=False` in .env
2. Configure proper `SECRET_KEY`
3. Set up proper `ALLOWED_HOSTS`
4. Configure HTTPS/SSL
5. Set up proper PostgreSQL credentials
6. Configure Redis with password
7. Add all API keys and secrets
8. Set up proper logging
9. Configure backup strategy
10. Set up monitoring (Sentry, etc.)

### Deploy with Docker

```bash
docker-compose -f docker-compose.yml up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
docker-compose exec web python manage.py createsuperuser
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License.

## Support

For support, email contact@whisprai.com or create an issue in the repository.
