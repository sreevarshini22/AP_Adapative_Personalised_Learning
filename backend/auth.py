"""
Authentication and Role-Based Access Control (RBAC) Module
"""

from functools import wraps
from flask import session, jsonify, request
from backend.database import get_db_connection
from backend.models import serialize_user

def get_current_user():
    """Retrieves current logged in user from session and DB."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, role, full_name, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return serialize_user(row)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
        if session.get("role") != "student":
            return jsonify({"success": False, "error": "Access forbidden: Student privileges required."}), 403
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
        if session.get("role") != "teacher":
            return jsonify({"success": False, "error": "Access forbidden: Teacher privileges required."}), 403
        return f(*args, **kwargs)
    return decorated_function
