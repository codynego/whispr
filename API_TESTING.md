# API Testing Guide

This guide provides examples for testing the WhisprAI API endpoints.

## Base URL
```
http://localhost:8000
```

## Authentication

All authenticated endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## 1. User Registration & Authentication

### Register a new user
```bash
curl -X POST http://localhost:8000/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "first_name": "John",
    "last_name": "Doe",
    "whatsapp": "+2348012345678"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123"
  }'
```

Response:
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJh...",
  "access": "eyJ0eXAiOiJKV1QiLCJhb..."
}
```

### Refresh Token
```bash
curl -X POST http://localhost:8000/api/users/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "eyJ0eXAiOiJKV1QiLCJh..."
  }'
```

### Get User Profile
```bash
curl -X GET http://localhost:8000/api/users/profile/ \
  -H "Authorization: Bearer <access_token>"
```

## 2. Email Management

### List Email Accounts
```bash
curl -X GET http://localhost:8000/api/emails/accounts/ \
  -H "Authorization: Bearer <access_token>"
```

### Sync Emails
```bash
curl -X POST http://localhost:8000/api/emails/sync/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gmail",
    "authorization_code": "4/0AWtgzh5..."
  }'
```

### List Emails
```bash
# All emails
curl -X GET http://localhost:8000/api/emails/messages/ \
  -H "Authorization: Bearer <access_token>"

# Filter by importance
curl -X GET "http://localhost:8000/api/emails/messages/?importance=high" \
  -H "Authorization: Bearer <access_token>"

# Filter by read status
curl -X GET "http://localhost:8000/api/emails/messages/?is_read=false" \
  -H "Authorization: Bearer <access_token>"
```

### Analyze Email Importance
```bash
curl -X POST http://localhost:8000/api/emails/messages/1/analyze/ \
  -H "Authorization: Bearer <access_token>"
```

## 3. WhatsApp Integration

### Send WhatsApp Message
```bash
curl -X POST http://localhost:8000/api/whatsapp/send/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "to_number": "+2348012345678",
    "message": "Hello from WhisprAI!",
    "alert_type": "test"
  }'
```

### List WhatsApp Messages
```bash
curl -X GET http://localhost:8000/api/whatsapp/messages/ \
  -H "Authorization: Bearer <access_token>"
```

## 4. AI Assistant

### Create AI Task - Generate Reply
```bash
curl -X POST http://localhost:8000/api/assistant/tasks/create/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "reply",
    "input_text": "Dear Sir, I need help with my account setup. Please assist.",
    "context": {"tone": "professional"}
  }'
```

### Create AI Task - Summarize
```bash
curl -X POST http://localhost:8000/api/assistant/tasks/create/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "summarize",
    "input_text": "Long email content here..."
  }'
```

### Create AI Task - Translate
```bash
curl -X POST http://localhost:8000/api/assistant/tasks/create/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "translate",
    "input_text": "Hello, how are you?",
    "context": {"target_language": "French"}
  }'
```

### List AI Tasks
```bash
# All tasks
curl -X GET http://localhost:8000/api/assistant/tasks/ \
  -H "Authorization: Bearer <access_token>"

# Filter by type
curl -X GET "http://localhost:8000/api/assistant/tasks/?task_type=reply" \
  -H "Authorization: Bearer <access_token>"

# Filter by status
curl -X GET "http://localhost:8000/api/assistant/tasks/?status=completed" \
  -H "Authorization: Bearer <access_token>"
```

### Get Task Result
```bash
curl -X GET http://localhost:8000/api/assistant/tasks/1/ \
  -H "Authorization: Bearer <access_token>"
```

## 5. Billing & Subscriptions

### Get Subscription Details
```bash
curl -X GET http://localhost:8000/api/billing/subscription/ \
  -H "Authorization: Bearer <access_token>"
```

### Initialize Payment
```bash
curl -X POST http://localhost:8000/api/billing/payments/initialize/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "premium",
    "email": "user@example.com"
  }'
```

Response:
```json
{
  "payment": {
    "id": 1,
    "reference": "T123456789",
    "amount": "150.00",
    "status": "pending"
  },
  "authorization_url": "https://checkout.paystack.com/..."
}
```

### Verify Payment
```bash
curl -X GET http://localhost:8000/api/billing/payments/verify/T123456789/ \
  -H "Authorization: Bearer <access_token>"
```

### List Payments
```bash
curl -X GET http://localhost:8000/api/billing/payments/ \
  -H "Authorization: Bearer <access_token>"
```

## 6. Notifications

### List Notifications
```bash
# All notifications
curl -X GET http://localhost:8000/api/notifications/ \
  -H "Authorization: Bearer <access_token>"

# Unread only
curl -X GET "http://localhost:8000/api/notifications/?is_read=false" \
  -H "Authorization: Bearer <access_token>"

# By type
curl -X GET "http://localhost:8000/api/notifications/?type=email" \
  -H "Authorization: Bearer <access_token>"
```

### Get Unread Count
```bash
curl -X GET http://localhost:8000/api/notifications/unread-count/ \
  -H "Authorization: Bearer <access_token>"
```

### Mark as Read
```bash
curl -X POST http://localhost:8000/api/notifications/1/read/ \
  -H "Authorization: Bearer <access_token>"
```

### Mark All as Read
```bash
curl -X POST http://localhost:8000/api/notifications/mark-all-read/ \
  -H "Authorization: Bearer <access_token>"
```

## Using Swagger UI

Access the interactive API documentation at:
```
http://localhost:8000/swagger/
```

1. Click "Authorize" button
2. Enter: `Bearer <your_access_token>`
3. Test endpoints interactively

## Using ReDoc

Access the alternative API documentation at:
```
http://localhost:8000/redoc/
```

## Error Responses

All error responses follow this format:
```json
{
  "detail": "Error message here"
}
```

or for validation errors:
```json
{
  "field_name": ["Error message 1", "Error message 2"]
}
```

## Pagination

List endpoints support pagination:
```bash
curl -X GET "http://localhost:8000/api/emails/messages/?page=2" \
  -H "Authorization: Bearer <access_token>"
```

Response format:
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/emails/messages/?page=3",
  "previous": "http://localhost:8000/api/emails/messages/?page=1",
  "results": [...]
}
```
