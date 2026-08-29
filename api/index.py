import os
import sys

# Ensure root directory is in python system path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app

# WSGI Middleware to ensure PATH_INFO compatibility in Vercel Serverless
class VercelPathNormalizer:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        # If Vercel stripped '/api' from the incoming route, prepend it
        api_prefixes = ["/login", "/auth", "/student", "/teacher", "/ml", "/health", "/logout"]
        if not path.startswith("/api"):
            for prefix in api_prefixes:
                if path.startswith(prefix):
                    environ["PATH_INFO"] = "/api" + path
                    break
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathNormalizer(app.wsgi_app)

# Expose app for Vercel Serverless
if __name__ == "__main__":
    app.run()
