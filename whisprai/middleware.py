# middleware.py
class ForceCORSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # FORCE these headers on EVERY response — nothing can block them
        response["Access-Control-Allow-Origin"] = "https://www.whisone.app"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-CSRFToken"

        # Handle preflight OPTIONS instantly
        if request.method == "OPTIONS":
            response.status_code = 200

        return response