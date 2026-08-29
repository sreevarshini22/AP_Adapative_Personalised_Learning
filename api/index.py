import os
import sys

# Ensure root directory is in python system path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app

# Handler for Vercel Serverless Function
def handler(request, response):
    return app(request, response)

# Expose app for WSGI / ASGI
if __name__ == "__main__":
    app.run()
