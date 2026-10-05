"""
Data Model Serializers and Helper Mappings for AP Adaptive Education Platform
Ensures passwords and password hashes are never leaked to responses.
Supports dynamic multi-institution curriculum entities.
"""

def serialize_user(row):
    """Serializes user DB row, strictly excluding password and password_hash."""
    if not row:
        return None
    keys = row.keys()
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "full_name": row["full_name"],
        "institution_id": row["institution_id"] if "institution_id" in keys else None,
        "institution_name": row["institution_name"] if "institution_name" in keys else "",
        "institution_code": row["institution_code"] if "institution_code" in keys else "",
        "district": row["district"] if "district" in keys else "",
        "state": row["state"] if "state" in keys else "",
        "created_at": str(row["created_at"]) if "created_at" in keys else None
    }

def serialize_teacher(row):
    """Serializes teacher record, strictly excluding passwords."""
    if not row:
        return None
    keys = row.keys()
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in keys else None,
        "full_name": row["full_name"],
        "email": row["email"],
        "branch": row["branch"] if "branch" in keys else "",
        "department": row["department"] if "department" in keys else "",
        "designation": row["designation"] if "designation" in keys else "Faculty",
        "year": row["year"] if "year" in keys else "",
        "section": row["section"] if "section" in keys else "",
        "institution_id": row["institution_id"] if "institution_id" in keys else None,
        "program_id": row["program_id"] if "program_id" in keys else None,
        "created_at": str(row["created_at"]) if "created_at" in keys else None
    }

def serialize_student(row):
    """
    Serializes student DB row into clean dictionary.
    Excludes sensitive user auth details and password hashes.
    """
    if not row:
        return None
    keys = row.keys()
    data = {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in keys else None,
        "full_name": row["full_name"],
        "roll_no": row["roll_no"],
        "email": row["email"],
        "year": row["year"],
        "branch": row["branch"],
        "section": row["section"],
        "semester": row["semester"],
        "attendance": float(row["attendance"]) if "attendance" in keys and row["attendance"] is not None else 75.0,
        "overall_progress": float(row["overall_progress"]) if "overall_progress" in keys and row["overall_progress"] is not None else 50.0,
        "study_hours": float(row["study_hours"]) if "study_hours" in keys and row["study_hours"] is not None else 8.0,
        "learning_activity": float(row["learning_activity"]) if "learning_activity" in keys and row["learning_activity"] is not None else 60.0,
        "previous_performance": float(row["previous_performance"]) if "previous_performance" in keys and row["previous_performance"] is not None else 65.0,
        "learning_streak": int(row["learning_streak"]) if "learning_streak" in keys and row["learning_streak"] is not None else 3,
        "institution_id": row["institution_id"] if "institution_id" in keys else None,
        "program_id": row["program_id"] if "program_id" in keys else None,
        "curriculum_version_id": row["curriculum_version_id"] if "curriculum_version_id" in keys else None,
        "teacher_id": row["teacher_id"] if "teacher_id" in keys else None,
        "class_id": row["class_id"] if "class_id" in keys else None,
        "regulation": row["regulation"] if "regulation" in keys else "R23",
        "academic_year": row["academic_year"] if "academic_year" in keys else "2024-2025",
        "is_demo": bool(row["is_demo"]) if "is_demo" in keys else False,
        "notes": row["notes"] if "notes" in keys and row["notes"] else "",
        "created_at": str(row["created_at"]) if "created_at" in keys else None
    }
    # Optional legacy fallback scores if present
    for k in ["mathematics_score", "physics_score", "programming_score", "data_structures_score", "database_score", "communication_score", "assignment_score", "quiz_score", "exam_score"]:
        if k in keys and row[k] is not None:
            data[k] = float(row[k])
    return data

def serialize_institution(row):
    """Serializes institution entity."""
    if not row:
        return None
    keys = row.keys()
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "institution_type": row["institution_type"] if "institution_type" in keys else "University",
        "state": row["state"] if "state" in keys else "Andhra Pradesh",
        "district": row["district"] if "district" in keys else "",
        "website": row["website"] if "website" in keys else "",
        "contact_email": row["contact_email"] if "contact_email" in keys else "",
        "is_demo": bool(row["is_demo"]) if "is_demo" in keys else False,
        "status": row["status"] if "status" in keys else "active"
    }

def serialize_subject(row):
    """Serializes subject entity."""
    if not row:
        return None
    keys = row.keys()
    return {
        "id": row["id"],
        "subject_code": row["subject_code"],
        "subject_name": row["subject_name"],
        "branch": row["branch"] if "branch" in keys else "",
        "year": row["year"] if "year" in keys else "",
        "semester": row["semester"] if "semester" in keys else 1,
        "credits": row["credits"] if "credits" in keys else 3,
        "subject_type": row["subject_type"] if "subject_type" in keys else "theory",
        "description": row["description"] if "description" in keys else "",
        "institution_id": row["institution_id"] if "institution_id" in keys else None,
        "program_id": row["program_id"] if "program_id" in keys else None,
        "curriculum_version_id": row["curriculum_version_id"] if "curriculum_version_id" in keys else None,
        "status": row["status"] if "status" in keys else "published"
    }

def serialize_intervention(row):
    """Serializes intervention record."""
    if not row:
        return None
    keys = row.keys()
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "teacher_id": row["teacher_id"] if "teacher_id" in keys else None,
        "risk_level": row["risk_level"],
        "title": row["title"],
        "category": row["category"],
        "priority": row["priority"],
        "description": row["description"],
        "status": row["status"] if "status" in keys else "Active",
        "notes": row["notes"] if "notes" in keys and row["notes"] else "",
        "created_at": str(row["created_at"]) if "created_at" in keys else None
    }
