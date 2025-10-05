# Deployment Guide

This guide covers deploying WhisprAI to production.

## Prerequisites

- Ubuntu 20.04+ or similar Linux server
- Docker & Docker Compose installed
- Domain name pointing to your server
- SSL certificate (Let's Encrypt recommended)

## 1. Server Setup

### Update system
```bash
sudo apt update && sudo apt upgrade -y
```

### Install Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### Install Docker Compose
```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## 2. Application Setup

### Clone repository
```bash
git clone <your-repo-url>
cd whispr
```

### Configure environment
```bash
cp .env.example .env
nano .env
```

**Important: Update these in .env:**
```env
# Security
SECRET_KEY=<generate-a-long-random-string>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (use strong passwords)
DB_PASSWORD=<strong-password>

# Redis (recommended to add password in production)
REDIS_PASSWORD=<redis-password>

# API Keys (add your actual keys)
OPENAI_API_KEY=sk-...
WHATSAPP_ACCESS_TOKEN=...
PAYSTACK_SECRET_KEY=sk_live_...
GMAIL_CLIENT_ID=...
OUTLOOK_CLIENT_ID=...
```

### Generate SECRET_KEY
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 3. SSL/HTTPS Setup

### Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### Get SSL Certificate
```bash
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

### Update docker-compose.yml for HTTPS

Add nginx service:
```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    depends_on:
      - web
```

### Create nginx.conf
```nginx
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /app/staticfiles/;
    }

    location /media/ {
        alias /app/media/;
    }
}
```

## 4. Deploy Application

### Build and start services
```bash
docker-compose up -d --build
```

### Run migrations
```bash
docker-compose exec web python manage.py migrate
```

### Collect static files
```bash
docker-compose exec web python manage.py collectstatic --noinput
```

### Create superuser
```bash
docker-compose exec web python manage.py createsuperuser
```

## 5. Security Hardening

### Firewall Setup
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Secure Redis
Add password to Redis in docker-compose.yml:
```yaml
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass your-redis-password
```

Update CELERY_BROKER_URL in .env:
```env
CELERY_BROKER_URL=redis://:your-redis-password@redis:6379/0
```

### Database Backups

Create backup script:
```bash
#!/bin/bash
docker-compose exec -T db pg_dump -U postgres whisprai_db > backup-$(date +%Y%m%d-%H%M%S).sql
```

Add to crontab:
```bash
crontab -e
# Add: 0 2 * * * /path/to/backup.sh
```

## 6. Monitoring & Logging

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f celery
```

### Setup log rotation
Create `/etc/logrotate.d/docker-compose`:
```
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    missingok
    delaycompress
    copytruncate
}
```

### Install monitoring (optional)
Consider installing:
- Sentry for error tracking
- Prometheus + Grafana for metrics
- ELK Stack for log management

## 7. Webhook Configuration

### WhatsApp Webhook
Configure in Meta Developer Console:
- Callback URL: `https://yourdomain.com/api/whatsapp/webhook/`
- Verify Token: (from your .env WHATSAPP_VERIFY_TOKEN)

### Paystack Webhook
Configure in Paystack Dashboard:
- Webhook URL: `https://yourdomain.com/api/billing/webhook/`

## 8. Maintenance

### Update application
```bash
git pull origin main
docker-compose down
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
```

### Restart services
```bash
docker-compose restart
```

### Scale workers
```bash
docker-compose up -d --scale celery=3
```

### Check service status
```bash
docker-compose ps
```

### Database maintenance
```bash
# Backup
docker-compose exec db pg_dump -U postgres whisprai_db > backup.sql

# Restore
docker-compose exec -T db psql -U postgres whisprai_db < backup.sql
```

## 9. Performance Optimization

### Gunicorn workers
Update Dockerfile CMD:
```dockerfile
CMD ["gunicorn", "whisprai.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2"]
```

### Redis caching
Add to settings.py:
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
    }
}
```

### Database connection pooling
Install pgbouncer for connection pooling

## 10. Troubleshooting

### Check service logs
```bash
docker-compose logs [service-name]
```

### Access container shell
```bash
docker-compose exec web bash
docker-compose exec db psql -U postgres
```

### Reset database (development only!)
```bash
docker-compose down -v
docker-compose up -d
docker-compose exec web python manage.py migrate
```

### Check Celery status
```bash
docker-compose exec celery celery -A whisprai inspect active
docker-compose exec celery celery -A whisprai inspect stats
```

## Support

For issues and questions:
- Check logs: `docker-compose logs -f`
- GitHub Issues: <repository-url>/issues
- Email: support@yourdomain.com
