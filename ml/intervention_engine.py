import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.personalized_learning import analyze_student_subjects
from ml.predict import predict_student_risk

def generate_teacher_interventions(student_data, prediction_info=None):
    """
    Synthesizes ML risk level, subject vulnerabilities, and behavioral patterns
    into a comprehensive teacher intervention action plan.
    """
    if prediction_info is None:
        prediction_info = predict_student_risk(student_data)
        
    risk_level = prediction_info["risk_level"]
    risk_score = prediction_info["risk_score"]
    subject_analysis = analyze_student_subjects(student_data)
    
    attendance = float(student_data.get("attendance", 75.0) or 75.0)
    study_hours = float(student_data.get("study_hours", 6.0) or 6.0)
    learning_activity = float(student_data.get("learning_activity", 60.0) or 60.0)
    
    interventions = []
    
    # 1. Primary Risk-Based Core Strategy
    if risk_level == "High Risk":
        interventions.append({
            "category": "Immediate Faculty Counseling",
            "priority": "Critical (Level 1)",
            "badge_color": "danger",
            "title": "Mandatory 1-on-1 Academic Advising Meeting",
            "description": f"Schedule an in-person diagnostic meeting within 48 hours to discuss risk indicators (Risk Index: {risk_score}%). Identify external impediments, mental health or conceptual roadblocks.",
            "action_items": [
                "Schedule 30-minute faculty mentor consultation",
                "Review recent mid-term and quiz answer scripts together",
                "Establish a customized 4-week recovery milestone contract"
            ],
            "recommended_timeline": "Within 48 Hours"
        })
        
        if attendance < 65.0:
            interventions.append({
                "category": "Attendance & Dean Alert",
                "priority": "High (Level 2)",
                "badge_color": "danger",
                "title": "Proactive Attendance Monitoring & Parent Communication",
                "description": f"Attendance is currently critical at {attendance}%. Issue formal departmental notification and counsel student regarding minimum semester attendance thresholds.",
                "action_items": [
                    "Issue automated SMS/Email attendance alert to guardian",
                    "Daily attendance verification by Class Section In-charge",
                    "Offer compensatory make-up lab/lecture sessions"
                ],
                "recommended_timeline": "Immediate (This Week)"
            })
            
        interventions.append({
            "category": "Remedial Coaching",
            "priority": "High (Level 2)",
            "badge_color": "warning",
            "title": "Paced Remedial Tutoring & Peer Study Group",
            "description": "Enroll student into guided remedial evening tutorials and assign a high-performing peer study partner from Section A.",
            "action_items": [
                "Assign peer study buddy from top academic quartile",
                "Mandatory attendance at weekly subject remedial tutorials",
                "Weekly micro-quiz to evaluate progressive retention"
            ],
            "recommended_timeline": "Ongoing Weekly"
        })

    elif risk_level == "Medium Risk":
        interventions.append({
            "category": "Targeted Reinforcement",
            "priority": "Moderate (Level 2)",
            "badge_color": "warning",
            "title": "Weekly Progress Monitoring & Guided Problem Sets",
            "description": f"Student exhibits moderate learning risk ({risk_score}%). Provide guided problem-solving sheets and check weekly assignment submissions.",
            "action_items": [
                "Review bi-weekly assignment completion rate",
                "Provide step-by-step problem breakdown sheets for weak modules",
                "Schedule a 15-minute checkpoint before mid-term assessments"
            ],
            "recommended_timeline": "Bi-Weekly"
        })
        
        if learning_activity < 55.0:
            interventions.append({
                "category": "LMS Engagement Booster",
                "priority": "Moderate (Level 3)",
                "badge_color": "info",
                "title": "Interactive LMS Practice & Quiz Engagement",
                "description": f"LMS interaction score is below cohort average ({learning_activity}/100). Encourage participation in interactive video lessons and formative chapter quizzes.",
                "action_items": [
                    "Assign gamified practice modules on learning portal",
                    "Check weekly quiz attempt logs"
                ],
                "recommended_timeline": "Next 7 Days"
            })
            
    else:  # Low Risk
        interventions.append({
            "category": "Enrichment & Leadership",
            "priority": "Standard (Level 3)",
            "badge_color": "success",
            "title": "Advanced Honors Project & Peer Mentor Role",
            "description": f"Student is performing exceptionally well with low academic risk ({risk_score}%). Offer advanced capstone projects, research paper reading, or peer tutoring leadership roles.",
            "action_items": [
                "Invite student to participate in inter-college hackathons / IEEE coding challenge",
                "Nominate as peer mentor for junior/struggling students in lab sessions",
                "Provide elective advanced modules (e.g. Distributed Systems, Neural Architectures)"
            ],
            "recommended_timeline": "Semester Long"
        })

    # 2. Specific Weak-Subject Action Recommendations
    for weak_item in subject_analysis["weak_subjects"]:
        subj_name = weak_item["subject"]
        score = weak_item["score"]
        interventions.append({
            "category": f"Subject Remediation: {subj_name}",
            "priority": "High (Subject Gap)",
            "badge_color": "danger",
            "title": f"Targeted Diagnostic Drill for {subj_name}",
            "description": f"Student scored {score}% in {subj_name}. Provide focused remedial resources and verify conceptual fundamentals.",
            "action_items": [
                f"Assign curated {subj_name} problem sheet focusing on foundational topics",
                f"Schedule 1-on-1 doubt clarification during faculty office hours",
                f"Require re-submission of key {subj_name} assignment exercises"
            ],
            "recommended_timeline": "Next 10 Days"
        })

    return {
        "student_risk_level": risk_level,
        "risk_score": risk_score,
        "total_interventions": len(interventions),
        "interventions": interventions,
        "summary_recommendation": (
            "Urgent direct faculty intervention and remedial plan required." if risk_level == "High Risk"
            else "Targeted weekly progress tracking and supplemental practice recommended." if risk_level == "Medium Risk"
            else "Maintain current pace and provide advanced enrichment opportunities."
        )
    }
