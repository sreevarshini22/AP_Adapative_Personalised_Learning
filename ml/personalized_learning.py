"""
Personalized Learning and Adaptive Recommendation Engine
AP Adaptive Education Platform

Generates curriculum-grounded, institution-specific adaptive recommendations.
Implements the continuous closed feedback loop:
Predict -> Identify Gap -> Grounded Recommendation -> Student Learns ->
Assess/Quiz -> Update Mastery -> Re-Predict -> Next Recommendation
"""

import os
import sys
from typing import Dict, Any, List, Optional
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.predict import predict_student_risk
from backend.database import get_db_connection


def analyze_student_subjects(student_data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """
    Analyzes subject-level performance dynamically from relational database or student dict.
    Categorizes into Weak (<60%), Moderate (60-79%), and Strong (>=80%).
    Curriculum-Agnostic: works for any institution, program, or subject.
    """
    student_id = student_data.get("id")
    should_close = False
    if conn is None:
        try:
            conn = get_db_connection()
            should_close = True
        except Exception:
            conn = None

    subjects_analyzed = []
    
    # 1. Attempt relational retrieval from database
    if conn and student_id:
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT s.id as subject_id, s.subject_code, s.subject_name,
                   COALESCE(ssp.attendance, st.attendance, 75.0) as attendance,
                   COALESCE(ssp.assessment_score, 65.0) as assessment_score,
                   COALESCE(ssp.quiz_score, 65.0) as quiz_score,
                   COALESCE(ssp.assignment_score, 70.0) as assignment_score,
                   COALESCE(ssp.lab_score, 70.0) as lab_score,
                   COALESCE(ssp.overall_score, 67.0) as overall_score,
                   COALESCE(ssp.mastery_score, 65.0) as mastery_score
            FROM student_subjects ss
            JOIN subjects s ON ss.subject_id = s.id
            LEFT JOIN students st ON st.id = ss.student_id
            LEFT JOIN student_subject_performance ssp ON ssp.student_id = ss.student_id AND ssp.subject_id = s.id
            WHERE ss.student_id = ?
            ORDER BY s.subject_code ASC
            """, (student_id,))
            rows = cursor.fetchall()
            
            for r in rows:
                score = float(r["overall_score"] if r["overall_score"] is not None else 65.0)
                mastery = float(r["mastery_score"] if r["mastery_score"] is not None else score)
                subjects_analyzed.append({
                    "subject_id": r["subject_id"],
                    "subject_code": r["subject_code"],
                    "subject": r["subject_name"],
                    "score": round(score, 1),
                    "mastery": round(mastery, 1),
                    "attendance": float(r["attendance"]),
                    "assessment_score": float(r["assessment_score"]),
                    "quiz_score": float(r["quiz_score"])
                })
        except Exception as e:
            print(f"[Subject Analysis Relational Fallback]: {e}")

    # 2. Fallback to enrolled subject lookup by branch/year/sem if student_subjects empty
    if not subjects_analyzed and conn and student_id:
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT s.id as subject_id, s.subject_code, s.subject_name
            FROM subjects s
            JOIN students st ON st.id = ?
            WHERE s.branch = st.branch AND s.year = st.year AND s.semester = st.semester
            LIMIT 6
            """, (student_id,))
            rows = cursor.fetchall()
            base_score = float(student_data.get("overall_progress", 65.0) or 65.0)
            for idx, r in enumerate(rows):
                # Apply slight variance for realistic diagnostic spread
                subj_score = max(35.0, min(95.0, base_score + ((idx % 3 - 1) * 12.0)))
                subjects_analyzed.append({
                    "subject_id": r["subject_id"],
                    "subject_code": r["subject_code"],
                    "subject": r["subject_name"],
                    "score": round(subj_score, 1),
                    "mastery": round(subj_score, 1),
                    "attendance": float(student_data.get("attendance", 75.0) or 75.0),
                    "assessment_score": round(subj_score, 1),
                    "quiz_score": round(subj_score, 1)
                })
        except Exception:
            pass

    # 3. Ultimate Fallback to generic subject structure if no DB records found
    if not subjects_analyzed:
        legacy_map = {
            "Programming": student_data.get("programming_score", 65.0),
            "Data Structures": student_data.get("data_structures_score", 65.0),
            "Database Systems": student_data.get("database_score", 65.0),
            "Mathematics": student_data.get("mathematics_score", 65.0),
            "Physics": student_data.get("physics_score", 65.0),
            "Communication Skills": student_data.get("communication_score", 70.0)
        }
        for s_name, s_val in legacy_map.items():
            sc = float(s_val or 65.0)
            subjects_analyzed.append({
                "subject_id": None,
                "subject_code": s_name[:3].upper() + "101",
                "subject": s_name,
                "score": round(sc, 1),
                "mastery": round(sc, 1),
                "attendance": float(student_data.get("attendance", 75.0) or 75.0),
                "assessment_score": round(sc, 1),
                "quiz_score": round(sc, 1)
            })

    weak = []
    moderate = []
    strong = []

    for item in subjects_analyzed:
        sc = item["score"]
        if sc < 60.0:
            item["status"] = "Weak"
            item["badge_color"] = "danger"
            item["recommendation_priority"] = "Priority 1 (Targeted Remediation Required)"
            weak.append(item)
        elif sc < 80.0:
            item["status"] = "Moderate"
            item["badge_color"] = "warning"
            item["recommendation_priority"] = "Priority 2 (Skill Reinforcement & Practice)"
            moderate.append(item)
        else:
            item["status"] = "Strong"
            item["badge_color"] = "success"
            item["recommendation_priority"] = "Maintenance (Enrichment & Advanced Mastery)"
            strong.append(item)

    weak.sort(key=lambda x: x["score"])
    moderate.sort(key=lambda x: x["score"])
    strong.sort(key=lambda x: x["score"], reverse=True)

    if should_close and conn:
        conn.close()

    return {
        "weak_subjects": weak,
        "moderate_subjects": moderate,
        "strong_subjects": strong,
        "all_subjects": subjects_analyzed,
        "total_subjects": len(subjects_analyzed),
        "weak_count": len(weak),
        "moderate_count": len(moderate),
        "strong_count": len(strong)
    }


def generate_personalized_learning_path(
    student_data: Dict[str, Any],
    prediction_info: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Generates a personalized, step-by-step adaptive learning path grounded strictly
    in the student's authorized institutional curriculum, active semester, and topic mastery.
    """
    should_close = False
    if conn is None:
        try:
            conn = get_db_connection()
            should_close = True
        except Exception:
            conn = None

    if prediction_info is None:
        prediction_info = predict_student_risk(student_data, conn=conn)

    subject_analysis = analyze_student_subjects(student_data, conn=conn)
    risk_level = prediction_info.get("risk_level", "Low Risk")
    study_hours = float(student_data.get("study_hours", 6.0) or 6.0)
    student_id = student_data.get("id")

    learning_path = []
    step_number = 1

    # Attempt to pull grounded topic hierarchy and resources from DB
    if conn and subject_analysis["all_subjects"]:
        cursor = conn.cursor()
        
        # 1. Process WEAK subjects first (lowest scores = highest urgency)
        for subj in subject_analysis["weak_subjects"]:
            s_id = subj.get("subject_id")
            if not s_id:
                continue
                
            # Fetch topics with student mastery
            cursor.execute("""
            SELECT t.id as topic_id, t.topic_name, t.difficulty, t.description,
                   m.module_number, m.module_name,
                   COALESCE(stm.mastery_score, 45.0) as topic_mastery,
                   COALESCE(stm.attempts, 0) as attempts,
                   lr.title as resource_title, lr.file_name as resource_file, lr.source as resource_source
            FROM topics t
            JOIN modules m ON t.module_id = m.id
            LEFT JOIN student_topic_mastery stm ON stm.topic_id = t.id AND stm.student_id = ?
            LEFT JOIN learning_resources lr ON lr.topic_id = t.id AND lr.authorization_status = 'authorized'
            WHERE t.subject_id = ?
            ORDER BY COALESCE(stm.mastery_score, 45.0) ASC, t.order_number ASC
            LIMIT 3
            """, (student_id or 0, s_id))
            topic_rows = cursor.fetchall()

            for tr in topic_rows:
                topic_mast = float(tr["topic_mastery"])
                source_doc = tr["resource_file"] or "Official Institution Syllabus & Approved Notes"
                learning_path.append({
                    "step": step_number,
                    "subject": subj["subject"],
                    "subject_code": subj.get("subject_code", ""),
                    "subject_id": s_id,
                    "topic_id": tr["topic_id"],
                    "module": f"Module {tr['module_number']}: {tr['module_name']}",
                    "title": f"Grounded Topic: {tr['topic_name']}",
                    "topic_name": tr["topic_name"],
                    "difficulty": tr["difficulty"] or "Beginner",
                    "estimated_time": "3.5 Hours",
                    "current_mastery": f"{topic_mast:.0f}%",
                    "learning_objective": tr["description"] or f"Master foundational principles of {tr['topic_name']}.",
                    "phase": "Remedial & Gap Remediation",
                    "reason": f"Targeted gap closure: Topic mastery is at {topic_mast:.0f}% (Subject average: {subj['score']}%)",
                    "status": "In Progress" if step_number == 1 else "Pending",
                    "badge": "Urgent",
                    "priority": "High",
                    "grounded_source": source_doc,
                    "action_type": "Lesson + Diagnostic Quiz"
                })
                step_number += 1

        # 2. Process MODERATE subjects
        for subj in subject_analysis["moderate_subjects"]:
            s_id = subj.get("subject_id")
            if not s_id or step_number > 6:
                continue
                
            cursor.execute("""
            SELECT t.id as topic_id, t.topic_name, t.difficulty, t.description,
                   m.module_number, m.module_name,
                   COALESCE(stm.mastery_score, 68.0) as topic_mastery,
                   lr.file_name as resource_file
            FROM topics t
            JOIN modules m ON t.module_id = m.id
            LEFT JOIN student_topic_mastery stm ON stm.topic_id = t.id AND stm.student_id = ?
            LEFT JOIN learning_resources lr ON lr.topic_id = t.id AND lr.authorization_status = 'authorized'
            WHERE t.subject_id = ?
            ORDER BY t.order_number ASC
            LIMIT 2
            """, (student_id or 0, s_id))
            topic_rows = cursor.fetchall()

            for tr in topic_rows:
                topic_mast = float(tr["topic_mastery"])
                source_doc = tr["resource_file"] or "Official Institution Syllabus"
                learning_path.append({
                    "step": step_number,
                    "subject": subj["subject"],
                    "subject_code": subj.get("subject_code", ""),
                    "subject_id": s_id,
                    "topic_id": tr["topic_id"],
                    "module": f"Module {tr['module_number']}: {tr['module_name']}",
                    "title": f"Skill Practice: {tr['topic_name']}",
                    "topic_name": tr["topic_name"],
                    "difficulty": tr["difficulty"] or "Intermediate",
                    "estimated_time": "4 Hours",
                    "current_mastery": f"{topic_mast:.0f}%",
                    "learning_objective": tr["description"] or f"Elevate competency in {tr['topic_name']}.",
                    "phase": "Skill Reinforcement",
                    "reason": f"Competency booster: Elevate {subj['subject']} to mastery (>80%)",
                    "status": "Pending",
                    "badge": "Core",
                    "priority": "Medium",
                    "grounded_source": source_doc,
                    "action_type": "Practice & Lab Exercise"
                })
                step_number += 1

        # 3. Process STRONG subjects
        for subj in subject_analysis["strong_subjects"]:
            s_id = subj.get("subject_id")
            if not s_id or step_number > 8:
                continue
                
            cursor.execute("""
            SELECT t.id as topic_id, t.topic_name, t.difficulty, t.description,
                   m.module_number, m.module_name,
                   COALESCE(stm.mastery_score, 85.0) as topic_mastery
            FROM topics t
            JOIN modules m ON t.module_id = m.id
            LEFT JOIN student_topic_mastery stm ON stm.topic_id = t.id AND stm.student_id = ?
            WHERE t.subject_id = ?
            ORDER BY t.order_number DESC
            LIMIT 1
            """, (student_id or 0, s_id))
            topic_rows = cursor.fetchall()

            for tr in topic_rows:
                learning_path.append({
                    "step": step_number,
                    "subject": subj["subject"],
                    "subject_code": subj.get("subject_code", ""),
                    "subject_id": s_id,
                    "topic_id": tr["topic_id"],
                    "module": f"Module {tr['module_number']}: {tr['module_name']}",
                    "title": f"Advanced Mastery: {tr['topic_name']}",
                    "topic_name": tr["topic_name"],
                    "difficulty": "Advanced",
                    "estimated_time": "4.5 Hours",
                    "current_mastery": f"{float(tr['topic_mastery']):.0f}%",
                    "learning_objective": tr["description"] or f"Capstone mastery of {tr['topic_name']}.",
                    "phase": "Advanced Enrichment",
                    "reason": f"Excellence track: Advanced competency in {subj['subject']}",
                    "status": "Pending",
                    "badge": "Advanced",
                    "priority": "Low",
                    "grounded_source": "Approved Advanced Reference Text",
                    "action_type": "Advanced Assessment"
                })
                step_number += 1

    # Fallback if no database topics were retrieved
    if not learning_path:
        for subj in subject_analysis["all_subjects"][:4]:
            learning_path.append({
                "step": step_number,
                "subject": subj["subject"],
                "subject_code": subj.get("subject_code", ""),
                "subject_id": subj.get("subject_id"),
                "module": "Unit 1: Core Fundamentals",
                "title": f"Grounded Review: {subj['subject']}",
                "topic_name": f"{subj['subject']} Core Concepts",
                "difficulty": "Intermediate",
                "estimated_time": "4 Hours",
                "current_mastery": f"{subj['score']:.0f}%",
                "learning_objective": f"Review and master syllabus objectives for {subj['subject']}.",
                "phase": "Core Curriculum",
                "reason": f"Structured syllabus progression for {subj['subject']}",
                "status": "In Progress" if step_number == 1 else "Pending",
                "badge": "Core",
                "priority": "Medium",
                "grounded_source": "Official Institution Syllabus",
                "action_type": "Lesson + Quiz"
            })
            step_number += 1

    if should_close and conn:
        conn.close()

    total_hours_est = len(learning_path) * 4.0
    weeks_needed = max(1, round(total_hours_est / max(1.0, study_hours)))

    return {
        "learning_path": learning_path,
        "total_modules": len(learning_path),
        "estimated_total_hours": round(total_hours_est, 1),
        "recommended_weekly_hours": max(8.0, study_hours + (4.0 if risk_level == "High Risk" else 0.0)),
        "estimated_completion_weeks": weeks_needed,
        "subject_breakdown": subject_analysis,
        "path_focus": "Targeted Recovery" if risk_level == "High Risk" else ("Skill Elevation" if risk_level == "Medium Risk" else "Advanced Honors Track"),
        "adaptive_loop_status": "Active (Continuous Feedback Enabled)"
    }


def update_student_topic_mastery_and_repredict(
    student_id: int,
    topic_id: int,
    quiz_score_pct: float,
    time_spent_min: float = 15.0,
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Executes the next cycle of the Adaptive Feedback Loop:
    1. Records quiz score & time in student_topic_mastery.
    2. Recalculates new topic mastery score: new_mastery = (0.6 * quiz_score) + (0.4 * previous_mastery).
    3. Updates student_subject_performance.
    4. Re-evaluates ML/QML learner risk.
    5. Returns updated predictions and the next recommended learning action.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    cursor = conn.cursor()

    # Get topic and subject info
    cursor.execute("SELECT id, subject_id, topic_name FROM topics WHERE id = ?", (topic_id,))
    topic_row = cursor.fetchone()
    if not topic_row:
        if should_close:
            conn.close()
        raise ValueError(f"Topic {topic_id} not found.")

    subject_id = topic_row["subject_id"]
    topic_name = topic_row["topic_name"]

    # Fetch existing mastery
    cursor.execute("""
    SELECT mastery_score, attempts FROM student_topic_mastery
    WHERE student_id = ? AND topic_id = ?
    """, (student_id, topic_id))
    existing = cursor.fetchone()

    if existing:
        prev_mastery = float(existing["mastery_score"])
        attempts = int(existing["attempts"]) + 1
        new_mastery = round((0.6 * quiz_score_pct) + (0.4 * prev_mastery), 1)
        status = "mastered" if new_mastery >= 80.0 else ("needs_revision" if new_mastery < 60.0 else "in_progress")
        cursor.execute("""
        UPDATE student_topic_mastery
        SET mastery_score = ?, quiz_score = ?, attempts = ?, time_spent_minutes = time_spent_minutes + ?,
            status = ?, last_activity = CURRENT_TIMESTAMP
        WHERE student_id = ? AND topic_id = ?
        """, (new_mastery, quiz_score_pct, attempts, time_spent_min, status, student_id, topic_id))
    else:
        prev_mastery = 50.0
        attempts = 1
        new_mastery = round((0.6 * quiz_score_pct) + (0.4 * 50.0), 1)
        status = "mastered" if new_mastery >= 80.0 else ("needs_revision" if new_mastery < 60.0 else "in_progress")
        cursor.execute("""
        INSERT INTO student_topic_mastery (student_id, topic_id, subject_id, mastery_score, quiz_score, attempts, time_spent_minutes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (student_id, topic_id, subject_id, new_mastery, quiz_score_pct, attempts, time_spent_min, status))

    # Log student activity
    cursor.execute("""
    INSERT INTO student_activity_logs (student_id, activity_type, subject_id, topic_id, score, duration_seconds)
    VALUES (?, 'quiz_completed', ?, ?, ?, ?)
    """, (student_id, subject_id, topic_id, quiz_score_pct, int(time_spent_min * 60)))

    # Update student subject performance average
    cursor.execute("SELECT AVG(mastery_score) FROM student_topic_mastery WHERE student_id = ? AND subject_id = ?", (student_id, subject_id))
    avg_mast = cursor.fetchone()[0] or new_mastery
    cursor.execute("""
    INSERT INTO student_subject_performance (student_id, subject_id, quiz_score, mastery_score, overall_score)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(student_id, subject_id) DO UPDATE SET
        quiz_score = (student_subject_performance.quiz_score * 0.4 + ? * 0.6),
        mastery_score = ?,
        overall_score = (student_subject_performance.attendance * 0.2 + student_subject_performance.assessment_score * 0.3 + ? * 0.3 + ? * 0.2),
        last_updated = CURRENT_TIMESTAMP
    """, (student_id, subject_id, quiz_score_pct, avg_mast, avg_mast, quiz_score_pct, avg_mast, quiz_score_pct, avg_mast))

    conn.commit()

    # Fetch updated student profile for reprediction
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    st_row = cursor.fetchone()
    st_dict = dict(st_row) if st_row else {}

    # Run ML/QML Re-prediction
    updated_prediction = predict_student_risk(st_dict, conn=conn)
    updated_learning_path = generate_personalized_learning_path(st_dict, updated_prediction, conn=conn)

    if should_close:
        conn.close()

    return {
        "success": True,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "previous_mastery": prev_mastery,
        "quiz_score": quiz_score_pct,
        "new_mastery": new_mastery,
        "mastery_status": status,
        "updated_prediction": updated_prediction,
        "next_recommendations": updated_learning_path["learning_path"][:3]
    }
