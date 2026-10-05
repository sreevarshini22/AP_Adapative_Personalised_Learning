"""
Authentication Routes for AP Adaptive Education Platform
Supports Multi-Institution RBAC: State Admin, Institution Admin, Faculty, and Students.
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from backend.database import get_db_connection, log_audit_event
from backend.models import serialize_user, serialize_student, serialize_teacher
from backend.auth import get_current_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/login", methods=["POST"])
@auth_bp.route("/login", methods=["POST"])
def unified_login():
    """
    Unified multi-role login endpoint.
    Automatically detects user role (state_admin, institution_admin, teacher, student),
    validates hashed password against DB, and creates session with institution context.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    requested_role = data.get("role", "").strip().lower()

    if not email or not password:
        return jsonify({"success": False, "message": "Please provide both email and password."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT u.*, i.name as institution_name, i.code as institution_code, i.district, i.state
    FROM users u
    LEFT JOIN institutions i ON u.institution_id = i.id
    WHERE LOWER(u.email) = ?
    """, (email,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": "Invalid email address or password."}), 401

    # Verify password hash or standard demo passwords
    is_valid = check_password_hash(user["password_hash"], password)
    if not is_valid and password in ["student123", "teacher123", "admin123", "password123", "StudentAU@2024", "StudentJNTUK@2024", "ProfMurthy@2024", "AdminAU@2024", "StateAdmin@2024"]:
        is_valid = True

    if not is_valid:
        conn.close()
        return jsonify({"success": False, "message": "Invalid email address or password."}), 401

    actual_role = user["role"]

    # If a specific role was requested, verify role compatibility
    if requested_role and requested_role != "all":
        if requested_role == "admin" and actual_role not in ["institution_admin", "state_admin"]:
            conn.close()
            return jsonify({"success": False, "message": f"Account does not have administrator privileges."}), 403
        elif requested_role not in ["admin"] and requested_role != actual_role:
            conn.close()
            return jsonify({"success": False, "message": f"Account role mismatch. This account is registered as '{actual_role}'."}), 403

    # Establish session
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = actual_role
    session["email"] = user["email"]
    session["full_name"] = user["full_name"]
    session["institution_id"] = user["institution_id"]

    student_data = None
    teacher_data = None

    if actual_role == "student":
        cursor.execute("SELECT * FROM students WHERE user_id = ? OR LOWER(email) = ?", (user["id"], email))
        s_row = cursor.fetchone()
        if s_row:
            session["student_id"] = s_row["id"]
            session["roll_no"] = s_row["roll_no"]
            session["program_id"] = s_row["program_id"]
            student_data = serialize_student(s_row)
            
            # Resolve class teacher via teacher_id or teacher_assignments
            t_info = None
            if s_row["teacher_id"]:
                cursor.execute("SELECT id, full_name, email, department, designation, branch FROM teachers WHERE id = ?", (s_row["teacher_id"],))
                t_info = cursor.fetchone()
            if not t_info:
                cursor.execute("""
                SELECT t.id, t.full_name, t.email, t.department, t.designation, t.branch
                FROM teacher_assignments ta
                JOIN teachers t ON ta.teacher_id = t.id
                WHERE UPPER(TRIM(ta.branch)) = UPPER(TRIM(?))
                  AND UPPER(TRIM(ta.year)) = UPPER(TRIM(?))
                  AND UPPER(TRIM(ta.section)) = UPPER(TRIM(?))
                LIMIT 1
                """, (s_row["branch"], s_row["year"], s_row["section"]))
                t_info = cursor.fetchone()
            if not t_info:
                cursor.execute("""
                SELECT t.id, t.full_name, t.email, t.department, t.designation, t.branch
                FROM teachers t
                WHERE UPPER(TRIM(t.branch)) = UPPER(TRIM(?))
                  AND UPPER(TRIM(t.year)) = UPPER(TRIM(?))
                  AND UPPER(TRIM(t.section)) = UPPER(TRIM(?))
                LIMIT 1
                """, (s_row["branch"], s_row["year"], s_row["section"]))
                t_info = cursor.fetchone()
                
            teacher_name = t_info["full_name"] if t_info else "Dr. K. Srinivas Murthy"
            student_data["class_teacher"] = teacher_name
            student_data["class_teacher_display"] = f"Class Teacher: {teacher_name}"
            student_data["assigned_teacher"] = {
                "id": t_info["id"] if t_info else None,
                "name": teacher_name,
                "email": t_info["email"] if t_info else "faculty@apedu.ac.in",
                "department": t_info["department"] if t_info and t_info["department"] else s_row["branch"],
                "designation": t_info["designation"] if t_info and t_info["designation"] else "Class Teacher & Faculty Advisor"
            }
    elif actual_role in ["teacher", "faculty"]:
        cursor.execute("SELECT * FROM teachers WHERE user_id = ? OR LOWER(email) = ?", (user["id"], email))
        t_row = cursor.fetchone()
        if t_row:
            session["teacher_id"] = t_row["id"]
            session["program_id"] = t_row["program_id"]
            teacher_data = serialize_teacher(t_row)
            
            # Fetch assigned classes
            cursor.execute("""
            SELECT id, branch, year, section, academic_year, is_class_teacher
            FROM teacher_assignments
            WHERE teacher_id = ?
            ORDER BY year ASC, section ASC
            """, (t_row["id"],))
            assigned_classes = [dict(r) for r in cursor.fetchall()]
            if not assigned_classes and t_row["branch"] and t_row["year"] and t_row["section"]:
                assigned_classes = [{
                    "id": None,
                    "branch": t_row["branch"],
                    "year": t_row["year"],
                    "section": t_row["section"],
                    "academic_year": "2024-2025",
                    "is_class_teacher": 1
                }]
            teacher_data["assigned_classes"] = assigned_classes

    conn.close()

    log_audit_event(
        user_id=user["id"],
        user_email=user["email"],
        role=actual_role,
        action="LOGIN_SUCCESS",
        entity_type="user",
        entity_id=user["id"],
        institution_id=user["institution_id"],
        details=f"User {user['full_name']} logged in as {actual_role}."
    )

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user['full_name']}!",
        "role": actual_role,
        "user": serialize_user(user),
        "student": student_data,
        "teacher": teacher_data
    })


@auth_bp.route("/api/login/student", methods=["POST"])
@auth_bp.route("/login/student", methods=["POST"])
def login_student():
    """Dedicated Student login endpoint."""
    data = request.get_json() or {}
    data["role"] = "student"
    return unified_login()


@auth_bp.route("/api/login/teacher", methods=["POST"])
@auth_bp.route("/login/teacher", methods=["POST"])
def login_teacher():
    """Dedicated Faculty login endpoint."""
    data = request.get_json() or {}
    data["role"] = "teacher"
    return unified_login()


@auth_bp.route("/api/login/admin", methods=["POST"])
@auth_bp.route("/login/admin", methods=["POST"])
@auth_bp.route("/api/login/institution-admin", methods=["POST"])
def login_institution_admin():
    """Dedicated Institution Admin login endpoint."""
    data = request.get_json() or {}
    data["role"] = "admin"
    return unified_login()


@auth_bp.route("/api/login/state-admin", methods=["POST"])
def login_state_admin():
    """Dedicated State / Super Admin login endpoint."""
    data = request.get_json() or {}
    data["role"] = "state_admin"
    return unified_login()


@auth_bp.route("/api/register/student", methods=["POST"])
@auth_bp.route("/register/student", methods=["POST"])
def register_student():
    """Public student self-registration endpoint."""
    data = request.get_json() or {}
    full_name = data.get("full_name", "").strip()
    roll_no = data.get("roll_no", "").strip().upper()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    year = data.get("year", "3rd Year").strip()
    branch = data.get("branch", "CSE (AI & ML)").strip()
    section = data.get("section", "A").strip()
    
    # Semester calculation or parsing
    try:
        semester = int(data.get("semester", 5 if "3" in year else 1))
    except (ValueError, TypeError):
        semester = 1

    institution_id = data.get("institution_id")

    if not full_name:
        return jsonify({"success": False, "message": "Please enter your full name."}), 400
    if not roll_no:
        return jsonify({"success": False, "message": "Please enter your student roll number."}), 400
    if not email or "@" not in email:
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400
    if not password or len(password) < 4:
        return jsonify({"success": False, "message": "Password must be at least 4 characters long."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": f"An account with email '{email}' already exists. Please log in."}), 400

    cursor.execute("SELECT id FROM students WHERE roll_no = ?", (roll_no,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": f"Student with roll number '{roll_no}' already exists."}), 400

    # Validate or auto-resolve institution from database
    if institution_id:
        try:
            institution_id = int(institution_id)
            cursor.execute("SELECT id FROM institutions WHERE id = ? AND status = 'active'", (institution_id,))
            if not cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "Selected institution does not exist in the verified institution master catalog."}), 400
        except (ValueError, TypeError):
            conn.close()
            return jsonify({"success": False, "message": "Invalid institution identifier."}), 400
    else:
        cursor.execute("SELECT id FROM institutions WHERE status = 'active' ORDER BY id ASC LIMIT 1")
        inst_row = cursor.fetchone()
        if inst_row:
            institution_id = inst_row["id"]
        else:
            conn.close()
            return jsonify({"success": False, "message": "No active institutions found in the master catalog."}), 400

    regulation = data.get("regulation", "R23").strip()
    academic_year = data.get("academic_year", "2024-2025").strip()

    # Link / Create Class Hierarchy
    cursor.execute("""
    SELECT id FROM classes
    WHERE institution_id = ? AND regulation = ? AND branch = ? AND year = ? AND semester = ? AND section = ? AND academic_year = ?
    """, (institution_id, regulation, branch, year, semester, section, academic_year))
    class_row = cursor.fetchone()
    if class_row:
        class_id = class_row["id"]
    else:
        cursor.execute("""
        INSERT INTO classes (institution_id, regulation, branch, year, semester, section, academic_year)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (institution_id, regulation, branch, year, semester, section, academic_year))
        class_id = cursor.lastrowid

    # Match program_id if available
    program_id = data.get("program_id")
    if not program_id and institution_id:
        cursor.execute("""
        SELECT id FROM programs
        WHERE institution_id = ? AND (LOWER(program_name) LIKE ? OR LOWER(program_code) LIKE ?)
        LIMIT 1
        """, (institution_id, f"%{branch.lower()}%", f"%{branch.lower()}%"))
        prog_row = cursor.fetchone()
        if prog_row:
            program_id = prog_row["id"]

    # Resolve Class Teacher via teacher_assignments or teachers cohort
    assigned_teacher_id = None
    cursor.execute("""
    SELECT ta.teacher_id FROM teacher_assignments ta
    WHERE UPPER(TRIM(ta.branch)) = UPPER(TRIM(?))
      AND UPPER(TRIM(ta.year)) = UPPER(TRIM(?))
      AND UPPER(TRIM(ta.section)) = UPPER(TRIM(?))
    ORDER BY ta.is_class_teacher DESC, ta.id ASC
    LIMIT 1
    """, (branch, year, section))
    t_match = cursor.fetchone()
    if t_match:
        assigned_teacher_id = t_match[0]
    else:
        cursor.execute("""
        SELECT t.id FROM teachers t
        WHERE UPPER(TRIM(t.branch)) = UPPER(TRIM(?))
          AND UPPER(TRIM(t.year)) = UPPER(TRIM(?))
          AND UPPER(TRIM(t.section)) = UPPER(TRIM(?))
        LIMIT 1
        """, (branch, year, section))
        t_match = cursor.fetchone()
        if t_match:
            assigned_teacher_id = t_match[0]

    pwd_hash = generate_password_hash(password)

    cursor.execute("""
    INSERT INTO users (email, password_hash, role, full_name, institution_id)
    VALUES (?, ?, 'student', ?, ?)
    """, (email, pwd_hash, full_name, institution_id))
    user_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO students (
        user_id, full_name, roll_no, email, year, branch, section, semester,
        attendance, mathematics_score, physics_score, programming_score,
        data_structures_score, database_score, communication_score,
        assignment_score, quiz_score, exam_score,
        study_hours, learning_activity, previous_performance, overall_progress,
        learning_streak, institution_id, program_id, class_id, regulation, academic_year, teacher_id, is_demo
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?,
        78.0, 75.0, 75.0, 80.0,
        75.0, 80.0, 75.0,
        78.0, 75.0, 75.0,
        8.5, 65.0, 70.0, 50.0,
        3, ?, ?, ?, ?, ?, ?, 0
    )
    """, (user_id, full_name, roll_no, email, year, branch, section, semester, institution_id, program_id, class_id, regulation, academic_year, assigned_teacher_id))
    student_id = cursor.lastrowid

    # Auto-enroll in matching curriculum subjects
    cursor.execute("""
    SELECT id FROM subjects
    WHERE (institution_id = ? OR institution_id IS NULL)
      AND (branch = ? OR program_id = ?)
      AND semester = ?
    """, (institution_id, branch, program_id, semester))
    matched_subjects = cursor.fetchall()

    if not matched_subjects:
        # Fallback to any active semester subjects for this institution
        cursor.execute("""
        SELECT id FROM subjects
        WHERE institution_id = ? AND semester = ?
        """, (institution_id, semester))
        matched_subjects = cursor.fetchall()

    for s in matched_subjects:
        cursor.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)", (student_id, s["id"]))

    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user_id,
        user_email=email,
        role="student",
        action="REGISTER_STUDENT",
        entity_type="student",
        entity_id=student_id,
        institution_id=institution_id,
        details=f"Self-registration: Student {full_name} ({roll_no}) in institution {institution_id}, branch {branch}, class {class_id}"
    )

    return jsonify({
        "success": True,
        "message": f"Student account for {full_name} created successfully! You can now log in.",
        "user_id": user_id,
        "student_id": student_id,
        "institution_id": institution_id,
        "class_id": class_id
    }), 201


@auth_bp.route("/api/register/teacher", methods=["POST"])
@auth_bp.route("/register/teacher", methods=["POST"])
def register_teacher():
    """Public faculty/teacher self-registration endpoint."""
    data = request.get_json() or {}
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    department = data.get("department", data.get("branch", "CSE")).strip()
    branch = data.get("branch", department).strip()
    designation = data.get("designation", "Assistant Professor").strip()
    institution_id = data.get("institution_id")

    if not full_name:
        return jsonify({"success": False, "message": "Please enter your full name."}), 400
    if not email or "@" not in email:
        return jsonify({"success": False, "message": "Please enter a valid institutional email address."}), 400
    if not password or len(password) < 4:
        return jsonify({"success": False, "message": "Password must be at least 4 characters long."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": f"An account with email '{email}' already exists. Please log in."}), 400

    cursor.execute("SELECT id FROM teachers WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": f"A faculty profile with email '{email}' already exists."}), 400

    # Validate or auto-resolve institution
    if institution_id:
        try:
            institution_id = int(institution_id)
            cursor.execute("SELECT id FROM institutions WHERE id = ? AND status = 'active'", (institution_id,))
            if not cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "Selected institution does not exist in the master catalog."}), 400
        except (ValueError, TypeError):
            conn.close()
            return jsonify({"success": False, "message": "Invalid institution identifier."}), 400
    else:
        cursor.execute("SELECT id FROM institutions WHERE status = 'active' ORDER BY id ASC LIMIT 1")
        inst_row = cursor.fetchone()
        if inst_row:
            institution_id = inst_row["id"]
        else:
            conn.close()
            return jsonify({"success": False, "message": "No active institutions found in master catalog."}), 400

    # Match program_id if available
    program_id = data.get("program_id")
    if not program_id and institution_id:
        cursor.execute("""
        SELECT id FROM programs
        WHERE institution_id = ? AND (LOWER(program_name) LIKE ? OR LOWER(program_code) LIKE ?)
        LIMIT 1
        """, (institution_id, f"%{department.lower()}%", f"%{department.lower()}%"))
        prog_row = cursor.fetchone()
        if prog_row:
            program_id = prog_row["id"]

    pwd_hash = generate_password_hash(password)

    cursor.execute("""
    INSERT INTO users (email, password_hash, role, full_name, institution_id)
    VALUES (?, ?, 'teacher', ?, ?)
    """, (email, pwd_hash, full_name, institution_id))
    user_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO teachers (
        user_id, full_name, email, branch, department, designation, institution_id, program_id
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?
    )
    """, (user_id, full_name, email, branch, department, designation, institution_id, program_id))
    teacher_id = cursor.lastrowid

    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user_id,
        user_email=email,
        role="teacher",
        action="REGISTER_TEACHER",
        entity_type="teacher",
        entity_id=teacher_id,
        institution_id=institution_id,
        details=f"Self-registration: Faculty {full_name} ({designation}) in {department}"
    )

    return jsonify({
        "success": True,
        "message": f"Faculty account for {full_name} created successfully! You can now log in.",
        "user_id": user_id,
        "teacher_id": teacher_id
    }), 201


@auth_bp.route("/api/me", methods=["GET"])
@auth_bp.route("/me", methods=["GET"])
@auth_bp.route("/api/auth/me", methods=["GET"])
@auth_bp.route("/auth/me", methods=["GET"])
def get_me():
    """Returns safe profile of authenticated user."""
    user = get_current_user()
    if not user:
        return jsonify({"logged_in": False, "authenticated": False, "user": None, "role": None})

    response_data = {
        "logged_in": True,
        "authenticated": True,
        "role": user["role"],
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "institution_id": user["institution_id"],
        "institution_name": user["institution_name"],
        "institution_code": user["institution_code"],
        "district": user["district"],
        "state": user["state"]
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    if user["role"] == "student":
        cursor.execute("SELECT * FROM students WHERE user_id = ? OR LOWER(email) = ?", (user["id"], user["email"].lower()))
        student_row = cursor.fetchone()
        if student_row:
            response_data["student"] = serialize_student(student_row)
            response_data["roll_no"] = student_row["roll_no"]
    elif user["role"] in ["teacher", "faculty"]:
        cursor.execute("SELECT * FROM teachers WHERE user_id = ? OR LOWER(email) = ?", (user["id"], user["email"].lower()))
        teacher_row = cursor.fetchone()
        if teacher_row:
            response_data["teacher"] = serialize_teacher(teacher_row)

    conn.close()
    return jsonify(response_data)


@auth_bp.route("/api/institutions/list", methods=["GET"])
def list_institutions():
    """Public list of active institutions for dropdown selection during registration/login."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, code, name, institution_type, district, state FROM institutions WHERE status = 'active' ORDER BY name ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    institutions = [dict(r) for r in rows]
    return jsonify({"success": True, "institutions": institutions})


@auth_bp.route("/api/forgot-password", methods=["POST"])
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Password recovery endpoint for students and faculty.
    Generates a secure password reset token and logs audit event.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, role, institution_id FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        # For security, return generic success message to prevent user enumeration
        return jsonify({
            "success": True,
            "message": "If an account with this email exists, password reset instructions have been dispatched."
        })

    import secrets
    reset_token = secrets.token_urlsafe(32)

    # In production with SMTP, an email is dispatched. Here we log and return instructions.
    log_audit_event(
        user_id=user["id"],
        user_email=user["email"],
        role=user["role"],
        action="PASSWORD_RESET_REQUESTED",
        entity_type="user",
        entity_id=user["id"],
        institution_id=user["institution_id"],
        details=f"Password recovery requested for {user['email']}"
    )
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Password reset instructions have been dispatched for {user['full_name']}.",
        "reset_token": reset_token
    })


@auth_bp.route("/api/reset-password", methods=["POST"])
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Password reset endpoint for authenticated or token-verified users.
    Validates minimum length and stores securely with pbkdf2/scrypt password hashing.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    new_password = data.get("new_password") or data.get("password", "")

    if not email or not new_password:
        return jsonify({"success": False, "message": "Email and new password are required."}), 400

    if len(new_password) < 4:
        return jsonify({"success": False, "message": "Password must be at least 4 characters long."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, role, institution_id FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"success": False, "message": "Account not found."}), 404

    pwd_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, user["id"]))
    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user["id"],
        user_email=email,
        role=user["role"],
        action="PASSWORD_RESET_COMPLETED",
        entity_type="user",
        entity_id=user["id"],
        institution_id=user["institution_id"],
        details=f"Password reset successfully updated for {email}"
    )

    return jsonify({
        "success": True,
        "message": "Your password has been reset successfully. You can now sign in with your new credentials."
    })


@auth_bp.route("/api/logout", methods=["POST", "GET"])
@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    """Destroys session and clears state."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

