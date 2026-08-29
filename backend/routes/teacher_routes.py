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
    "aiml": "CSE (AI & ML)",
    "ai & ml": "CSE (AI & ML)",
    "ai/ml": "CSE (AI & ML)",
    "cse (ai & ml)": "CSE (AI & ML)",
    "cse(ai&ml)": "CSE (AI & ML)",
    "cse-ai&ml": "CSE (AI & ML)",
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
    cursor = conn.cursor()
    
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
            INSERT INTO users (email, password_hash, role, full_name)
            VALUES (?, ?, 'student', ?)
            """, (email.lower(), pwd_hash, name))
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
                new_user_id, name, roll, email.lower(), norm_yr, norm_br, sec, sem,
                attendance, m_score, p_score, pr_score, ds_score, db_score, comm_score,
                asg_score, qz_score, ex_score, st_hours, activity, prev_perf, progress
            ))
            
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
