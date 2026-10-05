"""
Authentication and Role-Based Access Control (RBAC) Module
AP Adaptive Education Platform

Supports:
- Super Admin / State Admin ('state_admin')
- Institution Admin ('institution_admin')
- Teacher / Faculty ('teacher')
- Student ('student')
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
    cursor.execute("""
    SELECT u.id, u.email, u.role, u.full_name, u.institution_id, u.created_at,
           i.name as institution_name, i.code as institution_code, i.district, i.state
    FROM users u
    LEFT JOIN institutions i ON u.institution_id = i.id
    WHERE u.id = ?
    """, (user_id,))
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
        if session.get("role") not in ["teacher", "institution_admin", "state_admin"]:
            return jsonify({"success": False, "error": "Access forbidden: Faculty privileges required."}), 403
        return f(*args, **kwargs)
    return decorated_function


def institution_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
        if session.get("role") not in ["institution_admin", "state_admin"]:
            return jsonify({"success": False, "error": "Access forbidden: Institution Administrator privileges required."}), 403
        return f(*args, **kwargs)
    return decorated_function


def state_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
        if session.get("role") != "state_admin":
            return jsonify({"success": False, "error": "Access forbidden: State / Super Administrator privileges required."}), 403
        return f(*args, **kwargs)
    return decorated_function
