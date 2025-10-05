# Quick Start Guide

Get WhisprAI up and running in 5 minutes!

## Prerequisites
- Docker & Docker Compose installed
- Git

## Steps

### 1. Clone & Setup
```bash
git clone <repository-url>
cd whispr
cp .env.example .env
```

### 2. Configure API Keys
Edit `.env` and add your API keys:
```env
OPENAI_API_KEY=sk-...
WHATSAPP_ACCESS_TOKEN=...
PAYSTACK_SECRET_KEY=...
```

### 3. Start Services
```bash
docker-compose up -d --build
```

### 4. Initialize Database
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

### 5. Access Application
- **API**: http://localhost:8000/
- **Admin**: http://localhost:8000/admin/
- **Swagger Docs**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/

## Quick Test

### 1. Register a User
```bash
curl -X POST http://localhost:8000/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!",
    "password_confirm": "Test123!"
  }'
```

### 2. Login
```bash
curl -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!"
  }'
```

Save the `access` token from the response.

### 3. Get Profile
```bash
curl -X GET http://localhost:8000/api/users/profile/ \
  -H "Authorization: Bearer <your-access-token>"
```

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart services
docker-compose restart

# Run Django commands
docker-compose exec web python manage.py <command>
```

## Need Help?

- See [README.md](README.md) for full documentation
- See [API_TESTING.md](API_TESTING.md) for API examples
- See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment

## Project Structure Overview

```
whisprai/
├── users/              # User authentication & management
├── emails/             # Email sync & AI importance
├── whatsapp/           # WhatsApp Cloud API
├── assistant/          # AI tasks (reply, summarize, etc.)
├── billing/            # Paystack subscriptions
├── notifications/      # User notifications
├── whisprai/          # Django settings & config
├── docker-compose.yml  # Docker configuration
└── requirements.txt    # Python dependencies
```

## Key Features

✅ JWT Authentication  
✅ Custom User Model (email, whatsapp, plan)  
✅ Email Sync (Gmail/Outlook) with AI Importance  
✅ WhatsApp Alerts via Cloud API  
✅ AI Assistant (OpenAI powered)  
✅ Paystack Payment Integration  
✅ Celery Background Tasks  
✅ Swagger API Documentation  
✅ Docker Ready  

## Next Steps

1. Configure your OAuth apps (Gmail/Outlook)
2. Set up WhatsApp Business API
3. Configure Paystack for payments
4. Customize AI prompts in `*/tasks.py`
5. Add your domain and SSL for production

Happy coding! 🚀
