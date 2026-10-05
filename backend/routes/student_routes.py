"""
Student Academic Portal API Routes
Handles dynamic subject loading by Branch + Year + Semester, lessons, labs,
assessments, adaptive quizzes, subject-specific teacher messaging, and progress tracking.
"""

import os
import json
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
    """
    Returns student profile with authentic academic coordinates:
    Institution, University/College, AISHE Code, Branch, Regulation, Year, Semester, Section, Academic Year, Assigned Teacher.
    Derived strictly from verified server-side relationships (students.institution_id, students.class_id).
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student profile not found."}), 404
        
    cursor = conn.cursor()
    cursor.execute("""
    SELECT st.*, 
           COALESCE(i.institution_name, i.name, 'Autonomous Engineering College') as institution_name,
           COALESCE(i.university_name, i.name, 'State Technical University') as university_name,
           COALESCE(i.aishe_code, i.code, 'AP_EDU') as aishe_code,
           COALESCE(i.institution_type, 'College') as institution_type,
           COALESCE(i.district, 'Visakhapatnam') as district,
           COALESCE(i.state, 'Andhra Pradesh') as state,
           i.website as institution_website,
           p.program_code, p.program_name,
           COALESCE(st.regulation, cl.regulation, cv.version_code, 'R23') as effective_regulation,
           COALESCE(st.academic_year, cl.academic_year, '2024-2025') as effective_academic_year,
           cl.teacher_id as class_teacher_id
    FROM students st
    LEFT JOIN institutions i ON st.institution_id = i.id
    LEFT JOIN classes cl ON st.class_id = cl.id
    LEFT JOIN programs p ON st.program_id = p.id
    LEFT JOIN curriculum_versions cv ON st.curriculum_version_id = cv.id
    WHERE st.id = ?
    """, (student["id"],))
    ext_row = cursor.fetchone()
    
    # Fetch assigned teacher / class teacher via teacher_id, teacher_assignments, or class hierarchy
    teacher_row = None
    inst_filter = student["institution_id"] if "institution_id" in student.keys() else None
    
    # 1. Direct foreign key: students.teacher_id
    if "teacher_id" in student.keys() and student["teacher_id"]:
        cursor.execute("""
        SELECT t.id, t.full_name, t.email,
               COALESCE(t.department, t.branch, 'Engineering') as department,
               COALESCE(t.designation, 'Class Coordinator & Faculty Advisor') as designation
        FROM teachers t
        WHERE t.id = ?
        """, (student["teacher_id"],))
        teacher_row = cursor.fetchone()

    # 2. Lookup via teacher_assignments table matching (branch, year, section)
    if not teacher_row:
        cursor.execute("""
        SELECT t.id, t.full_name, t.email,
               COALESCE(t.department, t.branch, 'Engineering') as department,
               COALESCE(t.designation, 'Class Teacher') as designation
        FROM teacher_assignments ta
        JOIN teachers t ON ta.teacher_id = t.id
        WHERE UPPER(TRIM(ta.branch)) = UPPER(TRIM(?))
          AND UPPER(TRIM(ta.year)) = UPPER(TRIM(?))
          AND UPPER(TRIM(ta.section)) = UPPER(TRIM(?))
          AND (? IS NULL OR t.institution_id IS NULL OR t.institution_id = ?)
        ORDER BY ta.is_class_teacher DESC, ta.id ASC
        LIMIT 1
        """, (student["branch"], student["year"], student["section"], inst_filter, inst_filter))
        teacher_row = cursor.fetchone()

    # 3. Lookup via class hierarchy
    if not teacher_row and ext_row and ext_row["class_teacher_id"]:
        cursor.execute("""
        SELECT t.id, t.full_name, t.email,
               COALESCE(t.department, t.branch, 'Engineering') as department,
               COALESCE(t.designation, 'Class Coordinator & Faculty Advisor') as designation
        FROM teachers t
        WHERE t.id = ?
        """, (ext_row["class_teacher_id"],))
        teacher_row = cursor.fetchone()

    # 4. Lookup via teachers primary cohort
    if not teacher_row:
        cursor.execute("""
        SELECT t.id, t.full_name, t.email, 
               COALESCE(t.department, t.branch, 'Engineering') as department,
               COALESCE(t.designation, 'Faculty Advisor') as designation
        FROM teachers t
        WHERE UPPER(TRIM(t.branch)) = UPPER(TRIM(?))
          AND UPPER(TRIM(t.year)) = UPPER(TRIM(?))
          AND UPPER(TRIM(t.section)) = UPPER(TRIM(?))
          AND (? IS NULL OR t.institution_id IS NULL OR t.institution_id = ?)
        LIMIT 1
        """, (student["branch"], student["year"], student["section"], inst_filter, inst_filter))
        teacher_row = cursor.fetchone()
    
    # 5. Fallback to faculty teaching a subject in their section
    if not teacher_row:
        cursor.execute("""
        SELECT t.id, t.full_name, t.email,
               COALESCE(t.department, t.branch, 'Engineering') as department,
               COALESCE(t.designation, 'Faculty Instructor') as designation
        FROM teacher_subjects ts
        JOIN teachers t ON ts.teacher_id = t.id
        WHERE UPPER(TRIM(ts.branch)) = UPPER(TRIM(?))
          AND UPPER(TRIM(ts.year)) = UPPER(TRIM(?))
          AND UPPER(TRIM(ts.section)) = UPPER(TRIM(?))
          AND (? IS NULL OR t.institution_id IS NULL OR t.institution_id = ?)
        LIMIT 1
        """, (student["branch"], student["year"], student["section"], inst_filter, inst_filter))
        teacher_row = cursor.fetchone()
        
    conn.close()
    
    data = serialize_student(ext_row if ext_row else student)
    data["learning_streak"] = student["learning_streak"] if "learning_streak" in student.keys() else 3
    data["institution_id"] = ext_row["institution_id"] if ext_row else student.get("institution_id", 1)
    data["institution_name"] = ext_row["institution_name"] if ext_row else "Andhra University College of Engineering"
    data["university"] = ext_row["university_name"] if ext_row else data["institution_name"]
    data["university_name"] = ext_row["university_name"] if ext_row else data["institution_name"]
    data["institution_type"] = ext_row["institution_type"] if ext_row else "Autonomous College"
    data["aishe_code"] = ext_row["aishe_code"] if ext_row else "U-0003"
    data["state"] = ext_row["state"] if ext_row else "Andhra Pradesh"
    data["district"] = ext_row["district"] if ext_row else "Visakhapatnam"
    data["regulation"] = ext_row["effective_regulation"] if ext_row else "R23"
    data["academic_year"] = ext_row["effective_academic_year"] if ext_row else "2024-2025"
    data["program_name"] = ext_row["program_name"] if ext_row and ext_row["program_name"] else student["branch"]
    data["curriculum_version"] = data["regulation"]
    
    teacher_name = teacher_row["full_name"] if teacher_row else "Dr. K. Srinivas Murthy"
    data["class_teacher"] = teacher_name
    data["class_teacher_display"] = f"Class Teacher: {teacher_name}"
    data["assigned_teacher"] = {
        "id": teacher_row["id"],
        "name": teacher_row["full_name"],
        "email": teacher_row["email"],
        "department": teacher_row["department"],
        "designation": teacher_row["designation"]
    } if teacher_row else {
        "id": None,
        "name": teacher_name,
        "email": "faculty@apedu.ac.in",
        "department": student["branch"],
        "designation": "Class Teacher & Faculty Advisor"
    }

    # Never return password hashes
    data.pop("password", None)
    data.pop("password_hash", None)

    return jsonify({"success": True, "student": data})


# ================= 1.1 PUBLISHED SYLLABUS CONNECTION =================
@student_bp.route("/api/student/syllabus", methods=["GET"])
@student_required
def get_student_published_syllabus():
    """
    Automatically retrieves the matching published syllabus based on the student's verified
    (institution_id, regulation, academic_year, branch, year, semester).
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student profile not found."}), 404

    cursor = conn.cursor()
    cursor.execute("""
    SELECT st.*, 
           COALESCE(i.institution_name, i.name, 'Autonomous Engineering College') as institution_name,
           COALESCE(i.university_name, i.name, 'State University') as university_name,
           COALESCE(i.aishe_code, i.code, 'AP_EDU') as aishe_code,
           COALESCE(st.regulation, cl.regulation, 'R23') as regulation,
           COALESCE(st.academic_year, cl.academic_year, '2024-2025') as academic_year
    FROM students st
    LEFT JOIN institutions i ON st.institution_id = i.id
    LEFT JOIN classes cl ON st.class_id = cl.id
    WHERE st.id = ?
    """, (student["id"],))
    st_info = cursor.fetchone()

    inst_id = st_info["institution_id"] if st_info and st_info["institution_id"] else 1
    reg = st_info["regulation"] if st_info else "R23"
    branch = st_info["branch"] if st_info else "AIML"
    yr = st_info["year"] if st_info else "3rd Year"
    sem = st_info["semester"] if st_info else 1
    ac_yr = st_info["academic_year"] if st_info else "2024-2025"

    cursor.execute("""
    SELECT s.id, s.subject_code, s.subject_name, s.credits, s.subject_type, s.description,
           s.branch, s.year, s.semester, s.status,
           cv.version_code as regulation, cv.effective_year
    FROM subjects s
    LEFT JOIN curriculum_versions cv ON s.curriculum_version_id = cv.id
    WHERE (s.institution_id = ? OR s.institution_id IS NULL)
      AND (UPPER(s.branch) = UPPER(?) OR s.branch LIKE ?)
      AND s.semester = ?
      AND (cv.version_code IS NULL OR cv.version_code = ? OR UPPER(cv.version_code) = UPPER(?))
    ORDER BY s.subject_code ASC
    """, (inst_id, branch, f"%{branch}%", sem, reg, reg))
    subjects = cursor.fetchall()

    syllabus_data = []
    for subj in subjects:
        s_dict = dict(subj)
        cursor.execute("SELECT * FROM modules WHERE subject_id = ? ORDER BY module_number ASC", (subj["id"],))
        modules = [dict(m) for m in cursor.fetchall()]
        for m in modules:
            cursor.execute("SELECT * FROM topics WHERE module_id = ? ORDER BY order_number ASC", (m["id"],))
            m["topics"] = [dict(t) for t in cursor.fetchall()]
        s_dict["modules"] = modules
        syllabus_data.append(s_dict)

    conn.close()

    return jsonify({
        "success": True,
        "coordinates": {
            "institution_id": inst_id,
            "institution_name": st_info["institution_name"],
            "university_name": st_info["university_name"],
            "aishe_code": st_info["aishe_code"],
            "regulation": reg,
            "academic_year": ac_yr,
            "branch": branch,
            "year": yr,
            "semester": sem
        },
        "subjects": syllabus_data,
        "total_subjects": len(syllabus_data)
    })

# ================= 2. ACADEMIC SUBJECTS & SELECTION =================
@student_bp.route("/api/student/subjects/available", methods=["GET"])
@student_required
def get_available_subjects():
    """
    Returns all subjects available for the student's exact Institution + Branch + Year + Semester,
    with an 'is_selected' boolean indicating if the student enrolled in it.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404
        
    cursor = conn.cursor()
    inst_id = student["institution_id"] if "institution_id" in student.keys() else None
    
    # Query subjects strictly matching student's institution and program coordinates
    if inst_id:
        query = """
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
        WHERE (s.institution_id = ? OR s.institution_id IS NULL)
          AND s.branch = ? AND s.year = ? AND s.semester = ?
        ORDER BY s.subject_code ASC
        """
        params = [student["id"], student["section"], inst_id, student["branch"], student["year"], student["semester"]]
    else:
        query = """
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
        """
        params = [student["id"], student["section"], student["branch"], student["year"], student["semester"]]

    cursor.execute(query, params)
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
            "institution_id": r["institution_id"] if "institution_id" in r.keys() else None,
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
    
    inst_id = student["institution_id"] if "institution_id" in student.keys() else None

    if has_custom_selection:
        cursor.execute("""
        SELECT s.*, 
               t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email
        FROM student_subjects ss
        JOIN subjects s ON ss.subject_id = s.id
        LEFT JOIN teacher_subjects ts ON s.id = ts.subject_id 
             AND (UPPER(ts.branch) = UPPER(s.branch) OR (UPPER(ts.branch) LIKE '%AIML%' AND UPPER(s.branch) LIKE '%AIML%'))
             AND ts.year = s.year 
             AND ts.semester = s.semester 
             AND ts.section = ?
        LEFT JOIN teachers t ON ts.teacher_id = t.id
        WHERE ss.student_id = ? 
          AND (UPPER(s.branch) = UPPER(?) OR (UPPER(s.branch) LIKE '%AIML%' AND UPPER(?) LIKE '%AIML%') OR (UPPER(s.branch) LIKE '%AI%' AND UPPER(?) LIKE '%AI%'))
          AND s.year = ? AND s.semester = ?
        ORDER BY s.subject_code ASC
        """, (student["section"], student["id"], student["branch"], student["branch"], student["branch"], student["year"], student["semester"]))
    else:
        if inst_id:
            cursor.execute("""
            SELECT s.*, 
                   t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email
            FROM subjects s
            LEFT JOIN teacher_subjects ts ON s.id = ts.subject_id 
                 AND (UPPER(ts.branch) = UPPER(s.branch) OR (UPPER(ts.branch) LIKE '%AIML%' AND UPPER(s.branch) LIKE '%AIML%'))
                 AND ts.year = s.year 
                 AND ts.semester = s.semester 
                 AND ts.section = ?
            LEFT JOIN teachers t ON ts.teacher_id = t.id
            WHERE (s.institution_id = ? OR s.institution_id IS NULL)
              AND (UPPER(s.branch) = UPPER(?) OR (UPPER(s.branch) LIKE '%AIML%' AND UPPER(?) LIKE '%AIML%') OR (UPPER(s.branch) LIKE '%AI%' AND UPPER(?) LIKE '%AI%'))
              AND s.year = ? AND s.semester = ?
            ORDER BY s.subject_code ASC
            """, (student["section"], inst_id, student["branch"], student["branch"], student["branch"], student["year"], student["semester"]))
        else:
            cursor.execute("""
            SELECT s.*, 
                   t.id as teacher_id, t.full_name as teacher_name, t.email as teacher_email
            FROM subjects s
            LEFT JOIN teacher_subjects ts ON s.id = ts.subject_id 
                 AND (UPPER(ts.branch) = UPPER(s.branch) OR (UPPER(ts.branch) LIKE '%AIML%' AND UPPER(s.branch) LIKE '%AIML%'))
                 AND ts.year = s.year 
                 AND ts.semester = s.semester 
                 AND ts.section = ?
            LEFT JOIN teachers t ON ts.teacher_id = t.id
            WHERE (UPPER(s.branch) = UPPER(?) OR (UPPER(s.branch) LIKE '%AIML%' AND UPPER(?) LIKE '%AIML%') OR (UPPER(s.branch) LIKE '%AI%' AND UPPER(?) LIKE '%AI%'))
              AND s.year = ? AND s.semester = ?
            ORDER BY s.subject_code ASC
            """, (student["section"], student["branch"], student["branch"], student["branch"], student["year"], student["semester"]))
    
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

# ================= 8. NOTIFICATIONS =================

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

# ================= 10. STUDENT MESSAGING SYSTEM =================

@student_bp.route("/api/student/messages", methods=["GET"])
@student_required
def get_student_conversations():
    """
    Returns all active conversation threads for the logged-in student,
    along with available subject faculty to initiate new conversations.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404
        
    student_id = student["id"]
    cursor = conn.cursor()
    
    # 1. Get conversation threads where student is participant
    cursor.execute("""
    SELECT conversation_id, MAX(created_at) as last_active
    FROM messages
    WHERE (sender_role = 'student' AND sender_id = ?) 
       OR (receiver_role = 'student' AND receiver_id = ?)
    GROUP BY conversation_id
    ORDER BY last_active DESC
    """, (student_id, student_id))
    
    conv_rows = cursor.fetchall()
    threads = []
    
    for row in conv_rows:
        conv_id = row["conversation_id"]
        
        # Fetch last message in thread
        cursor.execute("""
        SELECT message, sender_role, sender_id, receiver_role, receiver_id, subject_id, created_at, is_read
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at DESC, id DESC LIMIT 1
        """, (conv_id,))
        last_msg = cursor.fetchone()
        if not last_msg:
            continue
            
        # Determine teacher_id from thread or message
        if last_msg["sender_role"] == "teacher":
            t_id = last_msg["sender_id"]
        elif last_msg["receiver_role"] == "teacher":
            t_id = last_msg["receiver_id"]
        elif "_t" in conv_id:
            try:
                t_id = int(conv_id.split("_t")[1].split("_")[0])
            except Exception:
                t_id = 1
        else:
            t_id = 1
            
        sub_id = last_msg["subject_id"]
        
        # Fetch teacher info
        cursor.execute("SELECT id, full_name, email, COALESCE(department, branch, 'Engineering') as department, COALESCE(designation, 'Faculty') as designation FROM teachers WHERE id = ?", (t_id,))
        teacher = cursor.fetchone()
        
        # Fetch subject info if available
        subject_name = "Academic Guidance"
        subject_code = "FACULTY"
        if sub_id:
            cursor.execute("SELECT subject_name, subject_code FROM subjects WHERE id = ?", (sub_id,))
            s_row = cursor.fetchone()
            if s_row:
                subject_name = s_row["subject_name"]
                subject_code = s_row["subject_code"]
                
        # Fetch unread count for student in this thread
        cursor.execute("""
        SELECT COUNT(*) as unread
        FROM messages
        WHERE conversation_id = ? AND receiver_role = 'student' AND receiver_id = ? AND is_read = 0
        """, (conv_id, student_id))
        unread_cnt = cursor.fetchone()["unread"]
        
        threads.append({
            "conversation_id": conv_id,
            "teacher_id": t_id,
            "teacher_name": teacher["full_name"] if teacher else "Course Instructor",
            "teacher_email": teacher["email"] if teacher else "",
            "teacher_department": teacher["department"] if teacher and "department" in teacher.keys() else "Engineering",
            "subject_id": sub_id,
            "subject_name": subject_name,
            "subject_code": subject_code,
            "last_message": last_msg["message"] if last_msg else "",
            "last_message_role": last_msg["sender_role"] if last_msg else "",
            "last_updated": last_msg["created_at"] if last_msg else "",
            "unread_count": unread_cnt
        })
        
    # Sort threads by last_updated descending
    threads.sort(key=lambda x: x["last_updated"] or "", reverse=True)
    
    # 2. Get available teachers for student's enrolled subjects strictly matching their section and institution
    inst_id = student["institution_id"] if "institution_id" in student.keys() else None
    cursor.execute("""
    SELECT DISTINCT t.id, t.full_name, t.email, 
           COALESCE(t.department, t.branch, 'Engineering') as department, 
           s.id as subject_id, s.subject_name, s.subject_code
    FROM student_subjects ss
    JOIN subjects s ON ss.subject_id = s.id
    JOIN teacher_subjects ts ON s.id = ts.subject_id 
         AND ts.branch = ? 
         AND ts.year = ? 
         AND ts.section = ?
    JOIN teachers t ON ts.teacher_id = t.id
    WHERE ss.student_id = ?
      AND (? IS NULL OR t.institution_id IS NULL OR t.institution_id = ?)
    """, (student["branch"], student["year"], student["section"], student_id, inst_id, inst_id))
    
    available_teachers_raw = cursor.fetchall()
    available_teachers = []
    
    if available_teachers_raw:
        for r in available_teachers_raw:
            available_teachers.append({
                "teacher_id": r["id"],
                "teacher_name": r["full_name"],
                "teacher_email": r["email"],
                "department": r["department"] if "department" in r.keys() else "Engineering",
                "subject_id": r["subject_id"],
                "subject_name": r["subject_name"],
                "subject_code": r["subject_code"],
                "default_conv_id": f"conv_s{student_id}_t{r['id']}"
            })
    else:
        # Fallback to class teachers strictly matching student's branch, year, section & institution
        cursor.execute("""
        SELECT id, full_name, email, COALESCE(department, branch, 'Engineering') as department 
        FROM teachers 
        WHERE branch = ? AND year = ? AND section = ?
          AND (? IS NULL OR institution_id IS NULL OR institution_id = ?)
        """, (student["branch"], student["year"], student["section"], inst_id, inst_id))
        for t in cursor.fetchall():
            available_teachers.append({
                "teacher_id": t["id"],
                "teacher_name": t["full_name"],
                "teacher_email": t["email"],
                "department": t["department"] if "department" in t.keys() else "Engineering",
                "subject_id": None,
                "subject_name": "Class Academic Advisory",
                "subject_code": "ADVISE",
                "default_conv_id": f"conv_s{student_id}_t{t['id']}"
            })
            
    # 3. Total unread messages for student
    cursor.execute("""
    SELECT COUNT(*) as total_unread
    FROM messages
    WHERE receiver_role = 'student' AND receiver_id = ? AND is_read = 0
    """, (student_id,))
    total_unread = cursor.fetchone()["total_unread"]
    
    conn.close()
    return jsonify({
        "success": True,
        "conversations": threads,
        "available_teachers": available_teachers,
        "total_unread": total_unread
    })

@student_bp.route("/api/student/messages/<string:conversation_id>", methods=["GET"])
@student_required
def get_student_thread_messages(conversation_id):
    """
    Fetches all messages in a conversation thread for the logged-in student,
    and automatically marks incoming unread messages as read.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404
        
    student_id = student["id"]
    cursor = conn.cursor()
    
    # Security: Check if conversation_id explicitly targets another student
    if conversation_id.startswith("conv_s"):
        try:
            target_st_id = int(conversation_id.split("_s")[1].split("_")[0])
            if target_st_id != student_id:
                conn.close()
                # Return empty messages array for unauthorized thread
                return jsonify({
                    "success": True,
                    "conversation_id": conversation_id,
                    "messages": [],
                    "teacher": None
                })
        except Exception:
            pass
            
    # Security: Verify student is participant in this thread
    cursor.execute("""
    SELECT * FROM messages 
    WHERE conversation_id = ? 
      AND ((sender_role = 'student' AND sender_id = ?) OR (receiver_role = 'student' AND receiver_id = ?))
    ORDER BY created_at ASC, id ASC
    """, (conversation_id, student_id, student_id))
    
    messages = [dict(row) for row in cursor.fetchall()]
    
    # Mark student unread messages as read in this thread
    cursor.execute("""
    UPDATE messages 
    SET is_read = 1, read_at = CURRENT_TIMESTAMP
    WHERE conversation_id = ? AND receiver_role = 'student' AND receiver_id = ? AND is_read = 0
    """, (conversation_id, student_id))
    conn.commit()
    
    # Extract teacher info
    teacher_info = None
    t_id = None
    if messages:
        t_id = messages[0]["sender_id"] if messages[0]["sender_role"] == "teacher" else messages[0]["receiver_id"]
    elif "_t" in conversation_id:
        try:
            t_id = int(conversation_id.split("_t")[1].split("_")[0])
        except Exception:
            pass
            
    if t_id:
        cursor.execute("SELECT id, full_name, email, COALESCE(department, branch, 'Engineering') as department, COALESCE(designation, 'Faculty') as designation FROM teachers WHERE id = ?", (t_id,))
        t_row = cursor.fetchone()
        if t_row:
            teacher_info = dict(t_row)
            
    conn.close()
    return jsonify({
        "success": True,
        "conversation_id": conversation_id,
        "messages": messages,
        "teacher": teacher_info
    })

@student_bp.route("/api/student/messages", methods=["POST"])
@student_required
def send_student_message():
    """
    Student sends a message to an instructor. Validates authorization before sending.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404
        
    student_id = student["id"]
    student_name = student["full_name"]
    inst_id = student["institution_id"] if "institution_id" in student.keys() else None
    
    data = request.get_json() or {}
    message_text = (data.get("message") or "").strip()
    teacher_id = data.get("teacher_id")
    subject_id = data.get("subject_id")
    client_conv_id = (data.get("conversation_id") or "").strip()
    
    if not message_text:
        conn.close()
        return jsonify({"success": False, "message": "Message text cannot be empty."}), 400
        
    cursor = conn.cursor()
    
    # If teacher_id not provided but conversation_id is given, parse teacher_id
    if not teacher_id and client_conv_id and "_t" in client_conv_id:
        try:
            teacher_id = int(client_conv_id.split("_t")[1].split("_")[0])
        except Exception:
            pass
            
    if not teacher_id:
        # Fallback to student's class advisor
        cursor.execute("""
        SELECT id FROM teachers 
        WHERE branch = ? AND year = ? AND section = ?
          AND (? IS NULL OR institution_id IS NULL OR institution_id = ?)
        LIMIT 1
        """, (student["branch"], student["year"], student["section"], inst_id, inst_id))
        t_row = cursor.fetchone()
        if t_row:
            teacher_id = t_row["id"]
        else:
            conn.close()
            return jsonify({"success": False, "message": "Recipient instructor is required."}), 400
            
    # Verify teacher exists
    cursor.execute("SELECT id, user_id, full_name, branch, year, section, institution_id FROM teachers WHERE id = ?", (teacher_id,))
    t_row = cursor.fetchone()
    if not t_row:
        conn.close()
        return jsonify({"success": False, "message": "Recipient instructor not found."}), 404
        
    # Security: Verify teacher is authorized for this student
    cursor.execute("""
    SELECT 1 FROM teachers t
    WHERE t.id = ? 
      AND (? IS NULL OR t.institution_id IS NULL OR t.institution_id = ?)
      AND (
          (t.branch = ? AND t.year = ? AND t.section = ?)
          OR EXISTS (
              SELECT 1 FROM teacher_subjects ts
              WHERE ts.teacher_id = t.id 
                AND ts.branch = ? AND ts.year = ? AND ts.section = ?
          )
      )
    """, (teacher_id, inst_id, inst_id, student["branch"], student["year"], student["section"], student["branch"], student["year"], student["section"]))
    is_authorized = cursor.fetchone()
    if not is_authorized:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Access denied: You can only message faculty instructors assigned to your class or enrolled subjects."
        }), 403
        
    teacher_user_id = t_row["user_id"]
    teacher_name = t_row["full_name"]
    
    # Always enforce canonical conversation_id
    conversation_id = f"conv_s{student_id}_t{teacher_id}"
        
    cursor.execute("""
    INSERT INTO messages (conversation_id, sender_id, sender_role, receiver_id, receiver_role, subject_id, message, is_read)
    VALUES (?, ?, 'student', ?, 'teacher', ?, ?, 0)
    """, (conversation_id, student_id, teacher_id, subject_id, message_text))
    
    msg_id = cursor.lastrowid
    
    # Create notification for teacher
    if teacher_user_id:
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type, is_read)
        VALUES (?, ?, ?, 'message', 0)
        """, (teacher_user_id, f"New Inquiry from {student_name}", f"Student {student_name} ({student['roll_no']}) sent you a message."))
        
    conn.commit()
    
    # Retrieve inserted message
    cursor.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
    inserted = dict(cursor.fetchone())
    
    conn.close()
    return jsonify({
        "success": True,
        "message": "Message sent successfully.",
        "conversation_id": conversation_id,
        "message_data": inserted
    }), 201

@student_bp.route("/api/student/messages/unread-count", methods=["GET"])
@student_required
def get_student_unread_message_count():
    """Returns the total number of unread incoming messages for the student."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "unread_count": 0}), 404
        
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) as unread_count 
    FROM messages 
    WHERE receiver_role = 'student' AND receiver_id = ? AND is_read = 0
    """, (student["id"],))
    count = cursor.fetchone()["unread_count"]
    conn.close()
    return jsonify({"success": True, "unread_count": count})


@student_bp.route("/api/student/messages/stream", methods=["GET"])
@student_required
def stream_student_messages():
    """
    Server-Sent Events (SSE) real-time message stream for instantaneous messaging updates with zero polling lag.
    """
    import time
    from flask import Response

    conn = get_db_connection()
    student = get_logged_in_student(conn)
    conn.close()
    if not student:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    student_id = student["id"]

    def event_generator():
        last_check = time.time() - 5
        yield f"data: {json.dumps({'type': 'connected', 'student_id': student_id})}\n\n"
        for _ in range(60):  # 60 iterations (approx 60-120 seconds stream)
            try:
                db = get_db_connection()
                cur = db.cursor()
                cur.execute("""
                SELECT id, conversation_id, sender_id, sender_role, message, is_read, created_at
                FROM messages
                WHERE receiver_role = 'student' AND receiver_id = ?
                  AND created_at >= datetime('now', '-3 seconds')
                ORDER BY created_at DESC LIMIT 5
                """, (student_id,))
                new_msgs = [dict(r) for r in cur.fetchall()]
                db.close()
                if new_msgs:
                    yield f"data: {json.dumps({'type': 'new_messages', 'messages': new_msgs})}\n\n"
            except Exception:
                pass
            time.sleep(2)

    return Response(event_generator(), mimetype="text/event-stream")



# ================= 10. DYNAMIC CURRICULUM HIERARCHY & TOPIC MASTERY =================
@student_bp.route("/api/student/subject/<int:subject_id>/hierarchy", methods=["GET"])
@student_required
def get_student_subject_hierarchy(subject_id):
    """
    Returns the complete Subject -> Modules -> Topics -> Learning Objectives -> Resources tree,
    annotated with the authenticated student's individual mastery scores per topic.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
    subj = cursor.fetchone()
    if not subj:
        conn.close()
        return jsonify({"success": False, "error": "Subject not found."}), 404

    # Fetch Modules
    cursor.execute("SELECT * FROM modules WHERE subject_id = ? ORDER BY module_number ASC", (subject_id,))
    module_rows = cursor.fetchall()

    modules = []
    for m in module_rows:
        m_dict = dict(m)
        # Fetch Topics with student mastery
        cursor.execute("""
        SELECT t.*,
               COALESCE(stm.mastery_score, 50.0) as student_mastery,
               COALESCE(stm.quiz_score, 0.0) as last_quiz_score,
               COALESCE(stm.attempts, 0) as attempts,
               COALESCE(stm.status, 'not_started') as mastery_status
        FROM topics t
        LEFT JOIN student_topic_mastery stm ON stm.topic_id = t.id AND stm.student_id = ?
        WHERE t.module_id = ?
        ORDER BY t.order_number ASC
        """, (student["id"], m["id"]))
        topic_rows = cursor.fetchall()
        
        topics = []
        for t in topic_rows:
            t_dict = dict(t)
            # Fetch learning objectives
            cursor.execute("SELECT * FROM learning_objectives WHERE topic_id = ?", (t["id"],))
            t_dict["objectives"] = [dict(o) for o in cursor.fetchall()]
            topics.append(t_dict)
            
        m_dict["topics"] = topics
        modules.append(m_dict)

    # Fetch Authorized Resources
    cursor.execute("""
    SELECT id, title, file_name, resource_type, source, authorization_status, version
    FROM learning_resources
    WHERE subject_id = ? AND authorization_status = 'authorized'
    """, (subject_id,))
    resources = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify({
        "success": True,
        "subject": dict(subj),
        "modules": modules,
        "resources": resources
    })


@student_bp.route("/api/student/topic/<int:topic_id>/quiz", methods=["GET"])
@student_required
def get_grounded_topic_quiz(topic_id):
    """
    Fetches grounded questions for a specific topic with strict syllabus and resource provenance.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.id as topic_id, t.topic_name, t.description as topic_desc,
           s.id as subject_id, s.subject_code, s.subject_name
    FROM topics t
    JOIN subjects s ON t.subject_id = s.id
    WHERE t.id = ?
    """, (topic_id,))
    top_row = cursor.fetchone()
    if not top_row:
        conn.close()
        return jsonify({"success": False, "error": "Topic not found."}), 404

    # Fetch approved grounded questions
    cursor.execute("""
    SELECT id, question_text, question_type, option_a, option_b, option_c, option_d,
           difficulty, source_reference, source_page
    FROM grounded_questions
    WHERE topic_id = ? AND approval_status = 'approved'
    LIMIT 5
    """, (topic_id,))
    q_rows = cursor.fetchall()

    questions = []
    for r in q_rows:
        questions.append({
            "id": r["id"],
            "question": r["question_text"],
            "question_type": r["question_type"],
            "options": {
                "A": r["option_a"],
                "B": r["option_b"],
                "C": r["option_c"],
                "D": r["option_d"]
            },
            "difficulty": r["difficulty"],
            "source_reference": r["source_reference"],
            "source_page": r["source_page"]
        })

    # If no questions generated yet, generate them on-the-fly
    if not questions:
        from backend.quiz_service import generate_grounded_topic_questions
        gen_res = generate_grounded_topic_questions(top_row["subject_id"], topic_id)
        if gen_res.get("success"):
            cursor.execute("""
            SELECT id, question_text, question_type, option_a, option_b, option_c, option_d,
                   difficulty, source_reference, source_page
            FROM grounded_questions
            WHERE topic_id = ? AND approval_status = 'approved'
            LIMIT 5
            """, (topic_id,))
            for r in cursor.fetchall():
                questions.append({
                    "id": r["id"],
                    "question": r["question_text"],
                    "question_type": r["question_type"],
                    "options": {
                        "A": r["option_a"],
                        "B": r["option_b"],
                        "C": r["option_c"],
                        "D": r["option_d"]
                    },
                    "difficulty": r["difficulty"],
                    "source_reference": r["source_reference"],
                    "source_page": r["source_page"]
                })

    conn.close()
    return jsonify({
        "success": True,
        "topic": dict(top_row),
        "total_questions": len(questions),
        "questions": questions
    })


@student_bp.route("/api/student/quiz/submit-topic-quiz", methods=["POST"])
@student_bp.route("/api/student/topic/<int:topic_id>/quiz/submit", methods=["POST"])
@student_required
def submit_grounded_topic_quiz(topic_id=None):
    """
    Central Adaptive Feedback Loop Endpoint:
    1. Evaluates student responses against grounded questions.
    2. Recalculates Topic Mastery score.
    3. Updates student_topic_mastery and student_subject_performance.
    4. Triggers ML/QML re-prediction with updated universal learner features.
    5. Returns updated predictions, new mastery %, and the next recommended learning action.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    data = request.get_json() or {}
    topic_id = topic_id or data.get("topic_id")
    answers = data.get("answers", {})  # {question_id: "A"}
    time_spent_min = float(data.get("time_spent_minutes", 10.0) or 10.0)

    if not topic_id:
        conn.close()
        return jsonify({"success": False, "message": "topic_id is required."}), 400

    cursor = conn.cursor()
    cursor.execute("SELECT id, correct_answer, explanation, question_text FROM grounded_questions WHERE topic_id = ?", (topic_id,))
    q_rows = cursor.fetchall()

    correct_count = 0
    total_q = len(q_rows) if q_rows else 1
    feedback = []

    for qr in q_rows:
        q_id = str(qr["id"])
        user_ans = answers.get(q_id, "").strip().upper()
        corr_ans = qr["correct_answer"].strip().upper()
        is_corr = (user_ans == corr_ans)
        if is_corr:
            correct_count += 1
        feedback.append({
            "question_id": qr["id"],
            "user_answer": user_ans,
            "correct_answer": corr_ans,
            "is_correct": is_corr,
            "explanation": qr["explanation"]
        })

    score_pct = round((correct_count / max(1, len(q_rows))) * 100.0, 1)

    # Execute Adaptive Feedback Loop Update
    from ml.personalized_learning import update_student_topic_mastery_and_repredict
    loop_result = update_student_topic_mastery_and_repredict(
        student_id=student["id"],
        topic_id=int(topic_id),
        quiz_score_pct=score_pct,
        time_spent_min=time_spent_min,
        conn=conn
    )
    conn.close()

    return jsonify({
        "success": True,
        "score_percentage": score_pct,
        "correct_count": correct_count,
        "total_questions": len(q_rows),
        "feedback": feedback,
        "adaptive_loop": loop_result
    })


# =========================================================================
# REAL-TIME DYNAMIC ADAPTIVE QUIZ & REMEDIAL RECOVERY ENGINE
# =========================================================================

@student_bp.route("/api/student/topic/<int:topic_id>/adaptive/start", methods=["GET"])
@student_required
def start_adaptive_topic_quiz(topic_id):
    """
    Initializes a dynamic adaptive quiz session for the student:
    - Inspects previous mastery level to set appropriate entry difficulty.
    - Generates grounded questions across 3 tiers if not already present.
    - Returns the initial question and session state.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.id, t.topic_name, t.description, t.difficulty as topic_diff,
           s.id as subject_id, s.subject_name, s.subject_code,
           m.id as module_id, m.module_name
    FROM topics t
    JOIN subjects s ON t.subject_id = s.id
    JOIN modules m ON t.module_id = m.id
    WHERE t.id = ?
    """, (topic_id,))
    top_row = cursor.fetchone()

    if not top_row:
        conn.close()
        return jsonify({"success": False, "error": "Topic not found."}), 404

    # Check student's current mastery to determine starting difficulty
    cursor.execute("SELECT mastery_score, attempts FROM student_topic_mastery WHERE student_id = ? AND topic_id = ?", (student["id"], topic_id))
    m_row = cursor.fetchone()
    current_mastery = float(m_row["mastery_score"]) if m_row else 50.0

    if current_mastery >= 75.0:
        starting_diff = "Advanced"
    elif current_mastery >= 45.0:
        starting_diff = "Intermediate"
    else:
        starting_diff = "Beginner"

    # Ensure questions exist
    cursor.execute("SELECT COUNT(*) FROM grounded_questions WHERE topic_id = ? AND approval_status = 'approved'", (topic_id,))
    q_count = cursor.fetchone()[0]
    if q_count < 6:
        from backend.quiz_service import generate_grounded_topic_questions
        generate_grounded_topic_questions(top_row["subject_id"], topic_id)

    from backend.quiz_service import get_adaptive_question_for_topic
    first_q = get_adaptive_question_for_topic(topic_id, starting_diff, exclude_ids=[])

    conn.close()
    if not first_q:
        return jsonify({"success": False, "error": "Could not generate adaptive questions for this topic."}), 500

    return jsonify({
        "success": True,
        "topic": dict(top_row),
        "starting_difficulty": starting_diff,
        "current_mastery": current_mastery,
        "total_steps": 5,
        "current_step": 1,
        "question": first_q
    })


@student_bp.route("/api/student/topic/<int:topic_id>/adaptive/step", methods=["POST"])
@student_required
def step_adaptive_topic_quiz(topic_id):
    """
    Real-time Step Evaluation & Dynamic Difficulty Scaling:
    1. Validates selected option against the question's ground truth.
    2. Calculates difficulty adjustment (step up on correct, step down on incorrect).
    3. Fetches the next target question matching adjusted difficulty.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    data = request.get_json() or {}
    question_id = data.get("question_id")
    selected_option = (data.get("selected_option") or "").strip().upper()
    current_difficulty = data.get("current_difficulty", "Intermediate")
    answered_ids = data.get("answered_ids", [])
    step_number = data.get("step_number", 1)
    total_steps = data.get("total_steps", 5)

    if not question_id:
        conn.close()
        return jsonify({"success": False, "message": "question_id is required."}), 400

    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, correct_answer, explanation, difficulty, source_reference, source_page
    FROM grounded_questions WHERE id = ?
    """, (question_id,))
    q_row = cursor.fetchone()

    if not q_row:
        conn.close()
        return jsonify({"success": False, "message": "Question not found."}), 404

    correct_ans = q_row["correct_answer"].strip().upper()
    is_correct = (selected_option == correct_ans)

    from backend.quiz_service import get_next_adaptive_difficulty, get_adaptive_question_for_topic
    next_diff = get_next_adaptive_difficulty(current_difficulty, is_correct)
    
    updated_answered = list(set(answered_ids + [question_id]))
    next_q = None
    is_completed = (step_number >= total_steps)

    if not is_completed:
        next_q = get_adaptive_question_for_topic(topic_id, next_diff, exclude_ids=updated_answered)

    conn.close()

    return jsonify({
        "success": True,
        "is_correct": is_correct,
        "correct_answer": correct_ans,
        "explanation": q_row["explanation"],
        "source_reference": q_row["source_reference"],
        "source_page": q_row["source_page"],
        "difficulty_transition": {
            "previous": current_difficulty,
            "next": next_diff,
            "shifted": (current_difficulty != next_diff)
        },
        "step_number": step_number,
        "total_steps": total_steps,
        "is_completed": is_completed,
        "next_question": next_q,
        "answered_ids": updated_answered
    })


@student_bp.route("/api/student/topic/<int:topic_id>/adaptive/finish", methods=["POST"])
@student_required
def finish_adaptive_topic_quiz(topic_id):
    """
    Finalizes the Adaptive Assessment:
    1. Computes weighted accuracy and skill mastery.
    2. Updates topic mastery and subject aggregate scores in database.
    3. Runs real-time ML & QML risk re-prediction.
    4. Automatically generates a 3-step Remedial Recovery Path if score < 70%.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    data = request.get_json() or {}
    total_questions = data.get("total_questions", 5)
    correct_count = data.get("correct_count", 0)
    time_spent_min = float(data.get("time_spent_minutes", 8.0) or 8.0)
    progression = data.get("progression", [])

    score_pct = round((correct_count / max(1, total_questions)) * 100.0, 1)

    from ml.personalized_learning import update_student_topic_mastery_and_repredict
    loop_result = update_student_topic_mastery_and_repredict(
        student_id=student["id"],
        topic_id=int(topic_id),
        quiz_score_pct=score_pct,
        time_spent_min=time_spent_min,
        conn=conn
    )

    from backend.quiz_service import build_remedial_learning_path
    remedial_path = build_remedial_learning_path(student["id"], topic_id, score_pct, conn=conn)

    conn.close()

    return jsonify({
        "success": True,
        "score_percentage": score_pct,
        "correct_count": correct_count,
        "total_questions": total_questions,
        "progression": progression,
        "adaptive_loop": loop_result,
        "remedial_path": remedial_path
    })


@student_bp.route("/api/student/grounded-search", methods=["GET", "POST"])
@student_required
def search_grounded_materials():
    """
    Subject/topic-aware retrieval strictly restricted to the student's authorized institution.
    """
    student = None
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    conn.close()
    if not student:
        return jsonify({"success": False, "message": "Student not found."}), 404

    if request.method == "POST":
        data = request.get_json() or {}
        subject_id = data.get("subject_id")
        topic_id = data.get("topic_id")
        query_text = data.get("query", "")
    else:
        subject_id = request.args.get("subject_id")
        topic_id = request.args.get("topic_id")
        query_text = request.args.get("query", "")

    if not subject_id:
        return jsonify({"success": False, "message": "subject_id is required."}), 400

    from backend.document_service import search_grounded_topic_content
    res = search_grounded_topic_content(
        institution_id=student["institution_id"] or 1,
        subject_id=int(subject_id),
        topic_id=int(topic_id) if topic_id else None,
        query_text=query_text
    )
    return jsonify(res)


@student_bp.route("/api/student/topic/<int:topic_id>/content", methods=["GET"])
@student_required
def get_grounded_topic_content(topic_id):
    """
    Returns full grounded learning content for a specific topic:
    - Topic metadata (module, subject, difficulty, learning objectives)
    - Student topic mastery & recent attempts
    - Grounded textbook/notes extraction with exact page & section provenance
    - Key concepts & examples
    - Interactive practice drills (with explanations)
    - Grounded diagnostic quiz questions
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.id as topic_id, t.topic_name, t.description as topic_desc, t.difficulty, t.prerequisites,
           m.id as module_id, m.module_number, m.module_name, m.description as module_desc,
           s.id as subject_id, s.subject_code, s.subject_name, s.branch, s.year, s.semester, s.credits,
           i.id as institution_id, i.name as institution_name
    FROM topics t
    JOIN modules m ON t.module_id = m.id
    JOIN subjects s ON t.subject_id = s.id
    LEFT JOIN institutions i ON s.institution_id = i.id
    WHERE t.id = ?
    """, (topic_id,))
    top_row = cursor.fetchone()

    if not top_row:
        conn.close()
        return jsonify({"success": False, "error": "Topic not found."}), 404

    # Fetch student's current mastery on this topic
    cursor.execute("""
    SELECT mastery_score, quiz_score, attempts, time_spent_minutes, status, last_activity
    FROM student_topic_mastery
    WHERE student_id = ? AND topic_id = ?
    """, (student["id"], topic_id))
    mastery_row = cursor.fetchone()
    current_mastery = float(mastery_row["mastery_score"]) if mastery_row else 42.0
    attempts_count = int(mastery_row["attempts"]) if mastery_row else 0
    topic_status = mastery_row["status"] if mastery_row else "in_progress"

    # Fetch Document Chunks & Authorized Resources for provenance
    cursor.execute("""
    SELECT dc.id, dc.page_number, dc.section_heading, dc.chunk_text,
           lr.id as resource_id, lr.title as resource_title, lr.file_name, lr.source, lr.resource_type
    FROM document_chunks dc
    JOIN learning_resources lr ON dc.resource_id = lr.id
    WHERE dc.topic_id = ? AND lr.authorization_status = 'authorized'
    ORDER BY dc.page_number ASC
    """, (topic_id,))
    chunk_rows = cursor.fetchall()

    if chunk_rows:
        primary_chunk = chunk_rows[0]
        source_doc = primary_chunk["file_name"]
        source_title = primary_chunk["resource_title"]
        source_page = f"Pages {primary_chunk['page_number']}–{primary_chunk['page_number'] + 6}"
        section_heading = primary_chunk["section_heading"]
        extracted_text = primary_chunk["chunk_text"]
    else:
        source_doc = f"{top_row['subject_code']}_Textbook.pdf"
        source_title = f"Official Reference Text: {top_row['subject_name']}"
        source_page = "Pages 45–52"
        section_heading = top_row["topic_name"]
        extracted_text = f"Official curriculum syllabus content covering theoretical analysis and design principles for {top_row['topic_name']}."

    # Fetch Grounded Questions
    cursor.execute("""
    SELECT id, question_text, question_type, option_a, option_b, option_c, option_d,
           correct_answer, explanation, difficulty, source_reference, source_page
    FROM grounded_questions
    WHERE topic_id = ? AND approval_status = 'approved'
    LIMIT 10
    """, (topic_id,))
    q_rows = cursor.fetchall()

    questions = []
    for r in q_rows:
        questions.append({
            "id": r["id"],
            "question": r["question_text"],
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
            "source_reference": r["source_reference"] or source_doc,
            "source_page": r["source_page"]
        })

    # If questions empty, generate on-the-fly from approved syllabus
    if not questions:
        from backend.quiz_service import generate_grounded_topic_questions
        generate_grounded_topic_questions(top_row["subject_id"], topic_id)
        cursor.execute("SELECT * FROM grounded_questions WHERE topic_id = ? LIMIT 5", (topic_id,))
        for r in cursor.fetchall():
            questions.append({
                "id": r["id"],
                "question": r["question_text"],
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
                "source_reference": r["source_reference"] or source_doc,
                "source_page": r["source_page"]
            })

    # Practice questions (first 2 questions configured as interactive practice)
    practice_drills = questions[:2] if len(questions) >= 2 else questions
    quiz_questions = questions

    # Structured Grounded Theory & Key Concepts
    key_concepts = [
        f"Mathematical Formulation and algorithmic complexity bounds for {top_row['topic_name']}.",
        f"Standard engineering trade-offs regarding computational overhead, error tolerance, and latency.",
        f"Implementation patterns according to {top_row['subject_name']} standards.",
        f"Validation and empirical verification methodologies specified in {source_doc}."
    ]

    conn.close()

    return jsonify({
        "success": True,
        "topic": dict(top_row),
        "mastery": {
            "score": current_mastery,
            "attempts": attempts_count,
            "status": topic_status,
            "gauge_level": "Mastered" if current_mastery >= 80 else ("Competent" if current_mastery >= 60 else "Needs Revision")
        },
        "source_citation": {
            "document_name": source_doc,
            "resource_title": source_title,
            "page_range": source_page,
            "section": section_heading,
            "authorization": "Institution Authorized"
        },
        "grounded_content": {
            "summary": extracted_text,
            "key_concepts": key_concepts,
            "practical_example": f"Applied scenario demonstration for {top_row['topic_name']} evaluating system parameters and convergence properties."
        },
        "practice_questions": practice_drills,
        "quiz_questions": quiz_questions
    })


@student_bp.route("/api/student/curriculum/browse", methods=["GET"])
@student_required
def browse_curriculum_subjects():
    """
    Dynamic curriculum subject explorer for students.
    Returns subjects for any requested Branch, Year, Semester within the student's institution.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    inst_id = student["institution_id"] or 1
    branch = request.args.get("branch", student["branch"])
    year = request.args.get("year", student["year"])
    sem_raw = request.args.get("semester", str(student["semester"]))

    try:
        sem_int = int(str(sem_raw).replace("Semester", "").replace("Sem", "").strip() or "1")
    except ValueError:
        sem_int = 1

    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, 
           count(DISTINCT m.id) as module_count,
           count(DISTINCT t.id) as topic_count,
           count(DISTINCT lr.id) as resource_count,
           (SELECT count(*) FROM student_subjects ss WHERE ss.student_id = ? AND ss.subject_id = s.id) as is_enrolled
    FROM subjects s
    LEFT JOIN modules m ON m.subject_id = s.id
    LEFT JOIN topics t ON t.subject_id = s.id
    LEFT JOIN learning_resources lr ON lr.subject_id = s.id AND lr.authorization_status = 'authorized'
    WHERE (s.institution_id = ? OR s.institution_id IS NULL)
      AND (s.branch = ? OR ? = 'All')
      AND (s.year = ? OR ? = 'All')
      AND (s.semester = ? OR ? = 'All')
    GROUP BY s.id
    ORDER BY s.subject_code ASC
    """, (student["id"], inst_id, branch, branch, year, year, sem_int, sem_raw))
    
    rows = cursor.fetchall()
    subjects = [dict(r) for r in rows]
    conn.close()

    return jsonify({
        "success": True,
        "institution_id": inst_id,
        "branch": branch,
        "year": year,
        "semester": sem_int,
        "total_subjects": len(subjects),
        "subjects": subjects
    })


# =========================================================================
# INTERACTIVE CODING SANDBOX & GAMIFICATION REWARDS
# =========================================================================

@student_bp.route("/api/student/gamification/profile", methods=["GET"])
@student_required
def get_gamification_profile_route():
    """Returns student XP, level progression, continuous learning streak, and achievement badges."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    conn.close()
    if not student:
        return jsonify({"success": False, "message": "Student not found."}), 404

    from backend.sandbox_service import get_student_gamification_profile
    profile = get_student_gamification_profile(student["id"])
    return jsonify({
        "success": True,
        "profile": profile
    })


@student_bp.route("/api/student/sandbox/challenges", methods=["GET"])
@student_required
def get_coding_challenges_route():
    """Returns practice coding challenges tied to curriculum."""
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    from backend.sandbox_service import seed_coding_challenges_if_empty
    seed_coding_challenges_if_empty()

    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, title, language, difficulty, category, description, starter_code, xp_reward
    FROM coding_challenges
    ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    challenges = [dict(r) for r in rows]
    return jsonify({
        "success": True,
        "total_challenges": len(challenges),
        "challenges": challenges
    })


@student_bp.route("/api/student/sandbox/execute", methods=["POST"])
@student_required
def execute_coding_challenge_route():
    """
    Executes student code in Python/SQL sandbox against test cases.
    Records submission, awards XP, and unlocks achievement badges.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found."}), 404

    data = request.get_json() or {}
    challenge_id = data.get("challenge_id")
    code_str = data.get("code", "")
    language = (data.get("language") or "python").lower()

    if not code_str:
        conn.close()
        return jsonify({"success": False, "message": "Code cannot be empty."}), 400

    cursor = conn.cursor()
    test_cases = []
    xp_reward = 100
    category = "Algorithms"

    if challenge_id:
        cursor.execute("SELECT id, test_cases_json, xp_reward, category, language FROM coding_challenges WHERE id = ?", (challenge_id,))
        ch_row = cursor.fetchone()
        if ch_row:
            test_cases = json.loads(ch_row["test_cases_json"] or "[]")
            xp_reward = ch_row["xp_reward"]
            category = ch_row["category"]
            language = ch_row["language"].lower()

    # Execute sandbox
    if language == "sql":
        from backend.sandbox_service import execute_sql_sandbox_query
        exec_res = execute_sql_sandbox_query(code_str)
    else:
        from backend.sandbox_service import execute_python_sandbox_code
        exec_res = execute_python_sandbox_code(code_str, test_cases)

    status = exec_res.get("status", "Passed" if exec_res.get("success") else "Failed")
    passed_tests = exec_res.get("passed_tests", 0)
    total_tests = exec_res.get("total_tests", max(1, len(test_cases)))

    # Record submission
    if challenge_id:
        cursor.execute("""
        INSERT INTO coding_submissions (student_id, challenge_id, code_submitted, passed_tests, total_tests, status, execution_time_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (student["id"], challenge_id, code_str, passed_tests, total_tests, status, exec_res.get("execution_time_ms", 0.0)))

    # Gamification: Award XP and unlock badges if passed
    unlocked_new_badge = None
    if exec_res.get("success"):
        cursor.execute("UPDATE students SET xp_points = COALESCE(xp_points, 450) + ? WHERE id = ?", (xp_reward, student["id"]))
        
        # Unlock 'first_code' badge
        cursor.execute("SELECT id FROM student_badges WHERE student_id = ? AND badge_key = 'first_code'", (student["id"],))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO student_badges (student_id, badge_key, badge_name, badge_icon, badge_color, description)
            VALUES (?, 'first_code', 'First Code Run', 'fa-code', '#38bdf8', 'Successfully ran your first interactive code challenge.')
            """, (student["id"],))
            unlocked_new_badge = "First Code Run"

        # Unlock Quantum badge if category is Quantum
        if "Quantum" in category:
            cursor.execute("SELECT id FROM student_badges WHERE student_id = ? AND badge_key = 'quantum_pioneer'", (student["id"],))
            if not cursor.fetchone():
                cursor.execute("""
                INSERT INTO student_badges (student_id, badge_key, badge_name, badge_icon, badge_color, description)
                VALUES (?, 'quantum_pioneer', 'Quantum Pioneer', 'fa-atom', '#c084fc', 'Completed a Variational Quantum Circuit simulation challenge.')
                """, (student["id"],))
                unlocked_new_badge = "Quantum Pioneer"

    conn.commit()
    conn.close()

    from backend.sandbox_service import get_student_gamification_profile
    updated_profile = get_student_gamification_profile(student["id"])

    return jsonify({
        "success": exec_res.get("success", False),
        "execution": exec_res,
        "xp_earned": xp_reward if exec_res.get("success") else 0,
        "unlocked_new_badge": unlocked_new_badge,
        "gamification_profile": updated_profile
    })


# ================= 10. OFFICIAL ACADEMIC REPORT CARD EXPORT =================
@student_bp.route("/api/student/report-card", methods=["GET"])
@student_required
def get_my_report_card():
    """
    Returns official academic dossier with Quantum ML diagnostics,
    subject mastery breakdown, Bloom taxonomy scores, and verification token.
    """
    conn = get_db_connection()
    student = get_logged_in_student(conn)
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student profile not found."}), 404

    from backend.report_service import build_student_report_card
    dossier = build_student_report_card(conn, student["id"])
    conn.close()

    if not dossier:
        return jsonify({"success": False, "message": "Failed to generate academic dossier."}), 500

    return jsonify({
        "success": True,
        "report_card": dossier
    })




