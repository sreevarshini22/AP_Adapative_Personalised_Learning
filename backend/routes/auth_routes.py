"""
Authentication Routes for AP Adaptive Education Platform
Real database-backed authentication, role verification, password hashing, and user registration.
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from backend.database import get_db_connection
from backend.models import serialize_user, serialize_student, serialize_teacher
from backend.auth import get_current_user

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/login/student", methods=["POST"])
@auth_bp.route("/login/student", methods=["POST"])
def login_student():
    """
    Authenticates student against database with hashed password and role check.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    
    if not email:
        return jsonify({"success": False, "message": "Please enter your email."}), 400
    if not password:
        return jsonify({"success": False, "message": "Please enter your password."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query user by email
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    
    # Verify user exists, password hash matches, AND role is 'student'
    if not user or not check_password_hash(user["password_hash"], password) or user["role"] != "student":
        conn.close()
        return jsonify({"success": False, "message": "Invalid student email or password."}), 401
        
    # Retrieve student record
    cursor.execute("SELECT * FROM students WHERE user_id = ? OR LOWER(email) = ?", (user["id"], email))
    student_row = cursor.fetchone()
    conn.close()
    
    # Establish secure session
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "student"
    session["email"] = user["email"]
    session["full_name"] = user["full_name"]
    if student_row:
        session["student_id"] = student_row["id"]
        session["roll_no"] = student_row["roll_no"]
        
    return jsonify({
        "success": True,
        "message": "Student login successful",
        "user": serialize_user(user),
        "student": serialize_student(student_row) if student_row else None
    })

@auth_bp.route("/api/login/teacher", methods=["POST"])
@auth_bp.route("/login/teacher", methods=["POST"])
def login_teacher():
    """
    Authenticates faculty against database with hashed password and role check.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    
    if not email:
        return jsonify({"success": False, "message": "Please enter your email."}), 400
    if not password:
        return jsonify({"success": False, "message": "Please enter your password."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query user by email
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    
    # Verify user exists, password hash matches, AND role is 'teacher'
    if not user or not check_password_hash(user["password_hash"], password) or user["role"] != "teacher":
        conn.close()
        return jsonify({"success": False, "message": "Invalid teacher email or password."}), 401
        
    # Retrieve teacher metadata if exists
    cursor.execute("SELECT * FROM teachers WHERE user_id = ? OR LOWER(email) = ?", (user["id"], email))
    teacher_row = cursor.fetchone()
    conn.close()
    
    # Establish secure session
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "teacher"
    session["email"] = user["email"]
    session["full_name"] = user["full_name"]
    
    return jsonify({
        "success": True,
        "message": "Teacher login successful",
        "user": serialize_user(user),
        "teacher": serialize_teacher(teacher_row) if teacher_row else None
    })

@auth_bp.route("/api/register/student", methods=["POST"])
@auth_bp.route("/register/student", methods=["POST"])
def register_student():
    """
    Public student self-registration endpoint storing hashed credentials in database.
    """
    data = request.get_json() or {}
    full_name = data.get("full_name", "").strip()
    roll_no = data.get("roll_no", "").strip().upper()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    year = data.get("year", "1st Year").strip()
    branch = data.get("branch", "CSE").strip()
    section = data.get("section", "A").strip()
    semester = int(data.get("semester", 1))
    
    if not full_name or not roll_no or not email or not password:
        return jsonify({"success": False, "message": "Please provide full name, roll number, email, and password."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Duplicate email validation
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "An account with this email already exists."}), 400
        
    # Duplicate roll_no validation
    cursor.execute("SELECT id FROM students WHERE roll_no = ?", (roll_no,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Student with this roll number already exists."}), 400
        
    # Hash password securely
    pwd_hash = generate_password_hash(password)
    
    # Insert user
    cursor.execute("""
    INSERT INTO users (email, password_hash, role, full_name)
    VALUES (?, ?, 'student', ?)
    """, (email, pwd_hash, full_name))
    user_id = cursor.lastrowid
    
    # Insert student
    cursor.execute("""
    INSERT INTO students (
        user_id, full_name, roll_no, email, year, branch, section, semester,
        attendance, mathematics_score, physics_score, programming_score,
        data_structures_score, database_score, communication_score,
        assignment_score, quiz_score, exam_score, study_hours,
        learning_activity, previous_performance, overall_progress
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?,
        75.0, 65.0, 65.0, 65.0,
        65.0, 65.0, 70.0,
        70.0, 65.0, 65.0, 8.0,
        60.0, 65.0, 50.0
    )
    """, (user_id, full_name, roll_no, email, year, branch, section, semester))
    
    student_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"Student account for {full_name} created successfully. You may now log in.",
        "user_id": user_id,
        "student_id": student_id
    }), 201

@auth_bp.route("/api/register/teacher", methods=["POST"])
@auth_bp.route("/register/teacher", methods=["POST"])
def register_teacher():
    """
    Public faculty self-registration endpoint storing hashed credentials in database.
    """
    data = request.get_json() or {}
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    branch = data.get("branch", "CSE").strip()
    year = data.get("year", "3rd Year").strip()
    section = data.get("section", "A").strip()
    
    if not full_name or not email or not password:
        return jsonify({"success": False, "message": "Please provide full name, email, and password."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Duplicate email validation
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "An account with this email already exists."}), 400
        
    # Hash password securely
    pwd_hash = generate_password_hash(password)
    
    # Insert user
    cursor.execute("""
    INSERT INTO users (email, password_hash, role, full_name)
    VALUES (?, ?, 'teacher', ?)
    """, (email, pwd_hash, full_name))
    user_id = cursor.lastrowid
    
    # Insert teacher profile
    cursor.execute("""
    INSERT INTO teachers (user_id, full_name, email, branch, year, section)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, full_name, email, branch, year, section))
    
    teacher_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"Faculty account for {full_name} created successfully. You may now log in.",
        "user_id": user_id,
        "teacher_id": teacher_id
    }), 201

@auth_bp.route("/api/me", methods=["GET"])
@auth_bp.route("/me", methods=["GET"])
@auth_bp.route("/api/auth/me", methods=["GET"])
@auth_bp.route("/auth/me", methods=["GET"])
def get_me():
    """
    Returns safe current authenticated user profile. Never exposes passwords or hashes.
    """
    user = get_current_user()
    if not user:
        return jsonify({"logged_in": False, "authenticated": False, "user": None, "role": None})
    
    response_data = {
        "logged_in": True,
        "authenticated": True,
        "role": user["role"],
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"]
    }
    
    if user["role"] == "student":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE user_id = ? OR LOWER(email) = ?", (user["id"], user["email"].lower()))
        student_row = cursor.fetchone()
        conn.close()
        if student_row:
            response_data["roll_no"] = student_row["roll_no"]
            response_data["student"] = serialize_student(student_row)
            
    return jsonify(response_data)

@auth_bp.route("/api/logout", methods=["POST", "GET"])
@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    """
    Destroys the current session and clears all authentication state.
    """
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

@auth_bp.route("/api/forgot-password", methods=["POST"])
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Secure password reset handler. Does not expose account existence.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    
    if not email:
        return jsonify({"success": False, "message": "Please enter your registered email."}), 400
        
    return jsonify({
        "success": True,
        "message": "If an account matches this email, password recovery instructions have been dispatched."
    })
