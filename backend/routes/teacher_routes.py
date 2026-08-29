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

@teacher_bp.route("/api/teacher/students", methods=["GET"])
@teacher_required
def get_students_list():
    """
    Returns filtered and searched student list from SQLite database.
    Strictly excludes passwords and password hashes.
    """
    branch_filter = request.args.get("branch", "").strip()
    year_filter = request.args.get("year", "").strip()
    semester_filter = request.args.get("semester", "").strip()
    section_filter = request.args.get("section", "").strip()
    risk_filter = request.args.get("risk", "").strip()
    search_query = request.args.get("search", "").strip().lower()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM students WHERE 1=1"
    params = []
    
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
    personalized learning path, and logged interventions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
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
    cursor = conn.cursor()
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
    cursor = conn.cursor()
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

@teacher_bp.route("/api/teacher/student", methods=["POST"])
@teacher_required
def add_student():
    """
    Allows teacher to register a new student record into the platform.
    Hashes password and inserts user into users and students tables.
    The student can immediately log in with these credentials.
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
    cursor = conn.cursor()
    
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
    INSERT INTO users (email, password_hash, role, full_name)
    VALUES (?, ?, 'student', ?)
    """, (email, pwd_hash, full_name))
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
        learning_activity, previous_performance, overall_progress, notes
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?
    )
    """, (
        user_id, full_name, roll_no, email,
        year, branch, section, int(semester),
        attendance, m_score, p_score, pr_score, ds_score, db_score, comm_score,
        asg_score, qz_score, ex_score, st_hours, activity, prev_perf, progress, notes
    ))
    
    new_student_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"Student {full_name} registered successfully. The student can now log in immediately.",
        "student_id": new_student_id
    }), 201

@teacher_bp.route("/api/teacher/student/<int:student_id>/intervention", methods=["POST"])
@teacher_required
def log_intervention(student_id):
    """
    Logs an actionable teacher intervention for a student.
    """
    data = request.get_json() or {}
    teacher_id = session.get("user_id")
    
    title = data.get("title", "").strip()
    category = data.get("category", "General Guidance").strip()
    priority = data.get("priority", "Moderate").strip()
    description = data.get("description", "").strip()
    risk_level = data.get("risk_level", "Medium Risk").strip()
    notes = data.get("notes", "").strip()
    
    if not title or not description:
        return jsonify({"success": False, "error": "Title and description are required."}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO interventions (student_id, teacher_id, risk_level, title, category, priority, description, notes, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, (student_id, teacher_id, risk_level, title, category, priority, description, notes))
    
    interv_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": "Teacher intervention logged successfully.",
        "intervention_id": interv_id
    }), 201

@teacher_bp.route("/api/teacher/analytics", methods=["GET"])
@teacher_required
def get_class_analytics():
    """
    Computes class-level analytics across all enrolled students:
    Risk distribution, average attendance, subject performance averages,
    and weak-subject frequencies.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    rows = cursor.fetchall()
    conn.close()
    
    total_students = len(rows)
    if total_students == 0:
        return jsonify({
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
    """Returns student inquiry threads for this teacher with unread counts."""
    user_id = session.get("user_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get teacher record id
    cursor.execute("SELECT id FROM teachers WHERE user_id = ?", (user_id,))
    t_row = cursor.fetchone()
    teacher_id = t_row["id"] if t_row else None
    
    if not teacher_id:
        conn.close()
        return jsonify({"success": True, "conversations": []})
        
    cursor.execute("""
    SELECT DISTINCT m.conversation_id, m.subject_id, s.subject_name, s.subject_code,
           st.id as student_id, st.full_name as student_name, st.roll_no, st.branch, st.year, st.section,
           (SELECT message FROM messages m2 WHERE m2.conversation_id = m.conversation_id ORDER BY m2.created_at DESC LIMIT 1) as last_message,
           (SELECT created_at FROM messages m2 WHERE m2.conversation_id = m.conversation_id ORDER BY m2.created_at DESC LIMIT 1) as last_updated,
           (SELECT count(*) FROM messages m2 WHERE m2.conversation_id = m.conversation_id AND m2.receiver_role = 'teacher' AND m2.receiver_id = ? AND m2.is_read = 0) as unread_count
    FROM messages m
    JOIN subjects s ON m.subject_id = s.id
    JOIN students st ON (m.sender_role = 'student' AND m.sender_id = st.id) OR (m.receiver_role = 'student' AND m.receiver_id = st.id)
    WHERE (m.sender_role = 'teacher' AND m.sender_id = ?) OR (m.receiver_role = 'teacher' AND m.receiver_id = ?)
    ORDER BY last_updated DESC
    """, (teacher_id, teacher_id, teacher_id))
    
    threads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "conversations": threads})

@teacher_bp.route("/api/teacher/messages/<string:conversation_id>", methods=["GET"])
@teacher_required
def get_teacher_thread_messages(conversation_id):
    """Fetches messages in a thread and marks unread items sent by student as read."""
    user_id = session.get("user_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM teachers WHERE user_id = ?", (user_id,))
    t_row = cursor.fetchone()
    teacher_id = t_row["id"] if t_row else None
    
    if not teacher_id:
        conn.close()
        return jsonify({"success": False, "message": "Teacher not found."}), 404
        
    cursor.execute("""
    SELECT * FROM messages 
    WHERE conversation_id = ? AND ((sender_role = 'teacher' AND sender_id = ?) OR (receiver_role = 'teacher' AND receiver_id = ?))
    ORDER BY created_at ASC
    """, (conversation_id, teacher_id, teacher_id))
    
    messages = [dict(row) for row in cursor.fetchall()]
    
    # Mark teacher unread messages as read
    cursor.execute("""
    UPDATE messages SET is_read = 1 
    WHERE conversation_id = ? AND receiver_role = 'teacher' AND receiver_id = ? AND is_read = 0
    """, (conversation_id, teacher_id))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "messages": messages})

@teacher_bp.route("/api/teacher/messages", methods=["POST"])
@teacher_required
def send_teacher_reply():
    """Teacher sends a reply to a student in a conversation thread."""
    user_id = session.get("user_id")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, full_name FROM teachers WHERE user_id = ?", (user_id,))
    t_row = cursor.fetchone()
    if not t_row:
        conn.close()
        return jsonify({"success": False, "message": "Teacher not found."}), 404
        
    teacher_id = t_row["id"]
    teacher_name = t_row["full_name"]
    
    data = request.get_json() or {}
    conversation_id = data.get("conversation_id", "").strip()
    student_id = data.get("student_id")
    subject_id = data.get("subject_id")
    reply_text = data.get("message", "").strip()
    
    if not conversation_id or not student_id or not subject_id or not reply_text:
        conn.close()
        return jsonify({"success": False, "message": "Conversation ID, student ID, subject ID, and message are required."}), 400
        
    cursor.execute("""
    INSERT INTO messages (conversation_id, sender_id, sender_role, receiver_id, receiver_role, subject_id, message, is_read)
    VALUES (?, ?, 'teacher', ?, 'student', ?, ?, 0)
    """, (conversation_id, teacher_id, student_id, subject_id, reply_text))
    
    # Create notification for student
    cursor.execute("SELECT user_id FROM students WHERE id = ?", (student_id,))
    st_row = cursor.fetchone()
    if st_row and st_row["user_id"]:
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type, is_read)
        VALUES (?, ?, ?, 'message', 0)
        """, (st_row["user_id"], f"New Reply from {teacher_name}", f"Faculty {teacher_name} replied to your subject inquiry."))
        
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": "Reply sent to student successfully.",
        "conversation_id": conversation_id
    }), 201

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
    "ai & ml": "CSE (AI & ML)",
    "ai/ml": "CSE (AI & ML)",
    "cse (ai & ml)": "CSE (AI & ML)",
    "cse(ai&ml)": "CSE (AI & ML)",
    "cse-ai&ml": "CSE (AI & ML)",
    "data science": "CSE (Data Science)",
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
    "1": "1st Year", "1st": "1st Year", "1st year": "1st Year", "first year": "1st Year",
    "2": "2nd Year", "2nd": "2nd Year", "2nd year": "2nd Year", "second year": "2nd Year",
    "3": "3rd Year", "3rd": "3rd Year", "3rd year": "3rd Year", "third year": "3rd Year",
    "4": "4th Year", "4th": "4th Year", "4th year": "4th Year", "fourth year": "4th Year"
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
    # Normalize header keys
    if not reader.fieldnames:
        return [], []
    cleaned_fieldnames = [f.strip().lower().replace(" ", "_") if f else "" for f in reader.fieldnames]
    reader.fieldnames = cleaned_fieldnames
    rows = list(reader)
    return rows, cleaned_fieldnames

@teacher_bp.route("/api/teacher/students/template", methods=["GET"])
@teacher_required
def download_student_csv_template():
    """Generates and downloads a clean CSV template for bulk student upload."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    headers = [
        "student_name", "roll_no", "email", "password", "year", "branch", "section", "semester",
        "attendance", "mathematics_score", "physics_score", "programming_score",
        "data_structures_score", "database_score", "communication_score",
        "assignment_score", "quiz_score", "exam_score", "study_hours", "overall_progress"
    ]
    writer.writerow(headers)
    
    # Sample rows (teachers can delete and replace)
    writer.writerow([
        "Rahul Kumar", "23CSE101", "rahul.sample@apedu.ac.in", "Rahul123",
        "2nd Year", "CSE", "A", "3",
        "78.0", "70.0", "65.0", "75.0", "72.0", "68.0", "80.0", "75.0", "70.0", "72.0", "8.0", "65.0"
    ])
    writer.writerow([
        "Priya Sharma", "23CSE102", "priya.sample@apedu.ac.in", "Priya123",
        "2nd Year", "CSE", "A", "3",
        "86.0", "88.0", "82.0", "90.0", "85.0", "88.0", "90.0", "88.0", "85.0", "86.0", "10.0", "82.0"
    ])
    writer.writerow([
        "Arun Varma", "23ECE101", "arun.sample@apedu.ac.in", "Arun123",
        "3rd Year", "ECE", "B", "5",
        "64.0", "58.0", "60.0", "55.0", "52.0", "60.0", "65.0", "62.0", "58.0", "58.0", "5.0", "50.0"
    ])
    
    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=student_bulk_upload_template.csv"}
    )

@teacher_bp.route("/api/teacher/students/upload/preview", methods=["POST"])
@teacher_required
def preview_student_csv():
    """
    Validates uploaded student CSV without saving.
    Returns preview stats, valid rows, invalid rows, and validation error list.
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
        
    # Verify required headers
    req_keys = ["student_name", "roll_no", "email", "password", "year", "branch", "section", "semester"]
    missing_headers = [k for k in req_keys if not any(k in h for h in headers)]
    if missing_headers:
        return jsonify({
            "success": False,
            "message": f"Missing required CSV column headers: {', '.join(missing_headers)}"
        }), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Pre-fetch existing emails and roll numbers
    cursor.execute("SELECT LOWER(email) FROM users")
    existing_emails = set(r[0] for r in cursor.fetchall())
    cursor.execute("SELECT UPPER(roll_no) FROM students")
    existing_rolls = set(r[0] for r in cursor.fetchall())
    conn.close()
    
    seen_csv_emails = set()
    seen_csv_rolls = set()
    
    valid_rows = []
    errors = []
    
    for idx, row in enumerate(rows, start=2): # Row 1 is header
        name = row.get("student_name") or row.get("name") or row.get("full_name") or ""
        roll = row.get("roll_no") or row.get("rollno") or row.get("roll_number") or ""
        email = row.get("email") or ""
        pwd = row.get("password") or ""
        yr = row.get("year") or ""
        br = row.get("branch") or ""
        sec = row.get("section") or ""
        sem = row.get("semester") or ""
        
        name = str(name).strip()
        roll = str(roll).strip().upper()
        email = str(email).strip().lower()
        pwd = str(pwd).strip()
        yr = normalize_year(yr)
        br = normalize_branch(br)
        sec = str(sec).strip().upper()
        parsed_sem = parse_semester(sem)
        
        # Validations
        row_errs = []
        if not name:
            row_errs.append("Student name is empty")
        if not roll:
            row_errs.append("Roll number is empty")
        elif roll in seen_csv_rolls:
            row_errs.append(f"Duplicate roll number in CSV: {roll}")
        elif roll in existing_rolls:
            row_errs.append(f"Roll number already exists in database: {roll}")
            
        if not email:
            row_errs.append("Email is empty")
        elif not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
            row_errs.append(f"Invalid email format: {email}")
        elif email in seen_csv_emails:
            row_errs.append(f"Duplicate email in CSV: {email}")
        elif email in existing_emails:
            row_errs.append(f"Email already registered in database: {email}")
            
        if not pwd:
            row_errs.append("Password is empty")
        elif len(pwd) < 4:
            row_errs.append("Password must be at least 4 characters")
            
        if not yr or yr not in ["1st Year", "2nd Year", "3rd Year", "4th Year"]:
            row_errs.append(f"Invalid academic year '{row.get('year')}'. Expected 1st, 2nd, 3rd, or 4th Year.")
            
        if not br:
            row_errs.append("Branch is empty")
            
        if not sec:
            sec = "A"
            
        if not parsed_sem:
            row_errs.append(f"Invalid semester '{sem}'. Expected integer between 1 and 8.")
            
        if row_errs:
            errors.append({
                "row": idx,
                "roll_no": roll or "-",
                "email": email or "-",
                "error": "; ".join(row_errs)
            })
        else:
            seen_csv_rolls.add(roll)
            seen_csv_emails.add(email)
            valid_rows.append({
                "student_name": name,
                "roll_no": roll,
                "email": email,
                "year": yr,
                "branch": br,
                "section": sec,
                "semester": parsed_sem
            })
            
    return jsonify({
        "success": True,
        "total_rows": len(rows),
        "valid_count": len(valid_rows),
        "valid_rows": len(valid_rows),
        "invalid_count": len(errors),
        "invalid_rows": len(errors),
        "preview": valid_rows[:10],
        "errors": errors
    })

@teacher_bp.route("/api/teacher/students/upload", methods=["POST"])
@teacher_required
def upload_students_csv():
    """
    Processes and inserts valid student records from CSV into SQLite database.
    Hashes passwords securely with Werkzeug generate_password_hash.
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
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Pre-fetch existing emails and roll numbers
    cursor.execute("SELECT LOWER(email) FROM users")
    existing_emails = set(r[0] for r in cursor.fetchall())
    cursor.execute("SELECT UPPER(roll_no) FROM students")
    existing_rolls = set(r[0] for r in cursor.fetchall())
    
    seen_csv_emails = set()
    seen_csv_rolls = set()
    
    imported_count = 0
    skipped_count = 0
    errors = []
    
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        for idx, row in enumerate(rows, start=2):
            name = (row.get("student_name") or row.get("name") or row.get("full_name") or "").strip()
            roll = (row.get("roll_no") or row.get("rollno") or row.get("roll_number") or "").strip().upper()
            email = (row.get("email") or "").strip().lower()
            pwd = (row.get("password") or "").strip()
            yr = normalize_year(row.get("year") or "")
            br = normalize_branch(row.get("branch") or "")
            sec = (row.get("section") or "A").strip().upper()
            sem = parse_semester(row.get("semester"))
            
            # Row level validations
            if not name or not roll or not email or not pwd or not yr or not br or not sem:
                skipped_count += 1
                errors.append({
                    "row": idx,
                    "roll_no": roll or "-",
                    "email": email or "-",
                    "error": "Missing mandatory fields (name, roll_no, email, password, year, branch, or semester)"
                })
                continue
                
            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
                skipped_count += 1
                errors.append({
                    "row": idx,
                    "roll_no": roll,
                    "email": email,
                    "error": f"Invalid email format: {email}"
                })
                continue
                
            if roll in existing_rolls or roll in seen_csv_rolls:
                skipped_count += 1
                errors.append({
                    "row": idx,
                    "roll_no": roll,
                    "email": email,
                    "error": f"Duplicate student roll number skipped: {roll}"
                })
                continue
                
            if email in existing_emails or email in seen_csv_emails:
                skipped_count += 1
                errors.append({
                    "row": idx,
                    "roll_no": roll,
                    "email": email,
                    "error": f"Duplicate email address skipped: {email}"
                })
                continue
                
            # Parse optional scores or defaults
            def get_float(k, default_v):
                try:
                    val = row.get(k)
                    return float(val) if val is not None and str(val).strip() != "" else default_v
                except Exception:
                    return default_v

            attendance = get_float("attendance", 75.0)
            m_score = get_float("mathematics_score", 65.0)
            p_score = get_float("physics_score", 65.0)
            pr_score = get_float("programming_score", 65.0)
            ds_score = get_float("data_structures_score", 65.0)
            db_score = get_float("database_score", 65.0)
            comm_score = get_float("communication_score", 70.0)
            asg_score = get_float("assignment_score", 70.0)
            qz_score = get_float("quiz_score", 65.0)
            ex_score = get_float("exam_score", 65.0)
            st_hours = get_float("study_hours", 8.0)
            activity = get_float("learning_activity", 60.0)
            prev_perf = get_float("previous_performance", 65.0)
            progress = get_float("overall_progress", 0.0)
            
            # Securely hash password using Werkzeug
            pwd_hash = generate_password_hash(pwd)
            
            cursor.execute("""
            INSERT INTO users (email, password_hash, role, full_name)
            VALUES (?, ?, 'student', ?)
            """, (email, pwd_hash, name))
            new_user_id = cursor.lastrowid
            
            cursor.execute("""
            INSERT INTO students (
                user_id, full_name, roll_no, email, year, branch, section, semester,
                attendance, mathematics_score, physics_score, programming_score,
                data_structures_score, database_score, communication_score,
                assignment_score, quiz_score, exam_score, study_hours,
                learning_activity, previous_performance, overall_progress, learning_streak
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, 3
            )
            """, (
                new_user_id, name, roll, email, yr, br, sec, sem,
                attendance, m_score, p_score, pr_score, ds_score, db_score, comm_score,
                asg_score, qz_score, ex_score, st_hours, activity, prev_perf, progress
            ))
            
            seen_csv_rolls.add(roll)
            seen_csv_emails.add(email)
            existing_rolls.add(roll)
            existing_emails.add(email)
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
