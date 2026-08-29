"""
Data Model Serializers and Helper Mappings for AP Adaptive Education Platform
Ensures passwords and password hashes are never leaked to responses.
"""

def serialize_user(row):
    """Serializes user DB row, strictly excluding password and password_hash."""
    if not row:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "full_name": row["full_name"],
        "created_at": str(row["created_at"]) if "created_at" in row.keys() else None
    }

def serialize_teacher(row):
    """Serializes teacher record, strictly excluding passwords."""
    if not row:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in row.keys() else None,
        "full_name": row["full_name"],
        "email": row["email"],
        "branch": row["branch"] if "branch" in row.keys() else "",
        "year": row["year"] if "year" in row.keys() else "",
        "section": row["section"] if "section" in row.keys() else "",
        "created_at": str(row["created_at"]) if "created_at" in row.keys() else None
    }

def serialize_student(row):
    """
    Serializes student DB row into clean dictionary.
    Excludes sensitive user auth details and password hashes.
    """
    if not row:
        return None
    
    data = {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in row.keys() else None,
        "full_name": row["full_name"],
        "roll_no": row["roll_no"],
        "email": row["email"],
        "year": row["year"],
        "branch": row["branch"],
        "section": row["section"],
        "semester": row["semester"],
        "attendance": float(row["attendance"]),
        "mathematics_score": float(row["mathematics_score"]),
        "physics_score": float(row["physics_score"]),
        "programming_score": float(row["programming_score"]),
        "data_structures_score": float(row["data_structures_score"]),
        "database_score": float(row["database_score"]),
        "communication_score": float(row["communication_score"]),
        "assignment_score": float(row["assignment_score"]),
        "quiz_score": float(row["quiz_score"]),
        "exam_score": float(row["exam_score"]),
        "study_hours": float(row["study_hours"]),
        "learning_activity": float(row["learning_activity"]),
        "previous_performance": float(row["previous_performance"]),
        "overall_progress": float(row["overall_progress"]),
        "notes": row["notes"] if "notes" in row.keys() else "",
        "created_at": str(row["created_at"]) if "created_at" in row.keys() else None
    }
    return data

def serialize_intervention(row):
    """Serializes intervention record."""
    if not row:
        return None
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "teacher_id": row["teacher_id"],
        "risk_level": row["risk_level"],
        "title": row["title"],
        "category": row["category"],
        "priority": row["priority"],
        "description": row["description"],
        "status": row["status"],
        "notes": row["notes"] or "",
        "created_at": str(row["created_at"]) if "created_at" in row.keys() else None
    }
