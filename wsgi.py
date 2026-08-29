"""
Production WSGI Entry Point for Gunicorn / uWSGI
Usage:
    gunicorn wsgi:app --workers 2 --threads 4 --timeout 120
"""

import os
import sys

# Ensure project root is in system path for cloud hosting
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
