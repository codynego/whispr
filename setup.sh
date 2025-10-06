#!/bin/bash

# Setup script for WhisprAI

echo "=== WhisprAI Setup Script ==="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit .env file and add your API keys and secrets"
else
    echo ".env file already exists"
fi

# Build and start Docker containers
echo "Building Docker containers..."
docker-compose build

echo "Starting Docker containers..."
docker-compose up -d

# Wait for database to be ready
echo "Waiting for database to be ready..."
sleep 10

# Run migrations
echo "Running database migrations..."
docker-compose exec -T web python manage.py migrate

# Create superuser (optional)
echo ""
echo "Would you like to create a superuser? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    docker-compose exec web python manage.py createsuperuser
fi

# Collect static files
echo "Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Access your application at:"
echo "  - API: http://localhost:8000/"
echo "  - Admin: http://localhost:8000/admin/"
echo "  - Swagger Docs: http://localhost:8000/swagger/"
echo "  - ReDoc: http://localhost:8000/redoc/"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
echo ""
