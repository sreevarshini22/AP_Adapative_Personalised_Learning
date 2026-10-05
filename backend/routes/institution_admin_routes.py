"""
Institution Admin Portal API Routes
AP Adaptive Education Platform

Provides complete institutional governance:
- Institution Profile & Settings
- Programs & Curriculum Versioning
- Multi-format Curriculum Upload, Validation, Preview & Approval
- Authorized Resource Management (with Copyright Confirmation)
- Faculty & Student Management
- Institution-level Analytics & Monitoring
"""

import os
import sys
import json
import csv
import io
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash
from backend.database import get_db_connection, log_audit_event
from backend.auth import institution_admin_required, get_current_user
from backend.models import serialize_institution, serialize_student, serialize_teacher, serialize_subject
from backend.curriculum_service import parse_curriculum_csv_or_text, import_and_publish_curriculum
from backend.document_service import add_authorized_learning_resource

inst_admin_bp = Blueprint("institution_admin", __name__)


def get_admin_institution_id():
    """Helper to get current logged in institution admin's institution_id."""
    user = get_current_user()
    if not user:
        return None
    # Super admins can pass ?institution_id=X or default to session
    req_inst = request.args.get("institution_id")
    if user["role"] == "state_admin" and req_inst:
        try:
            return int(req_inst)
        except ValueError:
            pass
    return user.get("institution_id") or 1


# ================= 1. INSTITUTION PROFILE =================
@inst_admin_bp.route("/api/institution/profile", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/profile", methods=["GET"])
@institution_admin_required
def get_institution_profile():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM institutions WHERE id = ?", (inst_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"success": False, "error": "Institution not found."}), 404
    return jsonify({"success": True, "institution": serialize_institution(row), **dict(row)})


# ================= 2. PROGRAMS & DEGREES =================
@inst_admin_bp.route("/api/institution/programs", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/programs", methods=["GET"])
@institution_admin_required
def get_institution_programs():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT p.*, count(s.id) as subject_count
    FROM programs p
    LEFT JOIN subjects s ON s.program_id = p.id
    WHERE p.institution_id = ?
    GROUP BY p.id
    ORDER BY p.program_code ASC
    """, (inst_id,))
    rows = cursor.fetchall()
    conn.close()
    programs = [dict(r) for r in rows]
    return jsonify({"success": True, "programs": programs}) if not request.path.endswith("-admin/programs") else jsonify(programs)


@inst_admin_bp.route("/api/institution/programs", methods=["POST"])
@inst_admin_bp.route("/api/institution-admin/programs", methods=["POST"])
@institution_admin_required
def create_institution_program():
    inst_id = get_admin_institution_id()
    data = request.get_json() or {}
    code = data.get("program_code", "").strip().upper()
    name = data.get("program_name", "").strip()
    degree = data.get("degree_type", "B.Tech").strip()

    if not code or not name:
        return jsonify({"success": False, "message": "Program code and name are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO programs (institution_id, program_code, program_name, degree_type, total_years, total_semesters)
        VALUES (?, ?, ?, ?, 4, 8)
        """, (inst_id, code, name, degree))
        prog_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Program '{code}' created successfully.", "program_id": prog_id}), 201
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": f"Failed to create program: {str(e)}"}), 400


# ================= 3. CURRICULUM UPLOAD & APPROVAL =================
@inst_admin_bp.route("/api/institution/curriculum/preview", methods=["POST"])
@inst_admin_bp.route("/api/institution-admin/curriculum/preview", methods=["POST"])
@institution_admin_required
def preview_curriculum_upload():
    """
    Parses and validates curriculum CSV/Text without committing to the live database.
    Shows parsed subjects, modules, topics, and validation errors.
    """
    inst_id = get_admin_institution_id()
    data = request.get_json() or {}
    file_content = data.get("content", "")
    program_id = data.get("program_id")
    version_code = data.get("version_code", data.get("regulation", "R24")).strip()

    if not file_content and not data.get("curriculum_data"):
        return jsonify({"success": False, "message": "Please provide curriculum file content or data."}), 400
    if not program_id:
        return jsonify({"success": False, "message": "Please select a target Program/Branch."}), 400

    if file_content:
        parsed = parse_curriculum_csv_or_text(file_content, inst_id, int(program_id), version_code)
    else:
        parsed = {"success": True, "curriculum": {"subjects": []}, "stats": {}}

    return jsonify(parsed)


@inst_admin_bp.route("/api/institution/curriculum/publish", methods=["POST"])
@inst_admin_bp.route("/api/institution-admin/curriculum/publish", methods=["POST"])
@inst_admin_bp.route("/api/institution-admin/curriculum/import", methods=["POST"])
@institution_admin_required
def publish_curriculum_upload():
    """
    Imports and publishes approved curriculum into the live institutional hierarchy.
    """
    inst_id = get_admin_institution_id()
    user = get_current_user()
    data = request.get_json() or {}
    file_content = data.get("content", "")
    curriculum_data = data.get("curriculum_data")
    program_id = data.get("program_id")
    version_code = data.get("version_code", data.get("regulation", "R24")).strip()

    if not program_id:
        return jsonify({"success": False, "message": "program_id is required."}), 400

    if curriculum_data and isinstance(curriculum_data, list):
        # Convert list rows to curriculum structure
        subjects_map = {}
        for row in curriculum_data:
            code = row.get("subject_code", row.get("code", "SUBJ")).strip().upper()
            if code not in subjects_map:
                subjects_map[code] = {
                    "code": code,
                    "name": row.get("subject_name", row.get("name", code)),
                    "semester": int(row.get("semester", 1)),
                    "year": (int(row.get("semester", 1)) + 1) // 2,
                    "credits": 3,
                    "modules": []
                }
            mod_name = row.get("module_name", "Unit 1").strip()
            top_name = row.get("topic_name", "Topic 1").strip()
            s_obj = subjects_map[code]
            m_obj = next((m for m in s_obj["modules"] if m["module_name"] == mod_name), None)
            if not m_obj:
                m_obj = {"module_number": len(s_obj["modules"]) + 1, "module_name": mod_name, "topics": []}
                s_obj["modules"].append(m_obj)
            m_obj["topics"].append({"name": top_name, "difficulty": "Medium", "learning_objectives": []})

        parsed = {"success": True, "curriculum": {"subjects": list(subjects_map.values())}, "stats": {}}
    elif file_content:
        parsed = parse_curriculum_csv_or_text(file_content, inst_id, int(program_id), version_code)
        if not parsed.get("success"):
            return jsonify(parsed), 400
    else:
        return jsonify({"success": False, "message": "Content or curriculum_data is required."}), 400

    import_result = import_and_publish_curriculum(
        institution_id=inst_id,
        program_id=int(program_id),
        version_code=version_code,
        parsed_curriculum=parsed,
        uploaded_by=user.get("id"),
        auto_publish=True
    )

    return jsonify(import_result)


# ================= 4. SUBJECTS, MODULES & TOPICS =================
@inst_admin_bp.route("/api/institution/subjects", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/subjects", methods=["GET"])
@institution_admin_required
def get_institution_subjects():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, p.program_code, p.program_name,
           (SELECT count(*) FROM modules m WHERE m.subject_id = s.id) as module_count,
           (SELECT count(*) FROM topics t WHERE t.subject_id = s.id) as topic_count,
           (SELECT count(*) FROM learning_resources lr WHERE lr.subject_id = s.id) as resource_count
    FROM subjects s
    LEFT JOIN programs p ON s.program_id = p.id
    WHERE s.institution_id = ? OR s.institution_id IS NULL
    ORDER BY s.subject_code ASC
    """, (inst_id,))
    rows = cursor.fetchall()
    conn.close()
    subjects = [dict(r) for r in rows]
    return jsonify({"success": True, "total": len(subjects), "subjects": subjects})


@inst_admin_bp.route("/api/institution/curriculum/hierarchy", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/curriculum/hierarchy", methods=["GET"])
@institution_admin_required
def get_institution_curriculum_hierarchy():
    """Returns the complete hierarchy of subjects, modules, and topics for a program."""
    inst_id = get_admin_institution_id()
    program_id = request.args.get("program_id")
    conn = get_db_connection()
    cursor = conn.cursor()

    if program_id:
        cursor.execute("SELECT * FROM subjects WHERE (institution_id = ? OR institution_id IS NULL) AND program_id = ? ORDER BY semester ASC, subject_code ASC", (inst_id, program_id))
    else:
        cursor.execute("SELECT * FROM subjects WHERE institution_id = ? OR institution_id IS NULL ORDER BY semester ASC, subject_code ASC", (inst_id,))
    
    subject_rows = cursor.fetchall()
    subjects_res = []

    for s in subject_rows:
        s_dict = dict(s)
        cursor.execute("SELECT * FROM modules WHERE subject_id = ? ORDER BY module_number ASC", (s["id"],))
        m_rows = cursor.fetchall()
        modules = []
        for m in m_rows:
            m_dict = dict(m)
            cursor.execute("SELECT * FROM topics WHERE module_id = ? ORDER BY order_number ASC", (m["id"],))
            m_dict["topics"] = [dict(t) for t in cursor.fetchall()]
            modules.append(m_dict)
        s_dict["modules"] = modules
        subjects_res.append(s_dict)

    conn.close()
    return jsonify({"success": True, "subjects": subjects_res})


@inst_admin_bp.route("/api/institution/subject/<int:subject_id>/hierarchy", methods=["GET"])
@institution_admin_required
def get_subject_full_hierarchy(subject_id):
    """Returns the complete Module -> Topic -> Learning Objective -> Resources tree for a subject."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
    subj = cursor.fetchone()
    if not subj:
        conn.close()
        return jsonify({"success": False, "error": "Subject not found."}), 404

    cursor.execute("SELECT * FROM modules WHERE subject_id = ? ORDER BY module_number ASC", (subject_id,))
    modules_rows = cursor.fetchall()

    modules = []
    for m in modules_rows:
        m_dict = dict(m)
        cursor.execute("SELECT * FROM topics WHERE module_id = ? ORDER BY order_number ASC", (m["id"],))
        topics_rows = cursor.fetchall()
        topics = []
        for t in topics_rows:
            t_dict = dict(t)
            cursor.execute("SELECT * FROM learning_objectives WHERE topic_id = ?", (t["id"],))
            t_dict["objectives"] = [dict(o) for o in cursor.fetchall()]
            topics.append(t_dict)
        m_dict["topics"] = topics
        modules.append(m_dict)

    cursor.execute("SELECT * FROM learning_resources WHERE subject_id = ?", (subject_id,))
    resources = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify({
        "success": True,
        "subject": serialize_subject(subj),
        "modules": modules,
        "resources": resources
    })


# ================= 5. AUTHORIZED LEARNING RESOURCES =================
@inst_admin_bp.route("/api/institution/resources", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/resources", methods=["GET"])
@institution_admin_required
def get_institution_resources():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT lr.*, s.subject_name, s.subject_code,
           (SELECT count(*) FROM document_chunks dc WHERE dc.resource_id = lr.id) as chunks_count
    FROM learning_resources lr
    LEFT JOIN subjects s ON lr.subject_id = s.id
    WHERE lr.institution_id = ? OR lr.institution_id IS NULL
    ORDER BY lr.id DESC
    """, (inst_id,))
    rows = cursor.fetchall()
    conn.close()
    resources = [dict(r) for r in rows]
    return jsonify({"success": True, "resources": resources}) if not request.path.endswith("-admin/resources") else jsonify(resources)


@inst_admin_bp.route("/api/institution/resources/upload", methods=["POST"])
@inst_admin_bp.route("/api/institution-admin/resources/upload", methods=["POST"])
@institution_admin_required
def upload_authorized_resource():
    inst_id = get_admin_institution_id()
    user = get_current_user()
    data = request.get_json() or {}

    subject_id = data.get("subject_id")
    title = data.get("title", "").strip()
    file_name = data.get("file_name", title).strip()
    resource_type = data.get("resource_type", "textbook")
    source = data.get("source", "Institution Approved Curriculum Committee")
    module_id = data.get("module_id")
    topic_id = data.get("topic_id")
    copyright_ack = data.get("copyright_acknowledged", data.get("confirmed_authorized", False))
    content = data.get("content", "")
    chunks = data.get("sample_text_chunks", [content] if content else [])

    if not subject_id or not title:
        return jsonify({"success": False, "message": "subject_id and title are required."}), 400

    if not copyright_ack:
        return jsonify({
            "success": False,
            "message": "Copyright confirmation required. You must verify that the institution is authorized to use this resource."
        }), 400

    res = add_authorized_learning_resource(
        institution_id=inst_id,
        subject_id=int(subject_id),
        title=title,
        file_name=file_name or title,
        resource_type=resource_type,
        source=source,
        module_id=module_id,
        topic_id=topic_id,
        uploaded_by=user.get("id"),
        copyright_acknowledged=True,
        sample_text_chunks=chunks
    )
    return jsonify(res)


# ================= 6. FACULTY & STUDENTS =================
@inst_admin_bp.route("/api/institution/teachers", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/teachers", methods=["GET"])
@institution_admin_required
def get_institution_faculty():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teachers WHERE institution_id = ? OR institution_id IS NULL ORDER BY full_name ASC", (inst_id,))
    rows = cursor.fetchall()
    conn.close()
    teachers = [serialize_teacher(r) for r in rows]
    return jsonify({"success": True, "teachers": teachers}) if not request.path.endswith("-admin/teachers") else jsonify(teachers)


@inst_admin_bp.route("/api/institution/students", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/students", methods=["GET"])
@institution_admin_required
def get_institution_students():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, p.program_name
    FROM students s
    LEFT JOIN programs p ON s.program_id = p.id
    WHERE s.institution_id = ? OR s.institution_id IS NULL
    ORDER BY s.roll_no ASC
    """, (inst_id,))
    rows = cursor.fetchall()
    conn.close()
    students = [serialize_student(r) for r in rows]
    return jsonify({"success": True, "students": students}) if not request.path.endswith("-admin/students") else jsonify(students)


# ================= 7. INSTITUTION ANALYTICS =================
@inst_admin_bp.route("/api/institution/analytics", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/analytics", methods=["GET"])
@institution_admin_required
def get_institution_analytics():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total students
    cursor.execute("SELECT count(*) FROM students WHERE institution_id = ? OR institution_id IS NULL", (inst_id,))
    total_students = cursor.fetchone()[0]

    # Total faculty
    cursor.execute("SELECT count(*) FROM teachers WHERE institution_id = ? OR institution_id IS NULL", (inst_id,))
    total_faculty = cursor.fetchone()[0]

    # Total subjects
    cursor.execute("SELECT count(*) FROM subjects WHERE institution_id = ? OR institution_id IS NULL", (inst_id,))
    total_subjects = cursor.fetchone()[0]

    # Average attendance & progress
    cursor.execute("""
    SELECT AVG(attendance) as avg_att, AVG(overall_progress) as avg_prog
    FROM students WHERE institution_id = ? OR institution_id IS NULL
    """, (inst_id,))
    avg_row = cursor.fetchone()
    avg_attendance = round(float(avg_row["avg_att"] or 76.5), 1)
    avg_progress = round(float(avg_row["avg_prog"] or 62.0), 1)

    # Risk distribution
    cursor.execute("""
    SELECT risk_level, count(*) as cnt
    FROM (
        SELECT student_id, risk_level, MAX(created_at)
        FROM model_predictions_history
        GROUP BY student_id
    ) GROUP BY risk_level
    """)
    risk_rows = cursor.fetchall()
    risk_dist = {"low": 0, "medium": 0, "high": 0}
    for r in risk_rows:
        lvl = (r["risk_level"] or "Low Risk").lower().replace(" risk", "")
        if lvl in risk_dist:
            risk_dist[lvl] = r["cnt"]

    if sum(risk_dist.values()) == 0:
        cursor.execute("SELECT attendance FROM students WHERE institution_id = ? OR institution_id IS NULL", (inst_id,))
        s_atts = cursor.fetchall()
        for sa in s_atts:
            att = float(sa[0] or 75.0)
            if att < 65.0:
                risk_dist["high"] += 1
            elif att < 75.0:
                risk_dist["medium"] += 1
            else:
                risk_dist["low"] += 1

    # Learning gaps
    cursor.execute("""
    SELECT t.topic_name, s.subject_name, AVG(stm.mastery_score) as avg_mastery, count(stm.id) as students_count
    FROM student_topic_mastery stm
    JOIN topics t ON stm.topic_id = t.id
    JOIN subjects s ON stm.subject_id = s.id
    WHERE s.institution_id = ? OR s.institution_id IS NULL
    GROUP BY t.id
    ORDER BY avg_mastery ASC
    LIMIT 6
    """, (inst_id,))
    learning_gaps = [dict(r) for r in cursor.fetchall()]

    conn.close()

    res = {
        "success": True,
        "institution_id": inst_id,
        "total_students": total_students,
        "total_faculty": total_faculty,
        "total_subjects": total_subjects,
        "average_attendance": avg_attendance,
        "average_progress": avg_progress,
        "risk_distribution": risk_dist,
        "learning_gaps": learning_gaps
    }
    return jsonify(res)


# ================= 8. AUDIT LOGS =================
@inst_admin_bp.route("/api/institution/audit-logs", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/audit-logs", methods=["GET"])
@institution_admin_required
def get_institution_audit_logs():
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM audit_logs
    WHERE institution_id = ? OR institution_id IS NULL
    ORDER BY id DESC
    LIMIT 50
    """, (inst_id,))
    rows = cursor.fetchall()
    conn.close()
    logs = [dict(r) for r in rows]
    return jsonify({"success": True, "logs": logs}) if not request.path.endswith("-admin/audit-logs") else jsonify(logs)


# ================= 9. INSTITUTIONAL DEAN ANALYTICS =================
@inst_admin_bp.route("/api/institution/dean-analytics", methods=["GET"])
@inst_admin_bp.route("/api/institution-admin/dean-analytics", methods=["GET"])
@institution_admin_required
def get_dean_institutional_analytics():
    """
    Returns comprehensive cross-departmental executive analytics for Academic Deans and Principals:
    - Department/Branch Pass-Rate & Performance Heatmaps
    - Year-Level Attrition & Risk Breakdown
    - Faculty Intervention Velocity & Recovery Metrics
    - Institutional Syllabus & Mastery Index
    - Priority At-Risk Cohort Focus Areas
    """
    inst_id = get_admin_institution_id()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Total Counts
    cursor.execute("SELECT count(*) FROM students WHERE institution_id = ? OR institution_id IS NULL", (inst_id,))
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM teachers WHERE institution_id = ? OR institution_id IS NULL", (inst_id,))
    total_faculty = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM subjects WHERE institution_id = ? OR institution_id IS NULL", (inst_id,))
    total_subjects = cursor.fetchone()[0]

    # 2. Department-wise Performance & Pass-Rate Breakdown
    cursor.execute("""
    SELECT 
        COALESCE(branch, 'General Engineering') as department,
        count(id) as student_count,
        ROUND(AVG(attendance), 1) as avg_attendance,
        ROUND(AVG(overall_progress), 1) as avg_progress,
        SUM(CASE WHEN attendance < 70 OR overall_progress < 50 THEN 1 ELSE 0 END) as high_risk_count,
        SUM(CASE WHEN attendance >= 70 AND attendance < 80 AND overall_progress >= 50 THEN 1 ELSE 0 END) as med_risk_count,
        SUM(CASE WHEN attendance >= 80 AND overall_progress >= 60 THEN 1 ELSE 0 END) as low_risk_count
    FROM students
    WHERE institution_id = ? OR institution_id IS NULL
    GROUP BY branch
    ORDER BY student_count DESC
    """, (inst_id,))
    dept_rows = cursor.fetchall()

    department_analytics = []
    for dr in dept_rows:
        sc = dr["student_count"]
        low_risk = dr["low_risk_count"] or 0
        med_risk = dr["med_risk_count"] or 0
        high_risk = dr["high_risk_count"] or 0
        pass_rate_est = round(((low_risk + med_risk * 0.75) / max(1, sc)) * 100.0, 1)
        department_analytics.append({
            "department": dr["department"],
            "student_count": sc,
            "avg_attendance": dr["avg_attendance"] or 75.0,
            "avg_progress": dr["avg_progress"] or 60.0,
            "high_risk_count": high_risk,
            "medium_risk_count": med_risk,
            "low_risk_count": low_risk,
            "estimated_pass_rate": min(100.0, pass_rate_est),
            "status": "Healthy" if pass_rate_est >= 75 else ("Monitor" if pass_rate_est >= 60 else "Critical Focus")
        })

    # 3. Year-wise Attrition Risk Distribution
    cursor.execute("""
    SELECT 
        COALESCE(year, '1st Year') as academic_year,
        count(id) as student_count,
        ROUND(AVG(attendance), 1) as avg_attendance,
        ROUND(AVG(overall_progress), 1) as avg_progress,
        SUM(CASE WHEN attendance < 70 OR overall_progress < 50 THEN 1 ELSE 0 END) as high_risk_count
    FROM students
    WHERE institution_id = ? OR institution_id IS NULL
    GROUP BY year
    ORDER BY year ASC
    """, (inst_id,))
    year_rows = cursor.fetchall()
    year_analytics = []
    for yr in year_rows:
        sc = yr["student_count"]
        hr = yr["high_risk_count"] or 0
        attrition_pct = round((hr / max(1, sc)) * 100.0, 1)
        year_analytics.append({
            "academic_year": yr["academic_year"],
            "student_count": sc,
            "avg_attendance": yr["avg_attendance"] or 75.0,
            "avg_progress": yr["avg_progress"] or 60.0,
            "high_risk_count": hr,
            "attrition_vulnerability_percentage": attrition_pct
        })

    # 4. Faculty Remedial Intervention Velocity & Effectiveness
    cursor.execute("""
    SELECT 
        count(*) as total_interventions,
        SUM(CASE WHEN status IN ('Completed', 'Resolved') THEN 1 ELSE 0 END) as completed_interventions,
        SUM(CASE WHEN status IN ('Assigned', 'In Progress') THEN 1 ELSE 0 END) as active_interventions,
        SUM(CASE WHEN priority IN ('Urgent', 'High') AND status NOT IN ('Completed', 'Resolved') THEN 1 ELSE 0 END) as urgent_pending
    FROM interventions
    WHERE institution_id = ? OR institution_id IS NULL
    """, (inst_id,))
    it_summary = cursor.fetchone()
    total_it = it_summary["total_interventions"] or 0
    completed_it = it_summary["completed_interventions"] or 0
    active_it = it_summary["active_interventions"] or 0
    urgent_it = it_summary["urgent_pending"] or 0
    resolution_rate = round((completed_it / max(1, total_it)) * 100.0, 1) if total_it > 0 else 85.0

    # Top Intervening Faculty
    cursor.execute("""
    SELECT t.full_name as teacher_name, t.branch, count(i.id) as intervention_count
    FROM interventions i
    JOIN teachers t ON i.teacher_id = t.id
    WHERE i.institution_id = ? OR i.institution_id IS NULL
    GROUP BY t.id
    ORDER BY intervention_count DESC LIMIT 5
    """, (inst_id,))
    top_faculty_interventions = [dict(r) for r in cursor.fetchall()]

    # 5. Curriculum & Mastery Index
    cursor.execute("SELECT count(*) FROM modules")
    total_modules = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM topics")
    total_topics = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(mastery_score) FROM student_topic_mastery")
    avg_mastery_row = cursor.fetchone()
    avg_mastery = round(float(avg_mastery_row[0] or 72.4), 1)

    # 6. Overall Institutional Health Score (Composite 0-100)
    avg_inst_att = sum(d["avg_attendance"] for d in department_analytics) / max(1, len(department_analytics)) if department_analytics else 78.0
    avg_inst_prog = sum(d["avg_progress"] for d in department_analytics) / max(1, len(department_analytics)) if department_analytics else 65.0
    institutional_health_score = round(avg_inst_att * 0.4 + avg_inst_prog * 0.35 + (100.0 - (sum(d["high_risk_count"] for d in department_analytics) / max(1, total_students) * 100.0)) * 0.25, 1)

    conn.close()

    return jsonify({
        "success": True,
        "institution_id": inst_id,
        "kpis": {
            "total_students": total_students,
            "total_faculty": total_faculty,
            "total_subjects": total_subjects,
            "institutional_health_score": institutional_health_score,
            "curriculum_modules_count": total_modules,
            "curriculum_topics_count": total_topics,
            "institutional_avg_mastery": avg_mastery
        },
        "department_heatmaps": department_analytics,
        "year_level_attrition": year_analytics,
        "interventions_analytics": {
            "total_dispatched": total_it,
            "completed_resolved": completed_it,
            "active_pending": active_it,
            "urgent_pending": urgent_it,
            "resolution_rate_percentage": resolution_rate,
            "top_active_faculty": top_faculty_interventions
        },
        "executive_dean_recommendations": [
            {
                "priority": "High",
                "department": department_analytics[0]["department"] if department_analytics else "Computer Science",
                "action": "Conduct mid-term remedial review for cohorts with estimated pass-rate below 75%."
            },
            {
                "priority": "Medium",
                "department": "Institutional",
                "action": "Ensure 100% resolution of urgent faculty remedial interventions within 5 calendar days."
            },
            {
                "priority": "Enrichment",
                "department": "Academic Affairs",
                "action": "Incorporate adaptive topic quizzes across all semester 3 and 4 core laboratory subjects."
            }
        ]
    })

