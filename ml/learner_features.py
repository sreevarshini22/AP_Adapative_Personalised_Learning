"""
Universal Learner Features Module for AP Adaptive Education Platform
Curriculum-Agnostic Feature Engineering for Classical and Quantum Machine Learning.

This module computes universal, curriculum-independent student learning features from:
1. Dynamic relational subject performances (student_subject_performance)
2. Dynamic topic masteries (student_topic_mastery)
3. Granular student activity logs (student_activity_logs)
4. Traditional student record profile (fallback/cached fields)

Universal Features:
1. attendance: Percentage of scheduled instructional sessions attended [0-100]
2. assessment_performance: Weighted mean of all subject midterm/major assessment marks [0-100]
3. quiz_performance: Mean percentage scored across all topic and subject diagnostic quizzes [0-100]
4. assignment_performance: Quality score of submitted assignments and problem sets [0-100]
5. lab_performance: Practical experiment execution and laboratory performance [0-100]
6. topic_mastery: Aggregate mastery percentage across all syllabus topics [0-100]
7. learning_engagement: Normalized index combining streak, study hours, and resource views [0-100]
8. previous_performance: Historical cumulative grade point performance [0-100]
9. overall_progress: Proportion of curriculum modules/lessons completed [0-100]
"""

import os
import sys
import numpy as np
from typing import Dict, Any, List, Optional

# Universal 8-feature specification for multi-model benchmarking
UNIVERSAL_FEATURE_KEYS = [
    "attendance",
    "assessment_performance",
    "quiz_performance",
    "assignment_performance",
    "lab_performance",
    "topic_mastery",
    "learning_engagement",
    "previous_performance"
]

UNIVERSAL_FEATURE_DESCRIPTIONS = {
    "attendance": "Classroom & Virtual Lecture Attendance Rate (%)",
    "assessment_performance": "Midterm & Subject Examination Weighted Mean (%)",
    "quiz_performance": "Curriculum-Grounded Diagnostic Quiz Score (%)",
    "assignment_performance": "Assignment & Problem Set Completion Score (%)",
    "lab_performance": "Laboratory & Practical Experiment Mastery (%)",
    "topic_mastery": "Syllabus Topic Competency Level (%)",
    "learning_engagement": "LMS Engagement Index (Streak, Time, Resource Views) (%)",
    "previous_performance": "Historical Academic GPA Baseline (%)"
}

FEATURE_BENCHMARKS = {
    "attendance": 75.0,
    "assessment_performance": 60.0,
    "quiz_performance": 60.0,
    "assignment_performance": 65.0,
    "lab_performance": 65.0,
    "topic_mastery": 60.0,
    "learning_engagement": 60.0,
    "previous_performance": 65.0
}


def extract_universal_learner_features(student_dict: Optional[Any] = None, conn=None, student_id: Optional[int] = None) -> Dict[str, float]:
    """
    Computes curriculum-independent learner features from student dictionary and/or database relations.
    Guarantees no hard-coded subject names are used.
    """
    if student_dict is None and student_id is not None:
        student_dict = {"id": student_id}
    elif isinstance(student_dict, (int, str)):
        student_dict = {"id": int(student_dict)}
    elif not isinstance(student_dict, dict):
        student_dict = {}

    student_id = student_dict.get("id") or student_id
    
    # 1. Base scalar features
    attendance = float(student_dict.get("attendance", 75.0) or 75.0)
    previous_perf = float(student_dict.get("previous_performance", 65.0) or 65.0)
    study_hours = float(student_dict.get("study_hours", 6.0) or 6.0)
    streak = int(student_dict.get("learning_streak", 3) or 3)
    learning_act = float(student_dict.get("learning_activity", 60.0) or 60.0)
    
    # 2. Extract from relational performance if database connection is available
    if conn and student_id:
        try:
            cursor = conn.cursor()
            
            # Fetch relational subject performances
            cursor.execute("""
            SELECT AVG(attendance) as avg_att,
                   AVG(assessment_score) as avg_assess,
                   AVG(assignment_score) as avg_assign,
                   AVG(quiz_score) as avg_quiz,
                   AVG(lab_score) as avg_lab,
                   AVG(overall_score) as avg_overall,
                   AVG(mastery_score) as avg_mastery
            FROM student_subject_performance
            WHERE student_id = ?
            """, (student_id,))
            perf_row = cursor.fetchone()
            
            if perf_row and perf_row[0] is not None:
                if perf_row["avg_att"] is not None:
                    attendance = float(perf_row["avg_att"])
                assess_perf = float(perf_row["avg_assess"] or 65.0)
                assign_perf = float(perf_row["avg_assign"] or 70.0)
                quiz_perf = float(perf_row["avg_quiz"] or 65.0)
                lab_perf = float(perf_row["avg_lab"] or 70.0)
                topic_mast = float(perf_row["avg_mastery"] or 60.0)
            else:
                # Fallback to topic mastery table if available
                cursor.execute("SELECT AVG(mastery_score) FROM student_topic_mastery WHERE student_id = ?", (student_id,))
                mast_row = cursor.fetchone()
                topic_mast = float(mast_row[0]) if mast_row and mast_row[0] is not None else 60.0
                
                assess_perf = float(student_dict.get("exam_score", 65.0) or 65.0)
                quiz_perf = float(student_dict.get("quiz_score", 65.0) or 65.0)
                assign_perf = float(student_dict.get("assignment_score", 70.0) or 70.0)
                lab_perf = 70.0
        except Exception:
            assess_perf = float(student_dict.get("exam_score", 65.0) or 65.0)
            quiz_perf = float(student_dict.get("quiz_score", 65.0) or 65.0)
            assign_perf = float(student_dict.get("assignment_score", 70.0) or 70.0)
            lab_perf = 70.0
            topic_mast = 60.0
    else:
        # Fallback from student dictionary keys
        assess_perf = float(student_dict.get("assessment_performance", student_dict.get("exam_score", 65.0)) or 65.0)
        quiz_perf = float(student_dict.get("quiz_performance", student_dict.get("quiz_score", 65.0)) or 65.0)
        assign_perf = float(student_dict.get("assignment_performance", student_dict.get("assignment_score", 70.0)) or 70.0)
        lab_perf = float(student_dict.get("lab_performance", 70.0) or 70.0)
        topic_mast = float(student_dict.get("topic_mastery", student_dict.get("overall_progress", 60.0)) or 60.0)

    # 3. Calculate Learning Engagement Index [0-100]
    # Combines normalized study hours (up to 15 hrs/wk), streak (up to 7 days), and LMS activity
    norm_study = min(100.0, (study_hours / 15.0) * 100.0)
    norm_streak = min(100.0, (streak / 7.0) * 100.0)
    engagement = round((0.4 * learning_act) + (0.35 * norm_study) + (0.25 * norm_streak), 1)
    
    return {
        "attendance": round(float(np.clip(attendance, 0.0, 100.0)), 1),
        "assessment_performance": round(float(np.clip(assess_perf, 0.0, 100.0)), 1),
        "quiz_performance": round(float(np.clip(quiz_perf, 0.0, 100.0)), 1),
        "assignment_performance": round(float(np.clip(assign_perf, 0.0, 100.0)), 1),
        "lab_performance": round(float(np.clip(lab_perf, 0.0, 100.0)), 1),
        "topic_mastery": round(float(np.clip(topic_mast, 0.0, 100.0)), 1),
        "learning_engagement": round(float(np.clip(engagement, 0.0, 100.0)), 1),
        "previous_performance": round(float(np.clip(previous_perf, 0.0, 100.0)), 1)
    }


def get_5qubit_feature_vector(features: Dict[str, float]) -> List[float]:
    """
    Maps universal learner features into the 5 Qubit inputs:
    - Qubit 0: Class Attendance (%)
    - Qubit 1: Assessment / Exam Performance (%)
    - Qubit 2: Topic Mastery / Quiz Score (%)
    - Qubit 3: Assignment & Practical Score (%)
    - Qubit 4: Learning Engagement Index (%)
    """
    q0 = features.get("attendance", 75.0)
    q1 = features.get("assessment_performance", 65.0)
    q2 = (features.get("topic_mastery", 60.0) * 0.5) + (features.get("quiz_performance", 60.0) * 0.5)
    q3 = (features.get("assignment_performance", 70.0) * 0.6) + (features.get("lab_performance", 70.0) * 0.4)
    q4 = features.get("learning_engagement", 60.0)
    return [q0, q1, q2, q3, q4]


def get_8qubit_feature_vector(features: Dict[str, float]) -> List[float]:
    """
    Maps universal learner features directly to 8 Qubits:
    - Qubit 0: attendance
    - Qubit 1: assessment_performance
    - Qubit 2: quiz_performance
    - Qubit 3: assignment_performance
    - Qubit 4: lab_performance
    - Qubit 5: topic_mastery
    - Qubit 6: learning_engagement
    - Qubit 7: previous_performance
    """
    return [features.get(k, 60.0) for k in UNIVERSAL_FEATURE_KEYS]


# Aliases for convenience
features_to_5qubit_vector = get_5qubit_feature_vector
features_to_8qubit_vector = get_8qubit_feature_vector

