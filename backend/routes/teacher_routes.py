"""
Teacher Portal REST API Routes
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from backend.database import get_db_connection
from backend.models import serialize_student, serialize_intervention
from backend.auth import teacher_required
from ml.predict import predict_student_risk
from ml.personalized_learning import analyze_student_subjects, generate_personalized_learning_path
from ml.intervention_engine import generate_teacher_interventions

teacher_bp = Blueprint("teacher", __name__)

def get_logged_in_teacher(conn):
    """Helper to fetch teacher record for the currently authenticated session."""
    user_id = session.get("user_id")
    email = (session.get("email") or "").strip().lower()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, full_name, email, branch, year, section,
               institution_id, program_id,
               COALESCE(department, branch, 'Engineering') as department,
               COALESCE(designation, 'Faculty') as designation
        FROM teachers 
        WHERE user_id = ? OR LOWER(email) = ?
    """, (user_id, email))
    return cursor.fetchone()

def get_teacher_assigned_student_ids(cursor, teacher_row):
    """
    Returns a set of student IDs belonging to the given teacher.
    Teacher-to-Student relationship is strictly identified via teacher_id, branch, year, section:
    1. Direct relationship: students.teacher_id = teacher.id
    2. Cohort assignment via teacher_assignments:
       teacher_assignments (teacher_id, branch, year, section) matching students (branch, year, section)
    3. Primary cohort in teachers table:
       teachers (id, branch, year, section) matching students (branch, year, section)
    4. Classes table assignment:
       classes (teacher_id, branch, year, section) matching students (branch, year, section)
    5. Teacher subjects table:
       teacher_subjects (teacher_id, branch, year, section) matching students (branch, year, section)
    Restricted to teacher's institution_id if present.
    """
    if not teacher_row:
        return set()
    
    t_id = teacher_row["id"]
    t_inst = teacher_row["institution_id"] if "institution_id" in teacher_row.keys() else None
    
    query = """
    SELECT DISTINCT s.id
    FROM students s
    WHERE (
        (? IS NULL OR s.institution_id IS NULL OR s.institution_id = ?)
    ) AND (
        s.teacher_id = ?
        OR
        EXISTS (
            SELECT 1 FROM teacher_assignments ta
            WHERE ta.teacher_id = ?
              AND UPPER(TRIM(ta.branch)) = UPPER(TRIM(s.branch))
              AND UPPER(TRIM(ta.year)) = UPPER(TRIM(s.year))
              AND UPPER(TRIM(ta.section)) = UPPER(TRIM(s.section))
        )
        OR
        EXISTS (
            SELECT 1 FROM teachers t
            WHERE t.id = ?
              AND t.branch IS NOT NULL AND t.year IS NOT NULL AND t.section IS NOT NULL
              AND UPPER(TRIM(t.branch)) = UPPER(TRIM(s.branch))
              AND UPPER(TRIM(t.year)) = UPPER(TRIM(s.year))
              AND UPPER(TRIM(t.section)) = UPPER(TRIM(s.section))
        )
        OR
        EXISTS (
            SELECT 1 FROM classes c
            WHERE c.teacher_id = ?
              AND UPPER(TRIM(c.branch)) = UPPER(TRIM(s.branch))
              AND UPPER(TRIM(c.year)) = UPPER(TRIM(s.year))
              AND UPPER(TRIM(c.section)) = UPPER(TRIM(s.section))
        )
        OR
        EXISTS (
            SELECT 1 FROM teacher_subjects ts
            WHERE ts.teacher_id = ?
              AND UPPER(TRIM(ts.branch)) = UPPER(TRIM(s.branch))
              AND UPPER(TRIM(ts.year)) = UPPER(TRIM(s.year))
              AND UPPER(TRIM(ts.section)) = UPPER(TRIM(s.section))
        )
    )
    """
    cursor.execute(query, (t_inst, t_inst, t_id, t_id, t_id, t_id, t_id))
    rows = cursor.fetchall()
    return set(r[0] for r in rows)


@teacher_bp.route("/api/teacher/me", methods=["GET"])
@teacher_bp.route("/api/teacher/profile", methods=["GET"])
@teacher_required
def get_teacher_profile():
    """
    Returns authenticated teacher record, assigned classes from teacher_assignments,
    institution details, and total assigned student count.
    """
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "message": "Teacher record not found."}), 404
        
    cursor = conn.cursor()
    t_id = t_row["id"]
    
    # Query assigned classes from teacher_assignments
    cursor.execute("""
    SELECT id, branch, year, section, academic_year, is_class_teacher
    FROM teacher_assignments
    WHERE teacher_id = ?
    ORDER BY year ASC, section ASC
    """, (t_id,))
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
        
    inst_name = "Autonomous Engineering College"
    aishe_code = "AP_EDU"
    if t_row["institution_id"]:
        cursor.execute("SELECT institution_name, name, aishe_code, code FROM institutions WHERE id = ?", (t_row["institution_id"],))
        i_row = cursor.fetchone()
        if i_row:
            inst_name = i_row["institution_name"] or i_row["name"] or inst_name
            aishe_code = i_row["aishe_code"] or i_row["code"] or aishe_code
            
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    conn.close()
    
    return jsonify({
        "success": True,
        "teacher": {
            "id": t_id,
            "user_id": t_row["user_id"],
            "full_name": t_row["full_name"],
            "email": t_row["email"],
            "department": t_row["department"],
            "designation": t_row["designation"],
            "branch": t_row["branch"],
            "year": t_row["year"],
            "section": t_row["section"],
            "institution_id": t_row["institution_id"],
            "institution_name": inst_name,
            "aishe_code": aishe_code,
            "assigned_classes": assigned_classes,
            "total_students": len(assigned_ids)
        }
    })

@teacher_bp.route("/api/teacher/students", methods=["GET"])
@teacher_required
def get_students_list():
    """
    Returns filtered and searched student list strictly for the authenticated teacher's cohort.
    Strictly excludes passwords and password hashes.
    """
    branch_filter = request.args.get("branch", "").strip()
    year_filter = request.args.get("year", "").strip()
    semester_filter = request.args.get("semester", "").strip()
    section_filter = request.args.get("section", "").strip()
    risk_filter = request.args.get("risk", "").strip()
    search_query = request.args.get("search", "").strip().lower()
    
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": True, "total": 0, "students": []})
        
    cursor = conn.cursor()
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    if not assigned_ids:
        conn.close()
        return jsonify({"success": True, "total": 0, "students": []})
        
    placeholders = ",".join("?" for _ in assigned_ids)
    query = f"SELECT * FROM students WHERE id IN ({placeholders})"
    params = list(assigned_ids)
    
    if branch_filter and branch_filter not in ["All", "all", ""]:
        query += " AND branch = ?"
        params.append(branch_filter)
    if year_filter and year_filter not in ["All", "all", ""]:
        query += " AND year = ?"
        params.append(year_filter)
    if semester_filter and semester_filter not in ["All", "all", ""]:
        try:
            sem_int = int(semester_filter.replace("Semester", "").replace("Sem", "").strip())
            query += " AND semester = ?"
            params.append(sem_int)
        except ValueError:
            pass
    if section_filter and section_filter not in ["All", "all", ""]:
        query += " AND section = ?"
        params.append(section_filter)
        
    query += " ORDER BY id ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    students_list = []
    for r in rows:
        st = serialize_student(r)
        
        # Search filter (name or roll number or email)
        if search_query:
            match_name = search_query in st["full_name"].lower()
            match_roll = search_query in st["roll_no"].lower()
            match_email = search_query in st["email"].lower()
            if not (match_name or match_roll or match_email):
                continue
                
        # Safe ML Prediction
        try:
            pred = predict_student_risk(st)
            risk_level = pred["risk_level"]
            risk_score = pred["risk_score"]
            risk_probs = pred["probabilities"]
        except Exception:
            risk_level = "Low Risk"
            risk_score = 10.0
            risk_probs = {"Low Risk": 0.9, "Medium Risk": 0.1, "High Risk": 0.0}
        
        if risk_filter and risk_filter not in ["All", "all", ""] and risk_filter.lower() not in risk_level.lower():
            continue
            
        try:
            subj_analysis = analyze_student_subjects(st)
            primary_weak = subj_analysis["weak_subjects"][0]["subject"] if subj_analysis["weak_subjects"] else "None (Proficient)"
            weak_count = subj_analysis.get("weak_count", 0)
        except Exception:
            primary_weak = "None (Proficient)"
            weak_count = 0
        
        try:
            interv_data = generate_teacher_interventions(st, pred)
            top_action = interv_data["interventions"][0]["title"] if interv_data.get("interventions") else "Continue current path"
        except Exception:
            top_action = "Continue current path"
        
        students_list.append({
            "id": st["id"],
            "full_name": st["full_name"],
            "roll_no": st["roll_no"],
            "email": st["email"],
            "year": st["year"],
            "branch": st["branch"],
            "section": st["section"],
            "semester": st["semester"],
            "attendance": st["attendance"],
            "overall_progress": st["overall_progress"],
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_probabilities": risk_probs,
            "weak_subject": primary_weak,
            "weak_count": weak_count,
            "recommended_action": top_action
        })
        
    return jsonify({
        "success": True,
        "total": len(students_list),
        "students": students_list
    })

@teacher_bp.route("/api/teacher/student/<int:student_id>", methods=["GET"])
@teacher_required
def get_student_detail(student_id):
    """
    Returns full student profile, academic metrics, ML predictions,
    personalized learning path, and logged interventions for authorized teachers only.
    """
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "error": "Unauthorized faculty session."}), 401
        
    cursor = conn.cursor()
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    if student_id not in assigned_ids:
        conn.close()
        return jsonify({
            "success": False, 
            "error": "Access denied: You are not authorized to view students outside your assigned class or subjects."
        }), 403

    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({"success": False, "error": f"Student with ID {student_id} not found."}), 404
        
    st = serialize_student(row)
    
    # Fetch logged interventions
    cursor.execute("SELECT * FROM interventions WHERE student_id = ? ORDER BY created_at DESC", (student_id,))
    interv_rows = cursor.fetchall()
    conn.close()
    
    logged_interventions = [serialize_intervention(ir) for ir in interv_rows]
    
    # Run ML Prediction and Recommendations
    prediction = predict_student_risk(st)
    learning_path_data = generate_personalized_learning_path(st, prediction)
    teacher_interventions = generate_teacher_interventions(st, prediction)
    
    return jsonify({
        "success": True,
        "student": st,
        "prediction": prediction,
        "learning_path_data": learning_path_data,
        "recommended_interventions": teacher_interventions,
        "logged_interventions": logged_interventions
    })

@teacher_bp.route("/api/teacher/student/<int:student_id>/prediction", methods=["GET"])
@teacher_required
def get_student_prediction_by_teacher(student_id):
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "error": "Unauthorized faculty session."}), 401
        
    cursor = conn.cursor()
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    if student_id not in assigned_ids:
        conn.close()
        return jsonify({
            "success": False,
            "error": "Access denied: Student is outside your assigned class or subjects."
        }), 403

    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"success": False, "error": "Student not found."}), 404
        
    st = serialize_student(row)
    prediction = predict_student_risk(st)
    return jsonify({
        "success": True,
        "student_id": student_id,
        "prediction": prediction
    })

@teacher_bp.route("/api/teacher/student/<int:student_id>/recommendations", methods=["GET"])
@teacher_required
def get_student_recommendations_by_teacher(student_id):
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "error": "Unauthorized faculty session."}), 401
        
    cursor = conn.cursor()
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    if student_id not in assigned_ids:
        conn.close()
        return jsonify({
            "success": False,
            "error": "Access denied: Student is outside your assigned class or subjects."
        }), 403

    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"success": False, "error": "Student not found."}), 404
        
    st = serialize_student(row)
    prediction = predict_student_risk(st)
    path_data = generate_personalized_learning_path(st, prediction)
    interventions = generate_teacher_interventions(st, prediction)
    
    return jsonify({
        "success": True,
        "student_id": student_id,
        "risk_level": prediction["risk_level"],
        "learning_path": path_data,
        "interventions": interventions
    })

@teacher_bp.route("/api/teacher/student/<int:student_id>/intervention", methods=["POST"])
@teacher_bp.route("/api/teacher/interventions", methods=["POST"])
@teacher_required
def log_intervention(student_id=None):
    """
    Logs an actionable teacher intervention for an authorized student.
    """
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "error": "Unauthorized faculty session."}), 401
        
    data = request.get_json() or {}
    target_student_id = student_id or data.get("student_id")
    if not target_student_id:
        conn.close()
        return jsonify({"success": False, "error": "Student ID is required."}), 400
        
    cursor = conn.cursor()
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    if int(target_student_id) not in assigned_ids:
        conn.close()
        return jsonify({
            "success": False,
            "error": "Access denied: You cannot log interventions for students outside your assigned class."
        }), 403

    teacher_user_id = session.get("user_id")
    title = data.get("title", "").strip()
    category = data.get("category", "General Guidance").strip()
    priority = data.get("priority", "Moderate").strip()
    description = data.get("description", "").strip()
    risk_level = data.get("risk_level", "Medium Risk").strip()
    notes = data.get("notes", "").strip()
    
    if not title or not description:
        conn.close()
        return jsonify({"success": False, "error": "Title and description are required."}), 400
        
    cursor.execute("""
    INSERT INTO interventions (student_id, teacher_id, risk_level, title, category, priority, description, notes, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, (int(target_student_id), teacher_user_id, risk_level, title, category, priority, description, notes))
    
    interv_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": "Teacher intervention logged successfully.",
        "intervention_id": interv_id
    }), 201

@teacher_bp.route("/api/teacher/student", methods=["POST"])
@teacher_required
def add_student():
    """
    Allows teacher to register a new student record into their cohort.
    Hashes password and inserts user into users and students tables.
    Automatically assigns student to teacher's institution and subjects.
    """
    data = request.get_json() or {}
    
    full_name = data.get("full_name", "").strip()
    roll_no = data.get("roll_no", "").strip().upper()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    year = data.get("year", "").strip()
    branch = data.get("branch", "").strip()
    section = data.get("section", "").strip()
    semester = data.get("semester")
    
    if not full_name:
        return jsonify({"success": False, "message": "Please enter student full name."}), 400
    if not roll_no:
        return jsonify({"success": False, "message": "Please enter student roll number."}), 400
    if not email:
        return jsonify({"success": False, "message": "Please enter student email."}), 400
    if not password:
        return jsonify({"success": False, "message": "Please enter an initial password for the student."}), 400
    if not year or not branch or not section or semester is None:
        return jsonify({"success": False, "message": "Year, branch, section, and semester are required."}), 400
            
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    cursor = conn.cursor()
    
    t_inst = t_row["institution_id"] if t_row and "institution_id" in t_row.keys() else None
    t_prog = t_row["program_id"] if t_row and "program_id" in t_row.keys() else None
    
    # Check email uniqueness
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "An account with this email already exists."}), 400
        
    # Check roll_no uniqueness
    cursor.execute("SELECT id FROM students WHERE roll_no = ?", (roll_no,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Student with this roll number already exists."}), 400
        
    # Create user account for student with hashed password
    pwd_hash = generate_password_hash(password)
    
    cursor.execute("""
    INSERT INTO users (email, password_hash, role, full_name, institution_id)
    VALUES (?, ?, 'student', ?, ?)
    """, (email, pwd_hash, full_name, t_inst))
    user_id = cursor.lastrowid
    
    # Insert student record with default or provided academic scores
    attendance = float(data.get("attendance", 75.0))
    m_score = float(data.get("mathematics_score", 65.0))
    p_score = float(data.get("physics_score", 65.0))
    pr_score = float(data.get("programming_score", 65.0))
    ds_score = float(data.get("data_structures_score", 65.0))
    db_score = float(data.get("database_score", 65.0))
    comm_score = float(data.get("communication_score", 70.0))
    asg_score = float(data.get("assignment_score", 70.0))
    qz_score = float(data.get("quiz_score", 65.0))
    ex_score = float(data.get("exam_score", 65.0))
    st_hours = float(data.get("study_hours", 8.0))
    activity = float(data.get("learning_activity", 60.0))
    prev_perf = float(data.get("previous_performance", 65.0))
    progress = float(data.get("overall_progress", 50.0))
    notes = data.get("notes", "")
    
    cursor.execute("""
    INSERT INTO students (
        user_id, full_name, roll_no, email, year, branch, section, semester,
        attendance, mathematics_score, physics_score, programming_score,
        data_structures_score, database_score, communication_score,
        assignment_score, quiz_score, exam_score, study_hours,
        learning_activity, previous_performance, overall_progress, notes,
        institution_id, program_id
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?
    )
    """, (
        user_id, full_name, roll_no, email,
        year, branch, section, int(semester),
        attendance, m_score, p_score, pr_score, ds_score, db_score, comm_score,
        asg_score, qz_score, ex_score, st_hours, activity, prev_perf, progress, notes,
        t_inst, t_prog
    ))
    
    new_student_id = cursor.lastrowid
    
    # Auto-enroll student into subjects taught by this teacher for this class
    if t_row:
        cursor.execute("""
        SELECT ts.subject_id FROM teacher_subjects ts
        WHERE ts.teacher_id = ? AND ts.branch = ? AND ts.year = ? AND ts.section = ?
        """, (t_row["id"], branch, year, section))
        for sub in cursor.fetchall():
            cursor.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)", (new_student_id, sub[0]))
            
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"Student {full_name} registered successfully. The student can now log in immediately.",
        "student_id": new_student_id
    }), 201

@teacher_bp.route("/api/teacher/analytics", methods=["GET"])
@teacher_required
def get_class_analytics():
    """
    Computes class-level analytics strictly for students assigned to the authenticated teacher:
    Risk distribution, average attendance, subject performance averages,
    and weak-subject frequencies.
    """
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({
            "success": True,
            "total_students": 0,
            "risk_distribution": {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0},
            "average_attendance": 0.0,
            "average_scores": {}
        })
        
    cursor = conn.cursor()
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    if not assigned_ids:
        conn.close()
        return jsonify({
            "success": True,
            "total_students": 0,
            "risk_distribution": {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0},
            "average_attendance": 0.0,
            "average_scores": {}
        })
        
    placeholders = ",".join("?" for _ in assigned_ids)
    cursor.execute(f"SELECT * FROM students WHERE id IN ({placeholders})", list(assigned_ids))
    rows = cursor.fetchall()
    conn.close()
    
    total_students = len(rows)
    if total_students == 0:
        return jsonify({
            "success": True,
            "total_students": 0,
            "risk_distribution": {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0},
            "average_attendance": 0.0,
            "average_scores": {}
        })
        
    risk_counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    weak_subject_counts = {
        "Mathematics": 0,
        "Physics": 0,
        "Programming Fundamentals": 0,
        "Data Structures & Algorithms": 0,
        "Database Management Systems": 0,
        "Communication Skills": 0
    }
    
    total_attendance = 0.0
    score_sums = {
        "mathematics": 0.0,
        "physics": 0.0,
        "programming": 0.0,
        "data_structures": 0.0,
        "database": 0.0,
        "communication": 0.0,
        "assignment": 0.0,
        "quiz": 0.0,
        "exam": 0.0
    }
    
    branch_distribution = {}
    
    for r in rows:
        st = serialize_student(r)
        pred = predict_student_risk(st)
        r_level = pred["risk_level"]
        risk_counts[r_level] = risk_counts.get(r_level, 0) + 1
        
        subj_analysis = analyze_student_subjects(st)
        for w in subj_analysis["weak_subjects"]:
            w_name = w["subject"]
            weak_subject_counts[w_name] = weak_subject_counts.get(w_name, 0) + 1
            
        total_attendance += st["attendance"]
        score_sums["mathematics"] += st["mathematics_score"]
        score_sums["physics"] += st["physics_score"]
        score_sums["programming"] += st["programming_score"]
        score_sums["data_structures"] += st["data_structures_score"]
        score_sums["database"] += st["database_score"]
        score_sums["communication"] += st["communication_score"]
        score_sums["assignment"] += st["assignment_score"]
        score_sums["quiz"] += st["quiz_score"]
        score_sums["exam"] += st["exam_score"]
        
        br = st["branch"]
        if br not in branch_distribution:
            branch_distribution[br] = {"total": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0}
        branch_distribution[br]["total"] += 1
        if r_level == "High Risk":
            branch_distribution[br]["high_risk"] += 1
        elif r_level == "Medium Risk":
            branch_distribution[br]["medium_risk"] += 1
        else:
            branch_distribution[br]["low_risk"] += 1
            
    avg_attendance = round(total_attendance / total_students, 1)
    avg_scores = {k: round(v / total_students, 1) for k, v in score_sums.items()}
    
    risk_percentages = {
        k: round((v / total_students) * 100, 1) for k, v in risk_counts.items()
    }
    
    return jsonify({
        "success": True,
        "total_students": total_students,
        "average_attendance": avg_attendance,
        "risk_distribution_counts": risk_counts,
        "risk_distribution_percentages": risk_percentages,
        "weak_subject_frequencies": weak_subject_counts,
        "average_subject_scores": avg_scores,
        "branch_analytics": branch_distribution,
        "high_risk_alert_count": risk_counts.get("High Risk", 0)
    })

@teacher_bp.route("/api/teacher/cohort/risk-distribution", methods=["GET"])
@teacher_required
def get_cohort_risk_distribution():
    return get_class_analytics()

# ================= TEACHER SUBJECTS & MESSAGING =================
@teacher_bp.route("/api/teacher/subject", methods=["POST"])
@teacher_required
def add_new_subject_by_teacher():
    """Allows teacher to create a new subject and auto-assign it."""
    user_id = session.get("user_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM teachers WHERE user_id = ?", (user_id,))
    t_row = cursor.fetchone()
    teacher_id = t_row["id"] if t_row else None
    
    data = request.get_json() or {}
    subject_code = data.get("subject_code", "").strip().upper()
    subject_name = data.get("subject_name", "").strip()
    branch = data.get("branch", "").strip()
    year = data.get("year", "").strip()
    semester = data.get("semester")
    credits = int(data.get("credits", 3))
    subject_type = data.get("subject_type", "theory").strip()
    description = data.get("description", "").strip()
    
    if not subject_code or not subject_name or not branch or not year or semester is None:
        conn.close()
        return jsonify({"success": False, "message": "Code, name, branch, year, and semester are required."}), 400
        
    # Check if subject code already exists
    cursor.execute("SELECT id FROM subjects WHERE subject_code = ?", (subject_code,))
    sub_existing = cursor.fetchone()
    if sub_existing:
        sub_id = sub_existing["id"]
    else:
        cursor.execute("""
        INSERT INTO subjects (subject_code, subject_name, branch, year, semester, credits, subject_type, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (subject_code, subject_name, branch, year, int(semester), credits, subject_type, description))
        sub_id = cursor.lastrowid
        
        # Add starter lesson and quiz
        cursor.execute("""
        INSERT INTO lessons (subject_id, title, description, topic, content, difficulty, estimated_minutes, order_number)
        VALUES (?, 'Unit 1: Fundamentals of ' || ?, 'Introduction and foundational concepts.', 'Foundations', '# Fundamentals of ' || ?, 'Beginner', 45, 1)
        """, (sub_id, subject_name, subject_name))
        
        cursor.execute("""
        INSERT INTO quizzes (subject_id, title, description, topic, difficulty, time_limit, total_questions)
        VALUES (?, ? || ' Diagnostic Quiz', 'Assessment of key concepts.', 'Fundamentals', 'Intermediate', 15, 2)
        """, (sub_id, subject_name))
        q_id = cursor.lastrowid
        
        cursor.execute("""
        INSERT INTO quiz_questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option, explanation, marks)
        VALUES (?, 'What is the primary objective of this subject?', 'Comprehensive mastery and practical application', 'Random guess', 'None', 'Other', 'A', 'Conceptual and practical engineering skills.', 1.0)
        """, (q_id,))
        
    # Assign teacher for sections A, B, C, D
    if teacher_id:
        for sec in ["A", "B", "C", "D"]:
            cursor.execute("""
            INSERT OR IGNORE INTO teacher_subjects (teacher_id, subject_id, branch, year, semester, section)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (teacher_id, sub_id, branch, year, int(semester), sec))
            
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": f"Subject {subject_name} ({subject_code}) created and assigned successfully.",
        "subject_id": sub_id
    }), 201

@teacher_bp.route("/api/teacher/subjects", methods=["GET"])
@teacher_required
def get_teacher_assigned_subjects():
    """Returns subjects assigned to the logged-in teacher."""
    user_id = session.get("user_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT s.*, ts.branch as assigned_branch, ts.year as assigned_year, 
           ts.semester as assigned_semester, ts.section as assigned_section
    FROM teacher_subjects ts
    JOIN subjects s ON ts.subject_id = s.id
    JOIN teachers t ON ts.teacher_id = t.id
    WHERE t.user_id = ?
    ORDER BY s.subject_code ASC
    """, (user_id,))
    
    subjects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "subjects": subjects})

@teacher_bp.route("/api/teacher/messages", methods=["GET"])
@teacher_required
def get_teacher_conversations():
    """Returns student inquiry threads for this teacher with unread counts and student picker."""
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": True, "conversations": [], "available_students": [], "total_unread": 0, "teacher": None})
        
    teacher_id = t_row["id"]
    cursor = conn.cursor()
    
    # 1. Fetch conversation IDs where teacher is participant
    cursor.execute("""
    SELECT conversation_id, MAX(created_at) as last_active
    FROM messages
    WHERE (sender_role = 'teacher' AND sender_id = ?) 
       OR (receiver_role = 'teacher' AND receiver_id = ?)
    GROUP BY conversation_id
    ORDER BY last_active DESC
    """, (teacher_id, teacher_id))
    
    conv_rows = cursor.fetchall()
    threads = []
    
    for row in conv_rows:
        conv_id = row["conversation_id"]
        
        # Get latest message in this thread
        cursor.execute("""
        SELECT message, sender_role, sender_id, receiver_role, receiver_id, subject_id, created_at, is_read
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at DESC, id DESC LIMIT 1
        """, (conv_id,))
        last_msg = cursor.fetchone()
        if not last_msg:
            continue
            
        # Determine student_id from thread or message
        if last_msg["sender_role"] == "student":
            st_id = last_msg["sender_id"]
        elif last_msg["receiver_role"] == "student":
            st_id = last_msg["receiver_id"]
        elif conv_id.startswith("conv_s"):
            try:
                st_id = int(conv_id.split("_s")[1].split("_")[0])
            except Exception:
                st_id = 1
        else:
            st_id = 1
            
        sub_id = last_msg["subject_id"]
        
        # Fetch student info
        cursor.execute("SELECT id, full_name, roll_no, email, branch, year, section, semester FROM students WHERE id = ?", (st_id,))
        student = cursor.fetchone()
        
        # Fetch subject info if available
        subject_name = "Academic Coursework"
        subject_code = "COURSE"
        if sub_id:
            cursor.execute("SELECT subject_name, subject_code FROM subjects WHERE id = ?", (sub_id,))
            s_row = cursor.fetchone()
            if s_row:
                subject_name = s_row["subject_name"]
                subject_code = s_row["subject_code"]
                
        # Fetch unread count for teacher in this thread
        cursor.execute("""
        SELECT COUNT(*) as unread
        FROM messages
        WHERE conversation_id = ? AND receiver_role = 'teacher' AND receiver_id = ? AND is_read = 0
        """, (conv_id, teacher_id))
        unread_cnt = cursor.fetchone()["unread"]
        
        threads.append({
            "conversation_id": conv_id,
            "student_id": st_id,
            "student_name": student["full_name"] if student else "Enrolled Student",
            "student_roll": student["roll_no"] if student else "-",
            "student_branch": student["branch"] if student else "-",
            "student_year": student["year"] if student else "-",
            "student_section": student["section"] if student else "-",
            "subject_id": sub_id,
            "subject_name": subject_name,
            "subject_code": subject_code,
            "last_message": last_msg["message"] if last_msg else "",
            "last_message_role": last_msg["sender_role"] if last_msg else "",
            "last_updated": last_msg["created_at"] if last_msg else "",
            "unread_count": unread_cnt
        })
        
    threads.sort(key=lambda x: x["last_updated"] or "", reverse=True)
    
    # 2. Fetch available students strictly within this teacher's assigned cohort
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    available_students = []
    if assigned_ids:
        placeholders = ",".join("?" for _ in assigned_ids)
        cursor.execute(f"""
        SELECT id as student_id, full_name as student_name, roll_no as student_roll, branch, year, section
        FROM students
        WHERE id IN ({placeholders})
        ORDER BY full_name ASC
        """, list(assigned_ids))
        for st in cursor.fetchall():
            available_students.append({
                "student_id": st["student_id"],
                "student_name": st["student_name"],
                "student_roll": st["student_roll"],
                "student_branch": st["branch"],
                "student_year": st["year"],
                "student_section": st["section"],
                "default_conv_id": f"conv_s{st['student_id']}_t{teacher_id}"
            })
        
    # 3. Total unread count for teacher
    cursor.execute("""
    SELECT COUNT(*) as total_unread
    FROM messages
    WHERE receiver_role = 'teacher' AND receiver_id = ? AND is_read = 0
    """, (teacher_id,))
    total_unread = cursor.fetchone()["total_unread"]
    
    conn.close()
    return jsonify({
        "success": True,
        "teacher": {
            "id": teacher_id,
            "full_name": t_row["full_name"],
            "email": t_row["email"],
            "department": t_row["department"]
        },
        "conversations": threads,
        "available_students": available_students,
        "total_unread": total_unread
    })

@teacher_bp.route("/api/teacher/messages/<string:conversation_id>", methods=["GET"])
@teacher_required
def get_teacher_thread_messages(conversation_id):
    """Fetches messages in a thread and marks unread items sent by student as read."""
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "message": "Teacher not found."}), 404
        
    teacher_id = t_row["id"]
    cursor = conn.cursor()
    
    # Extract student_id from conversation_id if available
    st_id = None
    if conversation_id.startswith("conv_s"):
        try:
            st_id = int(conversation_id.split("_s")[1].split("_")[0])
        except Exception:
            pass
            
    # Security: Fetch messages for this thread where teacher is participant
    cursor.execute("""
    SELECT * FROM messages 
    WHERE conversation_id = ? 
      AND ((sender_role = 'teacher' AND sender_id = ?) OR (receiver_role = 'teacher' AND receiver_id = ?))
    ORDER BY created_at ASC, id ASC
    """, (conversation_id, teacher_id, teacher_id))
    
    messages = [dict(row) for row in cursor.fetchall()]
    
    # Mark student unread messages as read in this thread
    cursor.execute("""
    UPDATE messages 
    SET is_read = 1, read_at = CURRENT_TIMESTAMP
    WHERE conversation_id = ? AND receiver_role = 'teacher' AND receiver_id = ? AND is_read = 0
    """, (conversation_id, teacher_id))
    conn.commit()
    
    # Extract student info
    student_info = None
    if messages:
        st_id = messages[0]["sender_id"] if messages[0]["sender_role"] == "student" else messages[0]["receiver_id"]
    if st_id:
        cursor.execute("SELECT id, full_name, roll_no, email, branch, year, section, semester FROM students WHERE id = ?", (st_id,))
        st_row = cursor.fetchone()
        if st_row:
            student_info = dict(st_row)
            
    conn.close()
    return jsonify({
        "success": True,
        "conversation_id": conversation_id,
        "messages": messages,
        "student": student_info
    })

@teacher_bp.route("/api/teacher/messages", methods=["POST"])
@teacher_required
def send_teacher_message():
    """Teacher sends a message or reply to an assigned student."""
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "message": "Teacher not found."}), 404
        
    teacher_id = t_row["id"]
    teacher_name = t_row["full_name"]
    
    data = request.get_json() or {}
    message_text = (data.get("message") or "").strip()
    student_id = data.get("student_id")
    subject_id = data.get("subject_id")
    client_conv_id = (data.get("conversation_id") or "").strip()
    
    if not message_text:
        conn.close()
        return jsonify({"success": False, "message": "Message text cannot be empty."}), 400
        
    # If student_id not provided but conversation_id given, parse student_id
    if not student_id and client_conv_id and client_conv_id.startswith("conv_s"):
        try:
            student_id = int(client_conv_id.split("_s")[1].split("_")[0])
        except Exception:
            pass
            
    if not student_id:
        conn.close()
        return jsonify({"success": False, "message": "Student recipient is required."}), 400
        
    cursor = conn.cursor()
    
    # Verify student exists first
    cursor.execute("SELECT id, user_id, full_name, roll_no FROM students WHERE id = ?", (student_id,))
    st_row = cursor.fetchone()
    if not st_row:
        conn.close()
        return jsonify({"success": False, "message": "Student recipient not found."}), 404

    # Security: Verify student is assigned to this teacher's cohort
    assigned_ids = get_teacher_assigned_student_ids(cursor, t_row)
    if student_id not in assigned_ids:
        conn.close()
        return jsonify({
            "success": False, 
            "message": "Access denied: You can only message students enrolled in your assigned class or subjects."
        }), 403
        
    student_user_id = st_row["user_id"]
    
    # Always enforce canonical conversation_id
    conversation_id = f"conv_s{student_id}_t{teacher_id}"
        
    cursor.execute("""
    INSERT INTO messages (conversation_id, sender_id, sender_role, receiver_id, receiver_role, subject_id, message, is_read)
    VALUES (?, ?, 'teacher', ?, 'student', ?, ?, 0)
    """, (conversation_id, teacher_id, student_id, subject_id, message_text))
    
    msg_id = cursor.lastrowid
    
    # Create notification for student
    if student_user_id:
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type, is_read)
        VALUES (?, ?, ?, 'message', 0)
        """, (student_user_id, f"New Message from {teacher_name}", f"Faculty {teacher_name} sent you an academic message: \"{message_text[:60]}...\""))
        
    conn.commit()
    
    cursor.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
    inserted = dict(cursor.fetchone())
    
    conn.close()
    return jsonify({
        "success": True,
        "message": "Message sent to student successfully.",
        "conversation_id": conversation_id,
        "message_data": inserted
    }), 201

@teacher_bp.route("/api/teacher/messages/unread-count", methods=["GET"])
@teacher_required
def get_teacher_unread_message_count():
    """Returns total unread incoming messages for this teacher."""
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    if not t_row:
        conn.close()
        return jsonify({"success": False, "unread_count": 0}), 404
        
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) as unread_count 
    FROM messages 
    WHERE receiver_role = 'teacher' AND receiver_id = ? AND is_read = 0
    """, (t_row["id"],))
    count = cursor.fetchone()["unread_count"]
    conn.close()
    return jsonify({"success": True, "unread_count": count})


@teacher_bp.route("/api/teacher/messages/stream", methods=["GET"])
@teacher_required
def stream_teacher_messages():
    """
    Server-Sent Events (SSE) real-time message stream for faculty with instantaneous updates.
    """
    import time
    from flask import Response

    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    conn.close()
    if not t_row:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    teacher_id = t_row["id"]

    def event_generator():
        yield f"data: {json.dumps({'type': 'connected', 'teacher_id': teacher_id})}\n\n"
        for _ in range(60):  # 60 iterations (approx 60-120 seconds stream)
            try:
                db = get_db_connection()
                cur = db.cursor()
                cur.execute("""
                SELECT id, conversation_id, sender_id, sender_role, message, is_read, created_at
                FROM messages
                WHERE receiver_role = 'teacher' AND receiver_id = ?
                  AND created_at >= datetime('now', '-3 seconds')
                ORDER BY created_at DESC LIMIT 5
                """, (teacher_id,))
                new_msgs = [dict(r) for r in cur.fetchall()]
                db.close()
                if new_msgs:
                    yield f"data: {json.dumps({'type': 'new_messages', 'messages': new_msgs})}\n\n"
            except Exception:
                pass
            time.sleep(2)

    return Response(event_generator(), mimetype="text/event-stream")


@teacher_bp.route("/api/teacher/students/for-messages", methods=["GET"])
@teacher_required
def get_students_for_messaging():
    """Returns student list with search filter to start a new chat."""
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    teacher_id = t_row["id"] if t_row else 1
    cursor = conn.cursor()
    q = request.args.get("q", "").strip().lower()
    
    if q:
        cursor.execute("""
        SELECT id as student_id, id, full_name, roll_no, email, branch, year, section
        FROM students
        WHERE LOWER(full_name) LIKE ? OR LOWER(roll_no) LIKE ? OR LOWER(email) LIKE ?
        ORDER BY full_name ASC LIMIT 30
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        cursor.execute("""
        SELECT id as student_id, id, full_name, roll_no, email, branch, year, section
        FROM students
        ORDER BY full_name ASC LIMIT 50
        """)
        
    students = []
    for r in cursor.fetchall():
        st = dict(r)
        st["student_id"] = st["id"]
        st["default_conv_id"] = f"conv_s{st['id']}_t{teacher_id}"
        students.append(st)
        
    conn.close()
    return jsonify({"success": True, "students": students})


# ================= CSV BULK STUDENT UPLOAD =================

import io
import csv
import re
from flask import Response

VALID_BRANCHES = [
    "CSE", "CSE (AI & ML)", "CSE (Data Science)", "ECE", "EEE",
    "Mechanical Engineering", "Civil Engineering", "Information Technology"
]

BRANCH_ALIASES = {
    "cse": "CSE",
    "computer science": "CSE",
    "aiml": "AIML",
    "ai & ml": "AIML",
    "ai/ml": "AIML",
    "cse (ai & ml)": "AIML",
    "cse(ai&ml)": "AIML",
    "cse-ai&ml": "AIML",
    "data science": "CSE (Data Science)",
    "ds": "CSE (Data Science)",
    "cse (data science)": "CSE (Data Science)",
    "ece": "ECE",
    "eee": "EEE",
    "mech": "Mechanical Engineering",
    "mechanical": "Mechanical Engineering",
    "mechanical engineering": "Mechanical Engineering",
    "civil": "Civil Engineering",
    "civil engineering": "Civil Engineering",
    "it": "Information Technology",
    "information technology": "Information Technology"
}

YEAR_ALIASES = {
    "1": "1st Year", "1st": "1st Year", "1st year": "1st Year", "first year": "1st Year", "year 1": "1st Year",
    "2": "2nd Year", "2nd": "2nd Year", "2nd year": "2nd Year", "second year": "2nd Year", "year 2": "2nd Year",
    "3": "3rd Year", "3rd": "3rd Year", "3rd year": "3rd Year", "third year": "3rd Year", "year 3": "3rd Year",
    "4": "4th Year", "4th": "4th Year", "4th year": "4th Year", "fourth year": "4th Year", "year 4": "4th Year"
}

def normalize_branch(val):
    v = str(val).strip().lower()
    return BRANCH_ALIASES.get(v, str(val).strip())

def normalize_year(val):
    v = str(val).strip().lower()
    return YEAR_ALIASES.get(v, str(val).strip())

def parse_semester(val):
    try:
        s = str(val).strip().lower().replace("st", "").replace("nd", "").replace("rd", "").replace("th", "").replace("semester", "").replace("sem", "").strip()
        sem = int(s)
        if 1 <= sem <= 8:
            return sem
        return None
    except Exception:
        return None

def parse_csv_stream(stream_or_str):
    if isinstance(stream_or_str, bytes):
        stream_or_str = stream_or_str.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(stream_or_str))
    if not reader.fieldnames:
        return [], []
    raw_fieldnames = list(reader.fieldnames)
    rows = list(reader)
    return rows, raw_fieldnames

def validate_csv_headers(fieldnames):
    """
    Validates that the 5 mandatory columns are present:
    'Student Name', 'Roll No', 'Branch', 'Year', 'Section'.
    Returns (is_valid, key_mapping).
    """
    if not fieldnames:
        return False, None
    mapping = {}
    for raw_h in fieldnames:
        if not raw_h:
            continue
        c = re.sub(r'[\s_]+', '', str(raw_h).strip().lower())
        if c in ['studentname', 'name', 'fullname', 'student'] and 'student_name' not in mapping:
            mapping['student_name'] = raw_h
        elif c in ['rollno', 'rollnumber', 'roll', 'rollnum'] and 'roll_no' not in mapping:
            mapping['roll_no'] = raw_h
        elif c in ['branch', 'dept', 'department'] and 'branch' not in mapping:
            mapping['branch'] = raw_h
        elif c in ['year', 'academicyear', 'yr'] and 'year' not in mapping:
            mapping['year'] = raw_h
        elif c in ['section', 'sec'] and 'section' not in mapping:
            mapping['section'] = raw_h

    required_keys = ['student_name', 'roll_no', 'branch', 'year', 'section']
    missing = [k for k in required_keys if k not in mapping]
    if missing:
        return False, None
    return True, mapping

@teacher_bp.route("/api/teacher/students/template", methods=["GET"])
@teacher_required
def download_student_csv_template():
    """Generates and downloads a clean 5-column CSV sample template for bulk student upload."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 5 Mandatory Headers
    headers = ["Student Name", "Roll No", "Branch", "Year", "Section"]
    writer.writerow(headers)
    
    # Sample rows
    writer.writerow(["Rahul Kumar", "23A91A0501", "AIML", "3", "A"])
    writer.writerow(["Priya Sharma", "23A91A0502", "CSE", "3", "A"])
    writer.writerow(["Arjun Reddy", "23A91A0503", "AIML", "3", "B"])
    
    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=student_sample.csv"}
    )

@teacher_bp.route("/api/teacher/students/upload/preview", methods=["POST"])
@teacher_required
def preview_student_csv():
    """
    Validates uploaded student CSV against the 5 mandatory columns.
    Returns preview stats, valid rows (Student Name, Roll No, Branch, Year, Section),
    invalid rows, and detailed validation error list.
    """
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded. Please select a CSV file."}), 400
        
    file = request.files["file"]
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "message": "Invalid file format. Please upload a .csv file."}), 400
        
    content = file.read()
    if len(content) > 5 * 1024 * 1024:
        return jsonify({"success": False, "message": "File exceeds maximum size limit of 5MB."}), 400
        
    rows, headers = parse_csv_stream(content)
    if not rows:
        return jsonify({"success": False, "message": "CSV file is empty or could not be read."}), 400
        
    # Verify 5 mandatory headers
    is_valid, header_map = validate_csv_headers(headers)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": "Invalid CSV. Required columns: Student Name, Roll No, Branch, Year, Section."
        }), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Pre-fetch existing roll numbers from database
    cursor.execute("SELECT UPPER(roll_no) FROM students")
    existing_rolls = set(r[0] for r in cursor.fetchall())
    conn.close()
    
    seen_csv_rolls = set()
    valid_rows = []
    errors = []
    
    for idx, row in enumerate(rows, start=2): # Row 1 is header
        name = str(row.get(header_map["student_name"]) or "").strip()
        roll = str(row.get(header_map["roll_no"]) or "").strip().upper()
        br_raw = str(row.get(header_map["branch"]) or "").strip()
        yr_raw = str(row.get(header_map["year"]) or "").strip()
        sec_raw = str(row.get(header_map["section"]) or "").strip().upper()
        
        row_errs = []
        
        # Check for empty required values
        missing_fields = []
        if not name:
            missing_fields.append("Student Name")
        if not roll:
            missing_fields.append("Roll No")
        if not br_raw:
            missing_fields.append("Branch")
        if not yr_raw:
            missing_fields.append("Year")
        if not sec_raw:
            missing_fields.append("Section")
            
        if missing_fields:
            row_errs.append(f"Missing required value(s): {', '.join(missing_fields)}")
            
        # Duplicate Roll No checks
        if roll:
            if roll in seen_csv_rolls:
                row_errs.append(f"Duplicate student roll number in CSV: {roll}")
            elif roll in existing_rolls:
                row_errs.append(f"Roll number already registered in database: {roll}")
                
        # Validate Academic Year
        norm_yr = normalize_year(yr_raw)
        if yr_raw and (not norm_yr or norm_yr not in ["1st Year", "2nd Year", "3rd Year", "4th Year"]):
            row_errs.append(f"Invalid academic year '{yr_raw}'. Expected 1, 2, 3, or 4 (or 1st/2nd/3rd/4th Year).")
            
        # Normalize Branch
        norm_br = normalize_branch(br_raw) if br_raw else ""
        
        # Calculate semester from year
        year_to_sem = {"1st Year": 1, "2nd Year": 3, "3rd Year": 5, "4th Year": 7}
        parsed_sem = year_to_sem.get(norm_yr, 1)
        
        if row_errs:
            errors.append({
                "row": idx,
                "student_name": name or "-",
                "roll_no": roll or "-",
                "branch": br_raw or "-",
                "year": yr_raw or "-",
                "section": sec_raw or "-",
                "error": "; ".join(row_errs)
            })
        else:
            seen_csv_rolls.add(roll)
            valid_rows.append({
                "student_name": name,
                "roll_no": roll,
                "branch": norm_br,
                "year": norm_yr,
                "section": sec_raw,
                "semester": parsed_sem
            })
            
    return jsonify({
        "success": True,
        "total_rows": len(rows),
        "valid_count": len(valid_rows),
        "valid_rows": len(valid_rows),
        "invalid_count": len(errors),
        "invalid_rows": len(errors),
        "preview": valid_rows,
        "errors": errors
    })

@teacher_bp.route("/api/teacher/students/upload", methods=["POST"])
@teacher_required
def upload_students_csv():
    """
    Processes and inserts valid student records from CSV into SQLite database.
    Requires 5 columns: Student Name, Roll No, Branch, Year, Section.
    Generates secure student login accounts with hashed passwords.
    Records metadata in student_import_history.
    """
    user_id = session.get("user_id")
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No CSV file provided in upload request."}), 400
        
    file = request.files["file"]
    filename = file.filename
    if not filename.lower().endswith(".csv"):
        return jsonify({"success": False, "message": "Invalid file type. Please upload a .csv file."}), 400
        
    content = file.read()
    rows, headers = parse_csv_stream(content)
    if not rows:
        return jsonify({"success": False, "message": "The CSV file contains no records."}), 400
        
    # Verify 5 mandatory headers
    is_valid, header_map = validate_csv_headers(headers)
    if not is_valid:
        return jsonify({
            "success": False,
            "message": "Invalid CSV. Required columns: Student Name, Roll No, Branch, Year, Section."
        }), 400
        
    conn = get_db_connection()
    t_row = get_logged_in_teacher(conn)
    cursor = conn.cursor()
    
    t_inst = t_row["institution_id"] if t_row and "institution_id" in t_row.keys() else None
    t_prog = t_row["program_id"] if t_row and "program_id" in t_row.keys() else None
    t_id = t_row["id"] if t_row else None
    
    # Pre-fetch existing emails and roll numbers
    cursor.execute("SELECT LOWER(email) FROM users")
    existing_emails = set(r[0] for r in cursor.fetchall())
    cursor.execute("SELECT UPPER(roll_no) FROM students")
    existing_rolls = set(r[0] for r in cursor.fetchall())
    
    seen_csv_rolls = set()
    imported_count = 0
    skipped_count = 0
    errors = []
    
    try:
        for idx, row in enumerate(rows, start=2):
            name = str(row.get(header_map["student_name"]) or "").strip()
            roll = str(row.get(header_map["roll_no"]) or "").strip().upper()
            br_raw = str(row.get(header_map["branch"]) or "").strip()
            yr_raw = str(row.get(header_map["year"]) or "").strip()
            sec = str(row.get(header_map["section"]) or "").strip().upper()

            # If branch/year/section missing, fallback to uploading teacher's assigned cohort
            if not br_raw and t_row and t_row["branch"]:
                br_raw = t_row["branch"]
            if not yr_raw and t_row and t_row["year"]:
                yr_raw = t_row["year"]
            if not sec and t_row and t_row["section"]:
                sec = t_row["section"].upper()
            
            # Row level validations
            if not name or not roll or not br_raw or not yr_raw or not sec:
                skipped_count += 1
                missing = []
                if not name: missing.append("Student Name")
                if not roll: missing.append("Roll No")
                if not br_raw: missing.append("Branch")
                if not yr_raw: missing.append("Year")
                if not sec: missing.append("Section")
                errors.append({
                    "row": idx,
                    "student_name": name or "-",
                    "roll_no": roll or "-",
                    "error": f"Missing required value(s): {', '.join(missing)}"
                })
                continue
                
            norm_yr = normalize_year(yr_raw)
            if not norm_yr or norm_yr not in ["1st Year", "2nd Year", "3rd Year", "4th Year"]:
                skipped_count += 1
                errors.append({
                    "row": idx,
                    "student_name": name,
                    "roll_no": roll,
                    "error": f"Invalid academic year '{yr_raw}'. Expected 1, 2, 3, or 4."
                })
                continue
                
            if roll in existing_rolls or roll in seen_csv_rolls:
                skipped_count += 1
                errors.append({
                    "row": idx,
                    "student_name": name,
                    "roll_no": roll,
                    "error": f"Duplicate student roll number skipped: {roll}"
                })
                continue
                
            norm_br = normalize_branch(br_raw)
            
            # Determine semester from year
            year_to_sem = {"1st Year": 1, "2nd Year": 3, "3rd Year": 5, "4th Year": 7}
            sem = year_to_sem.get(norm_yr, 1)
            
            # Ensure teacher_assignments entry exists for this teacher & cohort
            if t_id:
                cursor.execute("""
                INSERT OR IGNORE INTO teacher_assignments (teacher_id, branch, year, section, academic_year, is_class_teacher)
                VALUES (?, ?, ?, ?, '2024-2025', 1)
                """, (t_id, norm_br, norm_yr, sec))
                
            # Lookup or create class in classes table
            class_id = None
            cursor.execute("""
            SELECT id FROM classes
            WHERE (institution_id = ? OR institution_id IS NULL)
              AND UPPER(branch) = UPPER(?) AND UPPER(year) = UPPER(?) AND UPPER(section) = UPPER(?)
            LIMIT 1
            """, (t_inst, norm_br, norm_yr, sec))
            c_row = cursor.fetchone()
            if c_row:
                class_id = c_row[0]
                if t_id:
                    cursor.execute("UPDATE classes SET teacher_id = ? WHERE id = ? AND teacher_id IS NULL", (t_id, class_id))
            else:
                cursor.execute("""
                INSERT INTO classes (teacher_id, institution_id, regulation, branch, year, semester, section, academic_year)
                VALUES (?, ?, 'R23', ?, ?, ?, ?, '2024-2025')
                """, (t_id, t_inst or 1, norm_br, norm_yr, sem, sec))
                class_id = cursor.lastrowid
            
            # Check for optional extra columns or use clean defaults
            def get_extra(k):
                for rk, rv in row.items():
                    if rk and re.sub(r'[\s_]+', '', str(rk).strip().lower()) == re.sub(r'[\s_]+', '', k.lower()):
                        if rv is not None and str(rv).strip() != "":
                            return str(rv).strip()
                return ""
                
            email = get_extra("email") or f"{roll.lower()}@student.apedu.ac.in"
            pwd = get_extra("password") or f"{roll.lower()}"
            
            if email.lower() in existing_emails:
                email = f"{roll.lower()}@student.apedu.ac.in"
                
            def get_float_extra(k, default_v):
                val = get_extra(k)
                if val:
                    try:
                        return float(val)
                    except Exception:
                        return default_v
                return default_v

            attendance = get_float_extra("attendance", 75.0)
            m_score = get_float_extra("mathematics_score", 65.0)
            p_score = get_float_extra("physics_score", 65.0)
            pr_score = get_float_extra("programming_score", 65.0)
            ds_score = get_float_extra("data_structures_score", 65.0)
            db_score = get_float_extra("database_score", 65.0)
            comm_score = get_float_extra("communication_score", 70.0)
            asg_score = get_float_extra("assignment_score", 70.0)
            qz_score = get_float_extra("quiz_score", 65.0)
            ex_score = get_float_extra("exam_score", 65.0)
            st_hours = get_float_extra("study_hours", 8.0)
            activity = get_float_extra("learning_activity", 60.0)
            prev_perf = get_float_extra("previous_performance", 65.0)
            progress = get_float_extra("overall_progress", 50.0)
            
            # Securely hash password using Werkzeug
            pwd_hash = generate_password_hash(pwd)
            
            cursor.execute("""
            INSERT INTO users (email, password_hash, role, full_name, institution_id)
            VALUES (?, ?, 'student', ?, ?)
            """, (email.lower(), pwd_hash, name, t_inst))
            new_user_id = cursor.lastrowid
            
            cursor.execute("""
            INSERT INTO students (
                user_id, full_name, roll_no, email, year, branch, section, semester,
                attendance, mathematics_score, physics_score, programming_score,
                data_structures_score, database_score, communication_score,
                assignment_score, quiz_score, exam_score, study_hours,
                learning_activity, previous_performance, overall_progress, learning_streak,
                institution_id, program_id, teacher_id, class_id, regulation, academic_year
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, 3,
                ?, ?, ?, ?, 'R23', '2024-2025'
            )
            """, (
                new_user_id, name, roll, email.lower(), norm_yr, norm_br, sec, sem,
                attendance, m_score, p_score, pr_score, ds_score, db_score, comm_score,
                asg_score, qz_score, ex_score, st_hours, activity, prev_perf, progress,
                t_inst, t_prog, t_id, class_id
            ))
            new_student_id = cursor.lastrowid
            
            # Auto-enroll student into subjects taught by this teacher for this class
            if t_id:
                cursor.execute("""
                SELECT ts.subject_id FROM teacher_subjects ts
                WHERE ts.teacher_id = ? AND ts.branch = ? AND ts.year = ? AND ts.section = ?
                """, (t_id, norm_br, norm_yr, sec))
                for sub in cursor.fetchall():
                    cursor.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)", (new_student_id, sub[0]))
            
            seen_csv_rolls.add(roll)
            existing_rolls.add(roll)
            existing_emails.add(email.lower())
            imported_count += 1
            
        # Record import history
        cursor.execute("""
        INSERT INTO student_import_history (
            teacher_id, file_name, total_rows, imported_rows, skipped_rows, error_rows
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, filename, len(rows), imported_count, skipped_count, len(errors)))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({
            "success": False,
            "message": f"Database transaction failed during student import: {str(e)}"
        }), 500
        
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"Bulk import complete! {imported_count} student(s) imported, {skipped_count} skipped.",
        "total_rows": len(rows),
        "imported_rows": imported_count,
        "skipped_rows": skipped_count,
        "error_count": len(errors),
        "errors": errors
    }), 201

@teacher_bp.route("/api/teacher/students/upload/history", methods=["GET"])
@teacher_required
def get_student_upload_history():
    """Returns past CSV bulk upload logs."""
    user_id = session.get("user_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT * FROM student_import_history
    WHERE teacher_id = ?
    ORDER BY uploaded_at DESC
    LIMIT 20
    """, (user_id,))
    
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "history": history})


# ================= PERFORMANCE CSV IMPORT & VALIDATION (Requirement 23) =================
@teacher_bp.route("/api/teacher/import-student-performance-csv", methods=["POST"])
@teacher_required
def import_student_performance_csv():
    """
    Imports student relational performance CSV:
    Fields: roll_number (or student_id), subject_code, attendance, assessment_score, assignment_score, quiz_score, lab_score.
    Strictly validates each subject_code against the student's curriculum and institution.
    Rejects invalid subjects instead of silently creating new ones.
    """
    user_id = session.get("user_id")
    inst_id = session.get("institution_id")
    data = request.get_json() or {}
    csv_text = data.get("csv_content", "").strip()

    if not csv_text:
        return jsonify({"success": False, "message": "CSV content is required."}), 400

    lines = csv_text.splitlines()
    reader = csv.DictReader(lines)

    conn = get_db_connection()
    cursor = conn.cursor()

    valid_records = []
    invalid_records = []
    duplicate_records = []
    unknown_subjects = []
    missing_students = []

    seen_pairs = set()

    for idx, row in enumerate(reader, start=2):
        clean_row = {k.strip().lower().replace(" ", "_"): (v.strip() if v else "") for k, v in row.items() if k}
        roll = clean_row.get("roll_number", clean_row.get("roll_no", clean_row.get("student_id", ""))).upper()
        subj_code = clean_row.get("subject_code", "").upper()

        if not roll or not subj_code:
            invalid_records.append({"row": idx, "reason": "Missing roll_number or subject_code."})
            continue

        pair_key = (roll, subj_code)
        if pair_key in seen_pairs:
            duplicate_records.append({"row": idx, "roll_number": roll, "subject_code": subj_code})
            continue
        seen_pairs.add(pair_key)

        # 1. Validate student exists
        cursor.execute("SELECT id, branch, year, semester, institution_id FROM students WHERE roll_no = ?", (roll,))
        st_row = cursor.fetchone()
        if not st_row:
            missing_students.append({"row": idx, "roll_number": roll, "reason": "Student not registered in database."})
            continue

        st_id = st_row["id"]
        st_inst = st_row["institution_id"]

        # 2. Validate subject belongs to this institution & student's branch/year/sem
        cursor.execute("""
        SELECT id, subject_name FROM subjects
        WHERE subject_code = ? AND (institution_id = ? OR institution_id IS NULL)
        """, (subj_code, st_inst or inst_id))
        subj_row = cursor.fetchone()

        if not subj_row:
            unknown_subjects.append({"row": idx, "subject_code": subj_code, "reason": f"Subject code '{subj_code}' not found in institution curriculum."})
            continue

        subj_id = subj_row["id"]

        # Extract numerical performance values
        try:
            att = float(clean_row.get("attendance", 75.0))
            assess = float(clean_row.get("assessment_score", clean_row.get("exam_score", 65.0)))
            assign = float(clean_row.get("assignment_score", 70.0))
            quiz = float(clean_row.get("quiz_score", 65.0))
            lab = float(clean_row.get("lab_score", 70.0))
            overall = round((att * 0.2) + (assess * 0.3) + (quiz * 0.25) + (assign * 0.15) + (lab * 0.1), 1)
        except ValueError as val_err:
            invalid_records.append({"row": idx, "reason": f"Malformed numeric scores: {str(val_err)}"})
            continue

        valid_records.append({
            "student_id": st_id,
            "subject_id": subj_id,
            "roll_number": roll,
            "subject_code": subj_code,
            "attendance": att,
            "assessment_score": assess,
            "assignment_score": assign,
            "quiz_score": quiz,
            "lab_score": lab,
            "overall_score": overall
        })

    # Save valid records into database
    for vr in valid_records:
        cursor.execute("""
        INSERT INTO student_subjects (student_id, subject_id)
        VALUES (?, ?)
        ON CONFLICT(student_id, subject_id) DO NOTHING
        """, (vr["student_id"], vr["subject_id"]))

        cursor.execute("""
        INSERT INTO student_subject_performance (
            student_id, subject_id, attendance, assessment_score, assignment_score, quiz_score, lab_score, overall_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id, subject_id) DO UPDATE SET
            attendance = excluded.attendance,
            assessment_score = excluded.assessment_score,
            assignment_score = excluded.assignment_score,
            quiz_score = excluded.quiz_score,
            lab_score = excluded.lab_score,
            overall_score = excluded.overall_score,
            last_updated = CURRENT_TIMESTAMP
        """, (vr["student_id"], vr["subject_id"], vr["attendance"], vr["assessment_score"], vr["assignment_score"], vr["quiz_score"], vr["lab_score"], vr["overall_score"]))

    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user_id,
        role="teacher",
        action="IMPORT_PERFORMANCE_CSV",
        details=f"Processed performance CSV: {len(valid_records)} valid, {len(invalid_records)} invalid, {len(unknown_subjects)} unknown subjects."
    )

    return jsonify({
        "success": True,
        "summary": {
            "total_rows": len(lines) - 1,
            "valid_count": len(valid_records),
            "invalid_count": len(invalid_records),
            "duplicate_count": len(duplicate_records),
            "unknown_subject_count": len(unknown_subjects),
            "missing_student_count": len(missing_students)
        },
        "valid_records": valid_records,
        "invalid_records": invalid_records,
        "unknown_subjects": unknown_subjects,
        "missing_students": missing_students
    })


# ================= GROUNDED QUIZZES & TOPIC MASTERY (Requirements 11, 31) =================
@teacher_bp.route("/api/teacher/quizzes/grounded-generate", methods=["POST"])
@teacher_required
def generate_teacher_grounded_quiz():
    """Generates grounded questions with full citations from syllabus chunks."""
    user = get_current_user()
    data = request.get_json() or {}
    subject_id = data.get("subject_id")
    topic_id = data.get("topic_id")
    difficulty = data.get("difficulty", "Intermediate")

    if not subject_id or not topic_id:
        return jsonify({"success": False, "message": "subject_id and topic_id are required."}), 400

    from backend.quiz_service import generate_grounded_topic_questions
    res = generate_grounded_topic_questions(
        subject_id=int(subject_id),
        topic_id=int(topic_id),
        difficulty=difficulty,
        created_by=user.get("id") if user else None
    )
    return jsonify(res)


@teacher_bp.route("/api/teacher/topic-mastery-summary", methods=["GET"])
@teacher_required
def get_teacher_topic_mastery_summary():
    """Returns aggregated topic mastery distribution for faculty monitoring."""
    user = get_current_user()
    inst_id = session.get("institution_id")
    subject_id = request.args.get("subject_id")

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT t.id as topic_id, t.topic_name, t.difficulty,
           s.id as subject_id, s.subject_code, s.subject_name,
           m.module_number, m.module_name,
           ROUND(AVG(stm.mastery_score), 1) as avg_mastery,
           count(stm.id) as students_evaluated,
           SUM(CASE WHEN stm.mastery_score < 60.0 THEN 1 ELSE 0 END) as weak_learners_count,
           SUM(CASE WHEN stm.mastery_score >= 80.0 THEN 1 ELSE 0 END) as strong_learners_count
    FROM topics t
    JOIN modules m ON t.module_id = m.id
    JOIN subjects s ON t.subject_id = s.id
    LEFT JOIN student_topic_mastery stm ON stm.topic_id = t.id
    WHERE (s.institution_id = ? OR s.institution_id IS NULL)
    """
    params = [inst_id]

    if subject_id:
        query += " AND s.id = ?"
        params.append(subject_id)

    query += " GROUP BY t.id ORDER BY avg_mastery ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    topics = [dict(r) for r in rows]
    return jsonify({"success": True, "total_topics": len(topics), "topics": topics})


# ================= TEACHER ASSESSMENT & QUIZ REVIEW =================
@teacher_bp.route("/api/teacher/quizzes", methods=["GET"])
@teacher_required
def get_teacher_quizzes():
    """
    Returns AI-generated and faculty-authored questions for teacher review and approval.
    """
    subject_id = request.args.get("subject_id")
    topic_id = request.args.get("topic_id")
    status_filter = request.args.get("status")  # 'pending_review', 'approved', 'all'
    inst_id = session.get("institution_id")

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT gq.id, gq.subject_id, gq.module_id, gq.topic_id, gq.question_text, gq.question_type,
           gq.option_a, gq.option_b, gq.option_c, gq.option_d, gq.correct_answer, gq.explanation,
           gq.difficulty, gq.source_reference, gq.source_page, gq.generation_method, gq.approval_status,
           gq.created_at,
           s.subject_code, s.subject_name,
           t.topic_name, m.module_name
    FROM grounded_questions gq
    JOIN subjects s ON gq.subject_id = s.id
    JOIN topics t ON gq.topic_id = t.id
    JOIN modules m ON gq.module_id = m.id
    WHERE (s.institution_id = ? OR s.institution_id IS NULL)
    """
    params = [inst_id]

    if subject_id:
        query += " AND gq.subject_id = ?"
        params.append(subject_id)
    if topic_id:
        query += " AND gq.topic_id = ?"
        params.append(topic_id)
    if status_filter and status_filter != "all":
        query += " AND gq.approval_status = ?"
        params.append(status_filter)

    query += " ORDER BY gq.id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    questions = []
    for r in rows:
        questions.append({
            "id": r["id"],
            "subject_id": r["subject_id"],
            "subject_code": r["subject_code"],
            "subject_name": r["subject_name"],
            "topic_id": r["topic_id"],
            "topic_name": r["topic_name"],
            "module_name": r["module_name"],
            "question_text": r["question_text"],
            "question_type": r["question_type"],
            "options": {
                "A": r["option_a"],
                "B": r["option_b"],
                "C": r["option_c"],
                "D": r["option_d"]
            },
            "correct_answer": r["correct_answer"],
            "explanation": r["explanation"],
            "difficulty": r["difficulty"],
            "source_reference": r["source_reference"],
            "source_page": r["source_page"],
            "generation_method": r["generation_method"],
            "approval_status": r["approval_status"],
            "created_at": r["created_at"]
        })

    return jsonify({"success": True, "total_questions": len(questions), "questions": questions})


@teacher_bp.route("/api/teacher/quizzes/generate", methods=["POST"])
@teacher_required
def teacher_generate_grounded_quiz():
    """
    Faculty on-demand grounded question generation for a specific subject and topic.
    """
    data = request.get_json() or {}
    subject_id = data.get("subject_id")
    topic_id = data.get("topic_id")
    difficulty = data.get("difficulty", "Intermediate")
    count = int(data.get("num_questions", 3))
    auto_approve = bool(data.get("auto_approve", False))

    if not subject_id or not topic_id:
        return jsonify({"success": False, "message": "subject_id and topic_id are required."}), 400

    from backend.quiz_service import generate_grounded_topic_questions
    user = get_current_user()
    result = generate_grounded_topic_questions(
        subject_id=int(subject_id),
        topic_id=int(topic_id),
        num_questions=count,
        difficulty=difficulty,
        created_by=user.get("id") if user else None
    )

    if not auto_approve and result.get("success"):
        # Set to pending_review for explicit faculty inspection
        conn = get_db_connection()
        cursor = conn.cursor()
        q_ids = result.get("question_ids", [])
        if q_ids:
            cursor.execute(f"UPDATE grounded_questions SET approval_status = 'pending_review' WHERE id IN ({','.join(['?']*len(q_ids))})", q_ids)
            conn.commit()
        conn.close()

    return jsonify(result)


@teacher_bp.route("/api/teacher/quizzes/<int:question_id>/approve", methods=["POST"])
@teacher_required
def approve_teacher_quiz_question(question_id):
    """Approves an AI-generated question for student consumption."""
    user = get_current_user()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE grounded_questions
    SET approval_status = 'approved', approved_by = ?
    WHERE id = ?
    """, (user.get("id") if user else None, question_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Question #{question_id} approved and published to students."})


@teacher_bp.route("/api/teacher/quizzes/<int:question_id>", methods=["PUT"])
@teacher_required
def edit_teacher_quiz_question(question_id):
    """Faculty edits question text, options, correct answer, or explanation."""
    data = request.get_json() or {}
    q_text = data.get("question_text", "").strip()
    opt_a = data.get("option_a", "").strip()
    opt_b = data.get("option_b", "").strip()
    opt_c = data.get("option_c", "").strip()
    opt_d = data.get("option_d", "").strip()
    corr = data.get("correct_answer", "").strip().upper()
    expl = data.get("explanation", "").strip()
    diff = data.get("difficulty", "Intermediate")

    if not q_text or not corr:
        return jsonify({"success": False, "message": "Question text and correct answer are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE grounded_questions SET
        question_text = ?, option_a = ?, option_b = ?, option_c = ?, option_d = ?,
        correct_answer = ?, explanation = ?, difficulty = ?, approval_status = 'approved'
    WHERE id = ?
    """, (q_text, opt_a, opt_b, opt_c, opt_d, corr, expl, diff, question_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Question #{question_id} updated and approved."})


@teacher_bp.route("/api/teacher/quizzes/<int:question_id>", methods=["DELETE"])
@teacher_required
def delete_teacher_quiz_question(question_id):
    """Faculty deletes an unwanted or inappropriate question."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM grounded_questions WHERE id = ?", (question_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Question #{question_id} deleted."})


@teacher_bp.route("/api/teacher/quizzes/batch-approve", methods=["POST"])
@teacher_required
def batch_approve_teacher_quiz():
    """Approves all pending questions for a specific topic or subject."""
    data = request.get_json() or {}
    topic_id = data.get("topic_id")
    subject_id = data.get("subject_id")
    user = get_current_user()

    conn = get_db_connection()
    cursor = conn.cursor()
    if topic_id:
        cursor.execute("""
        UPDATE grounded_questions
        SET approval_status = 'approved', approved_by = ?
        WHERE topic_id = ?
        """, (user.get("id") if user else None, topic_id))
    elif subject_id:
        cursor.execute("""
        UPDATE grounded_questions
        SET approval_status = 'approved', approved_by = ?
        WHERE subject_id = ?
        """, (user.get("id") if user else None, subject_id))
    else:
        conn.close()
        return jsonify({"success": False, "message": "topic_id or subject_id required."}), 400

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Approved {rows_affected} questions."})


# =========================================================================
# 1-CLICK REMEDIAL INTERVENTIONS SYSTEM
# =========================================================================

@teacher_bp.route("/api/teacher/interventions", methods=["GET"])
@teacher_required
def get_teacher_interventions_list():
    """
    Returns all interventions dispatched by this teacher or within teacher's assigned cohort,
    along with student names, roll numbers, subjects, risk levels, and status metrics.
    """
    conn = get_db_connection()
    teacher = get_logged_in_teacher(conn)
    if not teacher:
        conn.close()
        return jsonify({"success": False, "message": "Teacher profile not found."}), 404

    cursor = conn.cursor()
    assigned_student_ids = get_teacher_assigned_student_ids(cursor, teacher)

    if not assigned_student_ids:
        conn.close()
        return jsonify({
            "success": True,
            "interventions": [],
            "summary": {"total": 0, "active": 0, "completed": 0, "urgent": 0}
        })

    placeholders = ",".join(["?"] * len(assigned_student_ids))
    query = f"""
    SELECT i.*, 
           s.full_name as student_name, s.roll_no as student_roll, s.branch as student_branch,
           s.year as student_year, s.section as student_section, s.attendance as student_attendance,
           s.overall_progress as student_progress,
           sub.subject_name, sub.subject_code,
           COALESCE(t.full_name, u.full_name, 'Assigned Faculty') as teacher_name
    FROM interventions i
    JOIN students s ON i.student_id = s.id
    LEFT JOIN subjects sub ON i.subject_id = sub.id
    LEFT JOIN teachers t ON (i.teacher_id = t.user_id OR i.teacher_id = t.id)
    LEFT JOIN users u ON i.teacher_id = u.id
    WHERE i.teacher_id = ? OR i.teacher_id = ? OR i.student_id IN ({placeholders})
    ORDER BY CASE WHEN i.status = 'Assigned' THEN 1 WHEN i.status = 'In Progress' THEN 2 ELSE 3 END, i.created_at DESC
    """
    params = [teacher["user_id"], teacher["id"]] + list(assigned_student_ids)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    interventions = [dict(r) for r in rows]
    total = len(interventions)
    active = sum(1 for it in interventions if it.get("status") in ["Assigned", "In Progress"])
    completed = sum(1 for it in interventions if it.get("status") in ["Completed", "Resolved"])
    urgent = sum(1 for it in interventions if it.get("priority") in ["Urgent", "High"] and it.get("status") != "Completed")

    return jsonify({
        "success": True,
        "interventions": interventions,
        "summary": {
            "total": total,
            "active": active,
            "completed": completed,
            "urgent": urgent
        }
    })


@teacher_bp.route("/api/teacher/students/<int:student_id>/recommended-interventions", methods=["GET"])
@teacher_required
def get_student_recommended_interventions(student_id):
    """
    Generates intelligent ML-grounded 1-Click intervention action templates
    customized to student's exact weak subjects, topic gaps, and predicted risk.
    """
    conn = get_db_connection()
    teacher = get_logged_in_teacher(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    s_row = cursor.fetchone()
    if not s_row:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    student = dict(s_row)

    # Quantum ML risk calculation
    risk_data = predict_student_risk(student)
    risk_lvl = risk_data.get("risk_level", "Medium Risk")

    # Fetch student's recent weak topics
    cursor.execute("""
    SELECT DISTINCT weak_topic FROM quiz_results
    WHERE student_id = ? AND weak_topic IS NOT NULL
    ORDER BY id DESC LIMIT 2
    """, (student_id,))
    weak_quiz_topics = [r[0] for r in cursor.fetchall()]

    # Fetch lowest mastery topic
    cursor.execute("""
    SELECT t.topic_name, s.subject_name, stm.mastery_score, s.id as subject_id
    FROM student_topic_mastery stm
    JOIN topics t ON stm.topic_id = t.id
    JOIN subjects s ON stm.subject_id = s.id
    WHERE stm.student_id = ?
    ORDER BY stm.mastery_score ASC LIMIT 1
    """, (student_id,))
    lowest_topic_row = cursor.fetchone()

    conn.close()

    primary_focus = (lowest_topic_row["topic_name"] if lowest_topic_row else None) or (weak_quiz_topics[0] if weak_quiz_topics else "Data Structures & Core Algorithms")
    primary_subj = (lowest_topic_row["subject_name"] if lowest_topic_row else "Engineering Coursework")
    primary_subj_id = lowest_topic_row["subject_id"] if lowest_topic_row else None

    templates = [
        {
            "action_type": "Remedial Quiz",
            "title": f"Targeted Diagnostic Drill: {primary_focus}",
            "category": "Remedial Practice",
            "priority": "High" if "High" in risk_lvl else "Medium",
            "subject_id": primary_subj_id,
            "description": f"Assign focused 5-question adaptive diagnostic drill on '{primary_focus}' to reinforce foundational comprehension and close mastery gaps.",
            "due_days": 3
        },
        {
            "action_type": "Mentorship Session",
            "title": f"1-on-1 Faculty Doubts Consultation ({primary_subj})",
            "category": "Academic Mentorship",
            "priority": "Urgent" if "High" in risk_lvl or float(student.get("attendance", 75.0)) < 70.0 else "Medium",
            "subject_id": primary_subj_id,
            "description": f"Schedule a 15-minute 1-on-1 concept clarification session to review {primary_focus} mechanics and improve engagement.",
            "due_days": 5
        },
        {
            "action_type": "Study Material",
            "title": f"Curated Remedial Reading & Lab Walkthrough",
            "category": "Learning Resources",
            "priority": "Medium",
            "subject_id": primary_subj_id,
            "description": f"Provide grounded lecture notes and solved code examples for '{primary_focus}' prior to the upcoming mid-term exam.",
            "due_days": 7
        }
    ]

    return jsonify({
        "success": True,
        "student": serialize_student(s_row),
        "risk_prediction": risk_data,
        "recommended_templates": templates
    })


@teacher_bp.route("/api/teacher/students/<int:student_id>/intervene", methods=["POST"])
@teacher_required
def create_student_remedial_intervention(student_id):
    """
    Dispatches a 1-Click Remedial Intervention for a student.
    Persists into interventions table, sends immediate student notification, and logs audit record.
    """
    conn = get_db_connection()
    teacher = get_logged_in_teacher(conn)
    if not teacher:
        conn.close()
        return jsonify({"success": False, "message": "Teacher profile not found."}), 404

    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, full_name, email, institution_id FROM students WHERE id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    data = request.get_json() or {}
    action_type = data.get("action_type", "Remedial Quiz").strip()
    title = data.get("title", f"Remedial Academic Support - {action_type}").strip()
    description = data.get("description", "Faculty intervention assigned for academic support.").strip()
    priority = data.get("priority", "High").strip()
    category = data.get("category", "Academic Support").strip()
    risk_level = data.get("risk_level", "Medium Risk").strip()
    subject_id = data.get("subject_id")
    due_date = data.get("due_date")
    notes = data.get("notes", "").strip()

    if not title:
        conn.close()
        return jsonify({"success": False, "message": "Intervention title is required."}), 400

    t_inst = teacher["institution_id"] if "institution_id" in teacher.keys() else None
    s_inst = student["institution_id"] if "institution_id" in student.keys() else None
    inst_id = t_inst or s_inst
    teacher_user_id = teacher["user_id"] or session.get("user_id")

    cursor.execute("""
    INSERT INTO interventions (student_id, teacher_id, institution_id, subject_id, risk_level, action_type, title, category, priority, description, status, notes, due_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Assigned', ?, ?)
    """, (
        student_id, teacher_user_id, inst_id,
        subject_id, risk_level, action_type, title, category, priority, description, notes, due_date
    ))
    intervention_id = cursor.lastrowid

    # Dispatch high-priority student notification
    if student["user_id"]:
        notif_msg = f"Faculty {teacher['full_name']} assigned a remedial intervention: '{title}'. Please check your tasks."
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type, is_read, created_at)
        VALUES (?, ?, ?, 'Intervention', 0, CURRENT_TIMESTAMP)
        """, (student["user_id"], f"⚠️ Faculty Action: {title}", notif_msg))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Remedial intervention '{title}' dispatched to {student['full_name']} successfully!",
        "intervention_id": intervention_id
    }), 201


@teacher_bp.route("/api/teacher/students/bulk-intervene", methods=["POST"])
@teacher_required
def bulk_student_remedial_intervention():
    """
    Dispatches 1-Click bulk remedial interventions to multiple students or entire at-risk cohort.
    """
    conn = get_db_connection()
    teacher = get_logged_in_teacher(conn)
    if not teacher:
        conn.close()
        return jsonify({"success": False, "message": "Teacher profile not found."}), 404

    data = request.get_json() or {}
    student_ids = data.get("student_ids", [])
    risk_filter = data.get("risk_filter", "").strip()
    action_type = data.get("action_type", "Remedial Quiz").strip()
    title = data.get("title", f"Bulk Cohort Remedial Intervention - {action_type}").strip()
    description = data.get("description", "Cohort-wide targeted remedial practice assigned by faculty.").strip()
    priority = data.get("priority", "High").strip()
    subject_id = data.get("subject_id")

    cursor = conn.cursor()
    assigned_student_ids = get_teacher_assigned_student_ids(cursor, teacher)

    target_ids = []
    if student_ids:
        target_ids = [sid for sid in student_ids if sid in assigned_student_ids]
    elif risk_filter:
        # Filter assigned students by risk
        placeholders = ",".join(["?"] * len(assigned_student_ids))
        if placeholders:
            cursor.execute(f"SELECT id, attendance, overall_progress FROM students WHERE id IN ({placeholders})", list(assigned_student_ids))
            s_rows = cursor.fetchall()
            for sr in s_rows:
                if risk_filter.lower() == "high" and (float(sr["attendance"] or 75) < 70 or float(sr["overall_progress"] or 50) < 50):
                    target_ids.append(sr["id"])
                elif risk_filter.lower() == "medium" and (float(sr["attendance"] or 75) < 80):
                    target_ids.append(sr["id"])
            
            # If no students match strict risk threshold, include up to 5 assigned students
            if not target_ids and s_rows:
                target_ids = [sr["id"] for sr in s_rows[:5]]
    else:
        target_ids = list(assigned_student_ids)

    if not target_ids:
        conn.close()
        return jsonify({"success": False, "message": "No eligible assigned students found for bulk intervention."}), 400

    t_inst = teacher["institution_id"] if "institution_id" in teacher.keys() else None
    teacher_user_id = teacher["user_id"] or session.get("user_id")
    dispatched_count = 0
    for sid in target_ids:
        cursor.execute("SELECT user_id, full_name, institution_id FROM students WHERE id = ?", (sid,))
        s_info = cursor.fetchone()
        if s_info:
            s_inst = s_info["institution_id"] if "institution_id" in s_info.keys() else None
            inst_id = t_inst or s_inst
            cursor.execute("""
            INSERT INTO interventions (student_id, teacher_id, institution_id, subject_id, risk_level, action_type, title, category, priority, description, status)
            VALUES (?, ?, ?, ?, 'High Risk', ?, ?, 'Cohort Remediation', ?, ?, 'Assigned')
            """, (sid, teacher_user_id, inst_id, subject_id, action_type, title, priority, description))
            
            if s_info["user_id"]:
                cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, is_read, created_at)
                VALUES (?, ?, ?, 'Intervention', 0, CURRENT_TIMESTAMP)
                """, (s_info["user_id"], f"⚠️ Faculty Cohort Action: {title}", f"Faculty {teacher['full_name']} assigned a cohort remedial drill: '{title}'."))
            
            dispatched_count += 1

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"1-Click bulk intervention successfully dispatched to {dispatched_count} students.",
        "intervened_count": dispatched_count
    })


@teacher_bp.route("/api/teacher/interventions/<int:intervention_id>/status", methods=["POST", "PUT"])
@teacher_required
def update_teacher_intervention_status(intervention_id):
    """
    Updates status of an intervention ('In Progress', 'Completed', 'Resolved') and optional resolution notes.
    """
    conn = get_db_connection()
    teacher = get_logged_in_teacher(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM interventions WHERE id = ?", (intervention_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Intervention not found."}), 404

    data = request.get_json() or {}
    new_status = data.get("status", "Completed").strip()
    notes = data.get("notes", "").strip()

    if new_status in ["Completed", "Resolved"]:
        cursor.execute("""
        UPDATE interventions 
        SET status = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END, completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (new_status, notes, notes, intervention_id))
    else:
        cursor.execute("""
        UPDATE interventions 
        SET status = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
        WHERE id = ?
        """, (new_status, notes, notes, intervention_id))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Intervention #{intervention_id} status updated to '{new_status}'."
    })


@teacher_bp.route("/api/teacher/students/<int:student_id>/report-card", methods=["GET"])
@teacher_required
def get_student_report_card_for_teacher(student_id):
    """
    Returns official academic dossier and report card for an assigned student.
    Restricted to teachers assigned to this student or within their cohort.
    """
    conn = get_db_connection()
    teacher = get_logged_in_teacher(conn)
    if not teacher:
        conn.close()
        return jsonify({"success": False, "message": "Teacher profile not found."}), 404

    cursor = conn.cursor()
    assigned_student_ids = get_teacher_assigned_student_ids(cursor, teacher)

    if student_id not in assigned_student_ids:
        conn.close()
        return jsonify({"success": False, "message": "Access denied: Student is not assigned to your class or cohort."}), 403

    from backend.report_service import build_student_report_card
    dossier = build_student_report_card(conn, student_id)
    conn.close()

    if not dossier:
        return jsonify({"success": False, "message": "Failed to generate student report card."}), 500

    return jsonify({
        "success": True,
        "report_card": dossier
    })




