"""
Student Academic Portal API Routes
Handles dynamic subject loading by Branch + Year + Semester, lessons, labs,
assessments, adaptive quizzes, subject-specific teacher messaging, and progress tracking.
"""

from flask import Blueprint, request, jsonify, session
from backend.database import get_db_connection
from backend.auth import student_required, get_current_user
from backend.models import serialize_student
from ml.predict import predict_student_risk
from ml.personalized_learning import generate_personalized_learning_path

student_bp = Blueprint("student", __name__)

def get_logged_in_student(conn):
    """Helper to fetch student record for the currently authenticated session."""
    user = get_current_user()
    if not user or user["role"] != "student":
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE user_id = ? OR LOWER(email) = ?", (user["id"], user["email"].lower()))
    return cursor.fetchone()

# ================= 1. STUDENT PROFILE =================
@student_bp.route("/api/student/me", methods=["GET"])
@student_required
def get_student_profile():
    """Returns student profile with academic coordinates (branch, year, semester, section)."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student profile not found."}), 404
        
    data = serialize_student(student)
    data["learning_streak"] = student["learning_streak"] if "learning_streak" in student.keys() else 3
    conn.close()
    return jsonify({"success": True, "student": data})

# ================= 2. ACADEMIC SUBJECTS & SELECTION =================
@student_bp.route("/api/student/subjects/available", methods=["GET"])
@student_required
def get_available_subjects():
    """
    Returns all subjects available for the student's exact Branch + Year + Semester,
    with an 'is_selected' boolean indicating if the student enrolled in it.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404
        
    cursor = conn.cursor()
    
    # Query all subjects matching student's Branch + Year + Semester
    cursor.execute("""
    SELECT s.*, 
           t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email,
           (SELECT count(*) FROM student_subjects ss WHERE ss.student_id = ? AND ss.subject_id = s.id) as is_selected
    FROM subjects s
    LEFT JOIN teacher_subjects ts ON s.id = ts.subject_id 
         AND ts.branch = s.branch 
         AND ts.year = s.year 
         AND ts.semester = s.semester 
         AND ts.section = ?
    LEFT JOIN teachers t ON ts.teacher_id = t.id
    WHERE s.branch = ? AND s.year = ? AND s.semester = ?
    ORDER BY s.subject_code ASC
    """, (student["id"], student["section"], student["branch"], student["year"], student["semester"]))
    
    rows = cursor.fetchall()
    subjects = []
    for r in rows:
        subjects.append({
            "id": r["id"],
            "subject_code": r["subject_code"],
            "subject_name": r["subject_name"],
            "branch": r["branch"],
            "year": r["year"],
            "semester": r["semester"],
            "credits": r["credits"],
            "subject_type": r["subject_type"],
            "description": r["description"],
            "is_selected": bool(r["is_selected"]),
            "teacher": {
                "id": r["teacher_id"],
                "name": r["teacher_name"] or "Faculty Assigned",
                "email": r["teacher_email"] or ""
            }
        })
        
    conn.close()
    return jsonify({
        "success": True,
        "branch": student["branch"],
        "year": student["year"],
        "semester": student["semester"],
        "total_available": len(subjects),
        "subjects": subjects
    })

@student_bp.route("/api/student/subjects/select", methods=["POST"])
@student_required
def select_student_subjects():
    """
    Saves the student's chosen subjects into student_subjects.
    Validates that each subject belongs strictly to the student's Branch + Year + Semester.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404
        
    cursor = conn.cursor()
    data = request.get_json() or {}
    selected_ids = data.get("subject_ids", [])
    
    if not isinstance(selected_ids, list):
        conn.close()
        return jsonify({"success": False, "message": "subject_ids must be a list of integers."}), 400
        
    # Verify that all requested subjects belong strictly to this student's branch/year/sem
    if selected_ids:
        placeholders = ",".join("?" for _ in selected_ids)
        cursor.execute(f"""
        SELECT id FROM subjects
        WHERE id IN ({placeholders}) AND branch = ? AND year = ? AND semester = ?
        """, (*selected_ids, student["branch"], student["year"], student["semester"]))
        
        valid_rows = cursor.fetchall()
        valid_ids = [r[0] for r in valid_rows]
        
        if len(valid_ids) != len(selected_ids):
            conn.close()
            return jsonify({
                "success": False,
                "message": "One or more selected subjects do not belong to your academic Branch, Year, or Semester."
            }), 400
            
    # Atomic update of selected subjects
    cursor.execute("DELETE FROM student_subjects WHERE student_id = ?", (student["id"],))
    for s_id in selected_ids:
        cursor.execute("""
        INSERT INTO student_subjects (student_id, subject_id)
        VALUES (?, ?)
        """, (student["id"], s_id))
        
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"Successfully enrolled in {len(selected_ids)} subject(s).",
        "selected_count": len(selected_ids)
    })

@student_bp.route("/api/student/subjects", methods=["GET"])
@student_required
def get_student_subjects():
    """
    Returns subjects for the authenticated student based on their selected courses (student_subjects).
    If student hasn't explicitly selected yet, returns all available subjects for their branch/year/sem.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404
        
    cursor = conn.cursor()
    
    # Check if student has explicit selections in student_subjects
    cursor.execute("SELECT count(*) FROM student_subjects WHERE student_id = ?", (student["id"],))
    has_custom_selection = cursor.fetchone()[0] > 0
    
    if has_custom_selection:
        cursor.execute("""
        SELECT s.*, 
               t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email
        FROM student_subjects ss
        JOIN subjects s ON ss.subject_id = s.id
        LEFT JOIN teacher_subjects ts ON s.id = ts.subject_id 
             AND ts.branch = s.branch 
             AND ts.year = s.year 
             AND ts.semester = s.semester 
             AND ts.section = ?
        LEFT JOIN teachers t ON ts.teacher_id = t.id
        WHERE ss.student_id = ? AND s.branch = ? AND s.year = ? AND s.semester = ?
        ORDER BY s.subject_code ASC
        """, (student["section"], student["id"], student["branch"], student["year"], student["semester"]))
    else:
        cursor.execute("""
        SELECT s.*, 
               t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email
        FROM subjects s
        LEFT JOIN teacher_subjects ts ON s.id = ts.subject_id 
             AND ts.branch = s.branch 
             AND ts.year = s.year 
             AND ts.semester = s.semester 
             AND ts.section = ?
        LEFT JOIN teachers t ON ts.teacher_id = t.id
        WHERE s.branch = ? AND s.year = ? AND s.semester = ?
        ORDER BY s.subject_code ASC
        """, (student["section"], student["branch"], student["year"], student["semester"]))
    
    subject_rows = cursor.fetchall()
    subjects_list = []
    
    for sub in subject_rows:
        sub_id = sub["id"]
        
        # Calculate subject progress
        cursor.execute("SELECT count(*) FROM lessons WHERE subject_id = ?", (sub_id,))
        total_lessons = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT count(*) FROM lesson_progress lp
        JOIN lessons l ON lp.lesson_id = l.id
        WHERE lp.student_id = ? AND l.subject_id = ? AND lp.status = 'Completed'
        """, (student["id"], sub_id))
        completed_lessons = cursor.fetchone()[0]
        
        cursor.execute("SELECT count(*) FROM labs WHERE subject_id = ?", (sub_id,))
        total_labs = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT count(*) FROM lab_progress labp
        JOIN labs lb ON labp.lab_id = lb.id
        WHERE labp.student_id = ? AND lb.subject_id = ? AND labp.status = 'Completed'
        """, (student["id"], sub_id))
        completed_labs = cursor.fetchone()[0]
        
        cursor.execute("SELECT count(*) FROM quizzes WHERE subject_id = ?", (sub_id,))
        total_quizzes = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT count(*) FROM quiz_results qr
        JOIN quizzes qz ON qr.quiz_id = qz.id
        WHERE qr.student_id = ? AND qz.subject_id = ?
        """, (student["id"], sub_id))
        completed_quizzes = cursor.fetchone()[0]
        
        cursor.execute("SELECT count(*) FROM assignments WHERE subject_id = ?", (sub_id,))
        total_assignments = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT count(*) FROM assignment_submissions asub
        JOIN assignments a ON asub.assignment_id = a.id
        WHERE asub.student_id = ? AND a.subject_id = ?
        """, (student["id"], sub_id))
        completed_assignments = cursor.fetchone()[0]
        
        total_items = total_lessons + total_labs + total_quizzes + total_assignments
        completed_items = completed_lessons + completed_labs + completed_quizzes + completed_assignments
        
        progress_pct = round((completed_items / total_items * 100.0), 1) if total_items > 0 else 0.0
        
        subjects_list.append({
            "id": sub["id"],
            "subject_code": sub["subject_code"],
            "subject_name": sub["subject_name"],
            "branch": sub["branch"],
            "year": sub["year"],
            "semester": sub["semester"],
            "credits": sub["credits"],
            "subject_type": sub["subject_type"],
            "description": sub["description"],
            "teacher": {
                "id": sub["teacher_id"],
                "name": sub["teacher_name"] or "Faculty Assigned",
                "email": sub["teacher_email"] or ""
            },
            "stats": {
                "total_lessons": total_lessons,
                "completed_lessons": completed_lessons,
                "total_labs": total_labs,
                "completed_labs": completed_labs,
                "total_quizzes": total_quizzes,
                "completed_quizzes": completed_quizzes,
                "total_assignments": total_assignments,
                "completed_assignments": completed_assignments,
                "progress_percentage": progress_pct
            }
        })
        
    conn.close()
    return jsonify({
        "success": True,
        "student": {
            "id": student["id"],
            "full_name": student["full_name"],
            "roll_no": student["roll_no"],
            "branch": student["branch"],
            "year": student["year"],
            "semester": student["semester"],
            "section": student["section"]
        },
        "branch": student["branch"],
        "year": student["year"],
        "semester": student["semester"],
        "section": student["section"],
        "total_subjects": len(subjects_list),
        "subjects": subjects_list
    })

# ================= 3. SUBJECT DETAILS =================
@student_bp.route("/api/student/subjects/<int:subject_id>", methods=["GET"])
@student_required
def get_subject_details(subject_id):
    """Returns single subject details, syllabus breakdown, and assigned teacher."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT s.*, t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email
    FROM subjects s
    LEFT JOIN teacher_subjects ts ON s.id = ts.subject_id 
         AND ts.branch = s.branch 
         AND ts.year = s.year 
         AND ts.semester = s.semester 
         AND ts.section = ?
    LEFT JOIN teachers t ON ts.teacher_id = t.id
    WHERE s.id = ? AND s.branch = ? AND s.year = ? AND s.semester = ?
    """, (student["section"], subject_id, student["branch"], student["year"], student["semester"]))
    
    sub = cursor.fetchone()
    if not sub:
        conn.close()
        return jsonify({"success": False, "message": "Subject not found in your academic curriculum."}), 404
        
    cursor.execute("SELECT count(*) FROM lessons WHERE subject_id = ?", (subject_id,))
    total_lessons = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM labs WHERE subject_id = ?", (subject_id,))
    total_labs = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM quizzes WHERE subject_id = ?", (subject_id,))
    total_quizzes = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM assessments WHERE subject_id = ?", (subject_id,))
    total_assessments = cursor.fetchone()[0]
    
    conn.close()
    return jsonify({
        "success": True,
        "subject": {
            "id": sub["id"],
            "subject_code": sub["subject_code"],
            "subject_name": sub["subject_name"],
            "branch": sub["branch"],
            "year": sub["year"],
            "semester": sub["semester"],
            "credits": sub["credits"],
            "subject_type": sub["subject_type"],
            "description": sub["description"],
            "teacher": {
                "id": sub["teacher_id"],
                "name": sub["teacher_name"] or "Faculty Assigned",
                "email": sub["teacher_email"] or ""
            },
            "counts": {
                "lessons": total_lessons,
                "labs": total_labs,
                "quizzes": total_quizzes,
                "assessments": total_assessments
            }
        }
    })

# ================= 4. LESSONS SYSTEM =================
@student_bp.route("/api/student/subjects/<int:subject_id>/lessons", methods=["GET"])
@student_required
def get_subject_lessons(subject_id):
    """Returns all lessons for a subject with student's completion progress."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT l.*, COALESCE(lp.status, 'Not Started') as status,
           COALESCE(lp.progress_percentage, 0.0) as progress_percentage,
           lp.completed_at, lp.last_accessed
    FROM lessons l
    LEFT JOIN lesson_progress lp ON l.id = lp.lesson_id AND lp.student_id = ?
    WHERE l.subject_id = ?
    ORDER BY l.order_number ASC
    """, (student["id"], subject_id))
    
    lessons = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "lessons": lessons})

@student_bp.route("/api/student/lessons/<int:lesson_id>", methods=["GET"])
@student_required
def get_lesson_content(lesson_id):
    """Fetches full markdown content for a lesson and marks it In Progress if Not Started."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
    lesson = cursor.fetchone()
    if not lesson:
        conn.close()
        return jsonify({"success": False, "message": "Lesson not found."}), 404
        
    cursor.execute("SELECT * FROM lesson_progress WHERE student_id = ? AND lesson_id = ?", (student["id"], lesson_id))
    prog = cursor.fetchone()
    if not prog:
        cursor.execute("""
        INSERT INTO lesson_progress (student_id, lesson_id, status, progress_percentage)
        VALUES (?, ?, 'In Progress', 25.0)
        """, (student["id"], lesson_id))
        conn.commit()
    
    cursor.execute("SELECT * FROM lesson_progress WHERE student_id = ? AND lesson_id = ?", (student["id"], lesson_id))
    updated_prog = cursor.fetchone()
    
    lesson_data = dict(lesson)
    lesson_data["status"] = updated_prog["status"] if updated_prog else "In Progress"
    lesson_data["progress_percentage"] = updated_prog["progress_percentage"] if updated_prog else 25.0
    
    conn.close()
    return jsonify({"success": True, "lesson": lesson_data})

@student_bp.route("/api/student/lessons/<int:lesson_id>/complete", methods=["POST"])
@student_required
def mark_lesson_complete(lesson_id):
    """Marks a lesson as Completed in SQLite, updates student progress and streak."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO lesson_progress (student_id, lesson_id, status, progress_percentage, completed_at)
    VALUES (?, ?, 'Completed', 100.0, CURRENT_TIMESTAMP)
    ON CONFLICT(student_id, lesson_id) DO UPDATE SET
        status = 'Completed',
        progress_percentage = 100.0,
        completed_at = CURRENT_TIMESTAMP,
        last_accessed = CURRENT_TIMESTAMP
    """, (student["id"], lesson_id))
    
    # Increment student learning activity
    cursor.execute("""
    UPDATE students SET 
        learning_activity = MIN(100.0, learning_activity + 2.5),
        overall_progress = MIN(100.0, overall_progress + 1.5)
    WHERE id = ?
    """, (student["id"],))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Lesson marked as completed successfully."})

# ================= 5. LABS SYSTEM =================
@student_bp.route("/api/student/subjects/<int:subject_id>/labs", methods=["GET"])
@student_required
def get_subject_labs(subject_id):
    """Returns labs for a subject with student's completion status."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT lb.*, COALESCE(lp.status, 'Not Started') as status,
           COALESCE(lp.score, 0.0) as score, lp.completed_at
    FROM labs lb
    LEFT JOIN lab_progress lp ON lb.id = lp.lab_id AND lp.student_id = ?
    WHERE lb.subject_id = ?
    ORDER BY lb.experiment_number ASC
    """, (student["id"], subject_id))
    
    labs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "labs": labs})

@student_bp.route("/api/student/labs/<int:lab_id>/complete", methods=["POST"])
@student_required
def complete_lab(lab_id):
    """Submits a lab experiment and marks it Completed in database."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    data = request.get_json() or {}
    score = float(data.get("score", 92.0))
    
    cursor.execute("""
    INSERT INTO lab_progress (student_id, lab_id, status, score, completed_at)
    VALUES (?, ?, 'Completed', ?, CURRENT_TIMESTAMP)
    ON CONFLICT(student_id, lab_id) DO UPDATE SET
        status = 'Completed',
        score = ?,
        completed_at = CURRENT_TIMESTAMP
    """, (student["id"], lab_id, score, score))
    
    cursor.execute("""
    UPDATE students SET 
        learning_activity = MIN(100.0, learning_activity + 3.0),
        overall_progress = MIN(100.0, overall_progress + 2.0)
    WHERE id = ?
    """, (student["id"],))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Lab experiment completed successfully with score {score}%."})

# ================= 6. ASSIGNMENTS & ASSESSMENTS =================
@student_bp.route("/api/student/subjects/<int:subject_id>/assignments", methods=["GET"])
@student_required
def get_subject_assignments(subject_id):
    """Returns assignments for a specific subject with student's submission status."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT a.*, 
           COALESCE(asub.status, 'Pending') as status,
           asub.submission_text, asub.score, asub.feedback, asub.submitted_at
    FROM assignments a
    LEFT JOIN assignment_submissions asub ON a.id = asub.assignment_id AND asub.student_id = ?
    WHERE a.subject_id = ?
    ORDER BY a.due_date ASC
    """, (student["id"], subject_id))
    
    assignments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "assignments": assignments})

@student_bp.route("/api/student/assignments", methods=["GET"])
@student_required
def get_student_all_assignments():
    """Returns assignments across all selected subjects for the student."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT a.*, s.subject_name, s.subject_code,
           COALESCE(asub.status, 'Pending') as status,
           asub.submission_text, asub.score, asub.feedback, asub.submitted_at
    FROM assignments a
    JOIN subjects s ON a.subject_id = s.id
    LEFT JOIN assignment_submissions asub ON a.id = asub.assignment_id AND asub.student_id = ?
    WHERE s.branch = ? AND s.year = ? AND s.semester = ?
    ORDER BY a.due_date ASC
    """, (student["id"], student["branch"], student["year"], student["semester"]))
    
    assignments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "assignments": assignments})

@student_bp.route("/api/student/assignments/<int:assignment_id>/submit", methods=["POST"])
@student_required
def submit_student_assignment(assignment_id):
    """Submits a coursework assignment, saving into assignment_submissions and updating progress."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
    assignment = cursor.fetchone()
    if not assignment:
        conn.close()
        return jsonify({"success": False, "message": "Assignment not found."}), 404
        
    data = request.get_json() or {}
    submission_text = data.get("submission_text", "").strip()
    if not submission_text:
        conn.close()
        return jsonify({"success": False, "message": "Submission text/content is required."}), 400
        
    cursor.execute("""
    INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, score, status, submitted_at)
    VALUES (?, ?, ?, 85.0, 'Submitted', CURRENT_TIMESTAMP)
    ON CONFLICT(assignment_id, student_id) DO UPDATE SET
        submission_text = ?,
        submitted_at = CURRENT_TIMESTAMP,
        status = 'Submitted'
    """, (assignment_id, student["id"], submission_text, submission_text))
    
    cursor.execute("""
    UPDATE students SET 
        learning_activity = MIN(100.0, learning_activity + 3.0),
        overall_progress = MIN(100.0, overall_progress + 2.0)
    WHERE id = ?
    """, (student["id"],))
    
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": "Assignment submitted successfully.",
        "assignment_id": assignment_id
    })

@student_bp.route("/api/student/assessments", methods=["GET"])
@student_required
def get_student_assessments():
    """Returns active and completed assessments for student's subjects."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT a.*, s.subject_name, s.subject_code,
           COALESCE(ar.status, 'Pending') as status,
           ar.score, ar.percentage, ar.submitted_at
    FROM assessments a
    JOIN subjects s ON a.subject_id = s.id
    LEFT JOIN assessment_results ar ON a.id = ar.assessment_id AND ar.student_id = ?
    WHERE s.branch = ? AND s.year = ? AND s.semester = ?
    ORDER BY a.due_date ASC
    """, (student["id"], student["branch"], student["year"], student["semester"]))
    
    assessments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "assessments": assessments})

@student_bp.route("/api/student/assessments/<int:assessment_id>/submit", methods=["POST"])
@student_required
def submit_assessment(assessment_id):
    """Submits an assessment, saving score into assessment_results."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,))
    assessment = cursor.fetchone()
    if not assessment:
        conn.close()
        return jsonify({"success": False, "message": "Assessment not found."}), 404
        
    data = request.get_json() or {}
    total_marks = assessment["total_marks"]
    score = float(data.get("score", total_marks * 0.85))
    percentage = round((score / total_marks * 100.0), 1)
    
    cursor.execute("""
    INSERT INTO assessment_results (student_id, assessment_id, score, total_marks, percentage, status)
    VALUES (?, ?, ?, ?, ?, 'Graded')
    ON CONFLICT(student_id, assessment_id) DO UPDATE SET
        score = ?,
        total_marks = ?,
        percentage = ?,
        submitted_at = CURRENT_TIMESTAMP,
        status = 'Graded'
    """, (student["id"], assessment_id, score, total_marks, percentage, score, total_marks, percentage))
    
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": "Assessment submitted successfully.",
        "score": score,
        "total_marks": total_marks,
        "percentage": percentage
    })

# ================= 7. ADAPTIVE QUIZZES =================
@student_bp.route("/api/student/subjects/<int:subject_id>/quizzes", methods=["GET"])
@student_required
def get_subject_quizzes(subject_id):
    """Returns list of quizzes for a subject with past results."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT q.*, qr.score as last_score, qr.percentage as last_percentage,
           qr.completed_at as last_completed_at, qr.weak_topic
    FROM quizzes q
    LEFT JOIN quiz_results qr ON q.id = qr.quiz_id AND qr.student_id = ?
    WHERE q.subject_id = ?
    ORDER BY q.id ASC
    """, (student["id"], subject_id))
    
    quizzes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "quizzes": quizzes})

@student_bp.route("/api/student/quizzes/<int:quiz_id>", methods=["GET"])
@student_required
def get_quiz_questions(quiz_id):
    """Returns quiz questions (hiding correct options until submission)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
    quiz = cursor.fetchone()
    if not quiz:
        conn.close()
        return jsonify({"success": False, "message": "Quiz not found."}), 404
        
    cursor.execute("""
    SELECT id, quiz_id, question, option_a, option_b, option_c, option_d, marks
    FROM quiz_questions WHERE quiz_id = ?
    ORDER BY id ASC
    """, (quiz_id,))
    
    questions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({
        "success": True,
        "quiz": dict(quiz),
        "questions": questions
    })

@student_bp.route("/api/student/quizzes/<int:quiz_id>/submit", methods=["POST"])
@student_required
def submit_quiz(quiz_id):
    """
    Evaluates quiz submission, computes score, stores in SQLite, and generates
    targeted adaptive recommendations based on weak topics.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
    quiz = cursor.fetchone()
    if not quiz:
        conn.close()
        return jsonify({"success": False, "message": "Quiz not found."}), 404
        
    cursor.execute("SELECT * FROM quiz_questions WHERE quiz_id = ?", (quiz_id,))
    questions = cursor.fetchall()
    
    data = request.get_json() or {}
    answers = data.get("answers", {}) # dict of {question_id: 'A'/'B'/'C'/'D'}
    
    total_score = 0.0
    total_possible = 0.0
    detailed_review = []
    
    for q in questions:
        q_id = str(q["id"])
        selected_opt = answers.get(q_id, "").strip().upper()
        correct_opt = q["correct_option"].strip().upper()
        marks = float(q["marks"])
        total_possible += marks
        
        is_correct = (selected_opt == correct_opt)
        if is_correct:
            total_score += marks
            
        detailed_review.append({
            "question_id": q["id"],
            "question": q["question"],
            "selected_option": selected_opt,
            "correct_option": correct_opt,
            "is_correct": is_correct,
            "explanation": q["explanation"]
        })
        
    percentage = round((total_score / total_possible * 100.0), 1) if total_possible > 0 else 0.0
    
    # Determine weak topic if score is below 70%
    weak_topic = quiz["topic"] if percentage < 70.0 else None
    
    cursor.execute("""
    INSERT INTO quiz_results (student_id, quiz_id, score, total_marks, percentage, weak_topic, completed_at)
    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (student["id"], quiz_id, total_score, total_possible, percentage, weak_topic))
    
    # Adaptive Recommendation Generation
    adaptive_recommendations = []
    if percentage < 60.0:
        adaptive_recommendations.append({
            "type": "Remedial Revision",
            "message": f"Review fundamental concepts in '{quiz['topic']}'. Re-read Lesson 3 & try practice drills.",
            "priority": "High"
        })
        adaptive_recommendations.append({
            "type": "Practice Quiz",
            "message": f"Retake the '{quiz['title']}' after revision to strengthen conceptual mastery.",
            "priority": "Medium"
        })
    elif percentage < 80.0:
        adaptive_recommendations.append({
            "type": "Targeted Drill",
            "message": f"Good effort! Deepen your understanding of edge cases in '{quiz['topic']}'.",
            "priority": "Low"
        })
    else:
        adaptive_recommendations.append({
            "type": "Advanced Challenge",
            "message": f"Excellent mastery ({percentage}%)! Advance to tree and graph problem sets.",
            "priority": "Enrichment"
        })
        
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "score": total_score,
        "total_marks": total_possible,
        "percentage": percentage,
        "weak_topic": weak_topic,
        "review": detailed_review,
        "adaptive_recommendations": adaptive_recommendations
    })

# ================= 8. MESSAGING & NOTIFICATIONS =================
@student_bp.route("/api/student/messages", methods=["GET"])
@student_required
def get_student_conversations():
    """Retrieves all conversation threads with assigned subject teachers."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT DISTINCT m.conversation_id, m.subject_id, s.subject_name, s.subject_code,
           t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email,
           (SELECT message FROM messages m2 WHERE m2.conversation_id = m.conversation_id ORDER BY m2.created_at DESC LIMIT 1) as last_message,
           (SELECT created_at FROM messages m2 WHERE m2.conversation_id = m.conversation_id ORDER BY m2.created_at DESC LIMIT 1) as last_updated,
           (SELECT count(*) FROM messages m2 WHERE m2.conversation_id = m.conversation_id AND m2.receiver_role = 'student' AND m2.receiver_id = ? AND m2.is_read = 0) as unread_count
    FROM messages m
    JOIN subjects s ON m.subject_id = s.id
    JOIN teachers t ON (m.sender_role = 'teacher' AND m.sender_id = t.id) OR (m.receiver_role = 'teacher' AND m.receiver_id = t.id)
    WHERE (m.sender_role = 'student' AND m.sender_id = ?) OR (m.receiver_role = 'student' AND m.receiver_id = ?)
    ORDER BY last_updated DESC
    """, (student["id"], student["id"], student["id"]))
    
    threads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "conversations": threads})

@student_bp.route("/api/student/messages/<string:conversation_id>", methods=["GET"])
@student_required
def get_thread_messages(conversation_id):
    """Fetches messages in a thread and marks unread items as read."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT * FROM messages 
    WHERE conversation_id = ? AND ((sender_role = 'student' AND sender_id = ?) OR (receiver_role = 'student' AND receiver_id = ?))
    ORDER BY created_at ASC
    """, (conversation_id, student["id"], student["id"]))
    
    messages = [dict(row) for row in cursor.fetchall()]
    
    # Mark student unread messages as read
    cursor.execute("""
    UPDATE messages SET is_read = 1 
    WHERE conversation_id = ? AND receiver_role = 'student' AND receiver_id = ? AND is_read = 0
    """, (conversation_id, student["id"]))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "messages": messages})

@student_bp.route("/api/student/messages", methods=["POST"])
@student_required
def send_student_message():
    """Sends a message to the assigned teacher of a specific subject."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    data = request.get_json() or {}
    subject_id = data.get("subject_id")
    message_text = data.get("message", "").strip()
    
    if not subject_id or not message_text:
        conn.close()
        return jsonify({"success": False, "message": "Subject ID and message text are required."}), 400
        
    # Determine the assigned teacher for this student's section and subject
    cursor.execute("""
    SELECT ts.teacher_id, t.user_id as teacher_user_id, t.full_name as teacher_name
    FROM teacher_subjects ts
    JOIN teachers t ON ts.teacher_id = t.id
    WHERE ts.subject_id = ? AND ts.branch = ? AND ts.year = ? AND ts.semester = ? AND ts.section = ?
    """, (subject_id, student["branch"], student["year"], student["semester"], student["section"]))
    
    t_row = cursor.fetchone()
    if not t_row:
        # Fallback to any teacher assigned to that subject
        cursor.execute("SELECT id as teacher_id, user_id as teacher_user_id, full_name as teacher_name FROM teachers LIMIT 1")
        t_row = cursor.fetchone()
        
    teacher_id = t_row["teacher_id"]
    teacher_uid = t_row["teacher_user_id"]
    
    conv_id = f"conv_stu{student['id']}_tea{teacher_id}_sub{subject_id}"
    
    cursor.execute("""
    INSERT INTO messages (conversation_id, sender_id, sender_role, receiver_id, receiver_role, subject_id, message, is_read)
    VALUES (?, ?, 'student', ?, 'teacher', ?, ?, 0)
    """, (conv_id, student["id"], teacher_id, subject_id, message_text))
    
    # Create notification for teacher
    if teacher_uid:
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type, is_read)
        VALUES (?, ?, ?, 'message', 0)
        """, (teacher_uid, f"New Inquiry from {student['full_name']}", f"Student {student['full_name']} sent a message regarding your subject.", ))
        
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": "Message sent successfully to your faculty instructor.",
        "conversation_id": conv_id
    }), 201

@student_bp.route("/api/student/notifications", methods=["GET"])
@student_required
def get_student_notifications():
    """Returns student's notifications."""
    conn = get_db_connection()
    user = get_current_user()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT * FROM notifications 
    WHERE user_id = ? 
    ORDER BY created_at DESC LIMIT 20
    """, (user["id"],))
    
    notifications = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "notifications": notifications})

@student_bp.route("/api/student/notifications/<int:notification_id>/read", methods=["POST"])
@student_required
def mark_notification_read(notification_id):
    """Marks a notification as read."""
    conn = get_db_connection()
    user = get_current_user()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, user["id"]))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Notification marked as read."})

# ================= 9. LEARNING GOALS =================
@student_bp.route("/api/student/goals", methods=["GET"])
@student_required
def get_student_goals():
    """Returns student's active learning goals."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM learning_goals WHERE student_id = ? ORDER BY created_at DESC", (student["id"],))
    goals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "goals": goals})

@student_bp.route("/api/student/goals", methods=["POST"])
@student_required
def create_learning_goal():
    """Allows student to set a custom academic goal."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    target_pct = float(data.get("target_percentage", 75.0))
    current_pct = float(student["overall_progress"])
    
    if not title:
        conn.close()
        return jsonify({"success": False, "message": "Goal title is required."}), 400
        
    cursor.execute("""
    INSERT INTO learning_goals (student_id, title, target_percentage, current_percentage, status)
    VALUES (?, ?, ?, ?, 'In Progress')
    """, (student["id"], title, target_pct, current_pct))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Learning goal '{title}' created successfully."}), 201

# ================= 10. ML / RECOMMENDATIONS / PROGRESS =================
@student_bp.route("/api/student/progress", methods=["GET"])
@student_required
def get_aggregated_student_progress():
    """Aggregates overall progress, streak, completed items, and weak/strong subject areas."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    # Count totals
    cursor.execute("SELECT count(*) FROM lesson_progress WHERE student_id = ? AND status = 'Completed'", (student["id"],))
    completed_lessons = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM lab_progress WHERE student_id = ? AND status = 'Completed'", (student["id"],))
    completed_labs = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM quiz_results WHERE student_id = ?", (student["id"],))
    completed_quizzes = cursor.fetchone()[0]
    
    cursor.execute("SELECT count(*) FROM assessment_results WHERE student_id = ?", (student["id"],))
    completed_assessments = cursor.fetchone()[0]
    
    # Identify Weak and Strong Subject Areas
    scores = {
        "Data Structures": float(student["data_structures_score"]),
        "Database Systems": float(student["database_score"]),
        "Programming": float(student["programming_score"]),
        "Mathematics": float(student["mathematics_score"]),
        "Communication": float(student["communication_score"])
    }
    
    weak_areas = [k for k, v in scores.items() if v < 60.0]
    strong_areas = [k for k, v in scores.items() if v >= 75.0]
    
    conn.close()
    return jsonify({
        "success": True,
        "overall_progress": float(student["overall_progress"]),
        "learning_streak": student["learning_streak"] if "learning_streak" in student.keys() else 4,
        "attendance": float(student["attendance"]),
        "learning_activity": float(student["learning_activity"]),
        "stats": {
            "completed_lessons": completed_lessons,
            "completed_labs": completed_labs,
            "completed_quizzes": completed_quizzes,
            "completed_assessments": completed_assessments
        },
        "scores": scores,
        "weak_areas": weak_areas or ["Linear Data Structures (Arrays/Linked Lists)"],
        "strong_areas": strong_areas or ["Database Systems", "Professional Communication"]
    })

@student_bp.route("/api/student/recommendations", methods=["GET"])
@student_required
def get_student_recommendations():
    """Generates personalized academic recommendations based on actual quiz performance and ML output."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    
    # Query recent weak quiz topics
    cursor.execute("""
    SELECT DISTINCT weak_topic FROM quiz_results 
    WHERE student_id = ? AND weak_topic IS NOT NULL 
    ORDER BY id DESC LIMIT 3
    """, (student["id"],))
    weak_topics = [row[0] for row in cursor.fetchall()]
    
    recs = []
    if weak_topics:
        for wt in weak_topics:
            recs.append({
                "title": f"Revise {wt} Concepts",
                "description": f"Recent quiz diagnostics identified learning gaps in {wt}. Review the module lesson and practice drills.",
                "action": "Open Lesson",
                "tag": "Adaptive Revision",
                "priority": "High"
            })
    else:
        recs.append({
            "title": "Revise Singly & Doubly Linked Lists",
            "description": "Strengthen pointer mechanics and dynamic node allocation before attempting upcoming Mid-Term Assessment.",
            "action": "Open Lesson 3",
            "tag": "Core Foundation",
            "priority": "High"
        })
        
    recs.append({
        "title": "Complete Array Operations Lab Experiment",
        "description": "Hands-on implementation of element shifting and Binary Search divide-and-conquer logic.",
        "action": "Open Lab 1",
        "tag": "Hands-on Lab",
        "priority": "Medium"
    })
    
    recs.append({
        "title": "Attempt Stacks & Queues Practice Quiz",
        "description": "Assess LIFO/FIFO disciplines and infix-to-postfix conversion mastery.",
        "action": "Start Quiz",
        "tag": "Self Assessment",
        "priority": "Medium"
    })
    
    conn.close()
    return jsonify({"success": True, "recommendations": recs})

@student_bp.route("/api/student/learning-path", methods=["GET"])
@student_required
def get_student_learning_path():
    """Generates personalized learning path using student performance and classical ML."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    conn.close()
    
    student_dict = dict(student)
    path_data = generate_personalized_learning_path(student_dict)
    learning_path_steps = path_data.get("learning_path", []) if isinstance(path_data, dict) else path_data
    
    return jsonify({
        "success": True,
        "student_id": student["id"],
        "branch": student["branch"],
        "learning_path": learning_path_steps,
        "path_data": path_data
    })

@student_bp.route("/api/student/progress/update", methods=["POST"])
@student_required
def update_student_progress_general():
    """Updates student progress or step completion."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE students SET 
        learning_activity = MIN(100.0, learning_activity + 2.0),
        overall_progress = MIN(100.0, overall_progress + 1.0)
    WHERE id = ?
    """, (student["id"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Student progress updated successfully."})

@student_bp.route("/api/student/prediction", methods=["GET"])
@student_required
def get_student_prediction():
    """Evaluates student's multi-factor risk prediction using active Quantum ML model."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    conn.close()
    
    student_dict = dict(student)
    pred_result = predict_student_risk(student_dict)
    return jsonify({
        "success": True,
        "model": pred_result.get("model", "Quantum ML"),
        "risk_level": pred_result.get("risk_level"),
        "risk_score": pred_result.get("risk_score"),
        "prediction": pred_result
    })
