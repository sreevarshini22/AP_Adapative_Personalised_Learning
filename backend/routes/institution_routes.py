"""
Institution Master REST API Routes
AP Adaptive Education Platform

Provides:
- Public / Authenticated search, cascading filters (State -> District -> Type), pagination
- Admin-only secure dataset import (CSV/XLSX/JSON)
- Dataset version tracking and activation
- Strict RBAC authorization enforcement
"""

import os
from flask import Blueprint, request, jsonify, session
from backend.auth import get_current_user
from backend.institution_service import (
    get_institutions,
    get_institution_by_id,
    get_distinct_states,
    get_distinct_districts,
    get_distinct_types,
    get_dataset_versions_list,
    import_institution_dataset,
    sanitize_formula_injection
)
from backend.database import get_db_connection, log_audit_event

institution_bp = Blueprint("institutions", __name__)


def require_admin_role():
    """
    Helper to enforce admin-only authorization.
    Returns (user_dict, error_response_tuple).
    """
    user = get_current_user()
    if not user:
        return None, (jsonify({"success": False, "message": "Authentication required. Please log in as an administrator."}), 401)
    
    role = user.get("role", "").lower()
    if role not in ["admin", "institution_admin", "state_admin", "super_admin"]:
        return None, (jsonify({
            "success": False,
            "message": f"Forbidden: Account role '{role}' is not authorized to manage the institution master dataset. Only administrators can perform this action."
        }), 403)
    
    return user, None


# =========================================================================
# 1. PUBLIC / AUTHENTICATED SEARCH & QUERY ENDPOINTS
# =========================================================================

@institution_bp.route("/api/institutions", methods=["GET"])
@institution_bp.route("/institutions", methods=["GET"])
def list_institutions():
    """
    Returns paginated and filtered institution records.
    Filters: state, district, institution_type, search, page, per_page
    """
    state = request.args.get("state")
    district = request.args.get("district")
    itype = request.args.get("institution_type", request.args.get("type"))
    search = request.args.get("search", request.args.get("q"))
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", request.args.get("limit", 20))

    result = get_institutions(
        state=state,
        district=district,
        institution_type=itype,
        search=search,
        page=page,
        per_page=per_page
    )
    return jsonify(result)


@institution_bp.route("/api/institutions/search", methods=["GET"])
def search_institutions():
    """Autocomplete search endpoint for institution selection."""
    query = request.args.get("q", request.args.get("search", "")).strip()
    state = request.args.get("state")
    district = request.args.get("district")
    limit = min(50, int(request.args.get("limit", 15)))

    result = get_institutions(
        state=state,
        district=district,
        search=query,
        page=1,
        per_page=limit
    )
    return jsonify(result)


@institution_bp.route("/api/institutions/<int:institution_id>", methods=["GET"])
def get_institution(institution_id):
    """Returns single institution master record."""
    inst = get_institution_by_id(institution_id)
    if not inst:
        return jsonify({"success": False, "message": f"Institution with ID {institution_id} not found."}), 404
    return jsonify({"success": True, "institution": inst})


@institution_bp.route("/api/institutions/states", methods=["GET"])
def list_states():
    """Returns distinct states for cascading dropdowns."""
    states = get_distinct_states()
    return jsonify({"success": True, "states": states})


@institution_bp.route("/api/institutions/districts", methods=["GET"])
def list_districts():
    """Returns distinct districts for cascading dropdowns, optionally filtered by state."""
    state = request.args.get("state")
    districts = get_distinct_districts(state=state)
    return jsonify({"success": True, "state": state, "districts": districts})


@institution_bp.route("/api/institutions/types", methods=["GET"])
def list_institution_types():
    """Returns distinct institution categories/types."""
    types = get_distinct_types()
    return jsonify({"success": True, "types": types})


# =========================================================================
# 2. ADMIN-ONLY DATASET INGESTION & DATASET VERSIONING
# =========================================================================

@institution_bp.route("/api/admin/institutions/import", methods=["POST"])
def admin_import_dataset():
    """
    Admin-only endpoint for uploading and ingesting institution datasets.
    Accepts: multipart/form-data with 'file' (.csv, .xlsx, .json)
    """
    user, err_resp = require_admin_role()
    if err_resp:
        return err_resp

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file part in request. Please attach a CSV, XLSX, or JSON file."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "message": "No file selected."}), 400

    source = request.form.get("source", "AISHE_PORTAL").strip()
    version_tag = request.form.get("version_tag", "").strip() or None

    file_bytes = file.read()
    filename = file.filename

    report = import_institution_dataset(
        file_bytes_or_path=file_bytes,
        filename=filename,
        imported_by=user["id"],
        source=source,
        version_tag=version_tag
    )

    status_code = 200 if report["success"] else 400
    return jsonify(report), status_code


@institution_bp.route("/api/admin/institutions/datasets", methods=["GET"])
def admin_list_datasets():
    """Admin-only endpoint to view history of dataset imports and versioning status."""
    user, err_resp = require_admin_role()
    if err_resp:
        return err_resp

    versions = get_dataset_versions_list()
    return jsonify({"success": True, "versions": versions})


@institution_bp.route("/api/admin/institutions/datasets/<int:version_id>/activate", methods=["POST"])
def admin_activate_dataset_version(version_id):
    """Admin-only endpoint to switch active dataset version."""
    user, err_resp = require_admin_role()
    if err_resp:
        return err_resp

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, version, filename FROM dataset_versions WHERE id = ?", (version_id,))
    v_row = cursor.fetchone()
    if not v_row:
        conn.close()
        return jsonify({"success": False, "message": f"Dataset version ID {version_id} not found."}), 404

    cursor.execute("UPDATE dataset_versions SET status = 'archived' WHERE status = 'active'")
    cursor.execute("UPDATE dataset_versions SET status = 'active' WHERE id = ?", (version_id,))
    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user["id"],
        role=user.get("role", "admin"),
        action="ACTIVATE_DATASET_VERSION",
        entity_type="dataset_versions",
        entity_id=version_id,
        details=f"Admin activated dataset version {v_row['version']} ({v_row['filename']})."
    )

    return jsonify({"success": True, "message": f"Dataset version {v_row['version']} is now active."})


# =========================================================================
# 3. ADMIN-ONLY INSTITUTION RECORD MANAGEMENT (CRUD)
# =========================================================================

@institution_bp.route("/api/admin/institutions", methods=["POST"])
def admin_create_institution():
    """Admin-only manual institution creation with parameterized SQL."""
    user, err_resp = require_admin_role()
    if err_resp:
        return err_resp

    data = request.get_json() or {}
    aishe = sanitize_formula_injection(data.get("aishe_code", "").strip().upper())
    name = sanitize_formula_injection(data.get("institution_name", "").strip())
    itype = sanitize_formula_injection(data.get("institution_type", "Autonomous College").strip())
    univ = sanitize_formula_injection(data.get("university_name", name).strip())
    state = sanitize_formula_injection(data.get("state", "Andhra Pradesh").strip())
    district = sanitize_formula_injection(data.get("district", "Visakhapatnam").strip())
    city = sanitize_formula_injection(data.get("city", district).strip())
    website = sanitize_formula_injection(data.get("website", "").strip())

    if not aishe:
        return jsonify({"success": False, "message": "AISHE code is required."}), 400
    if not name or len(name) < 3:
        return jsonify({"success": False, "message": "Valid institution name is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM institutions WHERE aishe_code = ?", (aishe,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": f"Institution with AISHE code '{aishe}' already exists."}), 400

    cursor.execute("""
    INSERT INTO institutions (
        aishe_code, institution_name, institution_type, university_name,
        state, district, city, website, status, source, source_version,
        code, name
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 'MANUAL_ADMIN', 'v1.0', ?, ?)
    """, (aishe, name, itype, univ, state, district, city, website, aishe, name))
    inst_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user["id"],
        role=user.get("role", "admin"),
        action="CREATE_INSTITUTION",
        entity_type="institutions",
        entity_id=inst_id,
        details=f"Admin created institution {name} ({aishe})."
    )

    return jsonify({"success": True, "message": "Institution created successfully.", "institution_id": inst_id}), 201


@institution_bp.route("/api/admin/institutions/<int:institution_id>", methods=["PUT"])
def admin_update_institution(institution_id):
    """Admin-only institution update with parameterized SQL."""
    user, err_resp = require_admin_role()
    if err_resp:
        return err_resp

    data = request.get_json() or {}
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM institutions WHERE id = ?", (institution_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": f"Institution ID {institution_id} not found."}), 404

    # Build safe update dictionary
    updates = {}
    for field in ["institution_name", "institution_type", "university_name", "state", "district", "city", "website", "status"]:
        if field in data:
            val = sanitize_formula_injection(str(data[field]))
            updates[field] = val

    if not updates:
        conn.close()
        return jsonify({"success": False, "message": "No valid fields to update."}), 400

    set_clauses = [f"{k} = ?" for k in updates.keys()]
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    if "institution_name" in updates:
        set_clauses.append("name = ?")
        params = list(updates.values()) + [updates["institution_name"], institution_id]
    else:
        params = list(updates.values()) + [institution_id]

    sql = f"UPDATE institutions SET {', '.join(set_clauses)} WHERE id = ?"
    cursor.execute(sql, params)
    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user["id"],
        role=user.get("role", "admin"),
        action="UPDATE_INSTITUTION",
        entity_type="institutions",
        entity_id=institution_id,
        details=f"Admin updated institution ID {institution_id}: {list(updates.keys())}"
    )

    return jsonify({"success": True, "message": "Institution updated successfully."})


@institution_bp.route("/api/admin/institutions/<int:institution_id>", methods=["DELETE"])
def admin_delete_institution(institution_id):
    """Admin-only institution archival/deletion."""
    user, err_resp = require_admin_role()
    if err_resp:
        return err_resp

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, institution_name, aishe_code FROM institutions WHERE id = ?", (institution_id,))
    inst = cursor.fetchone()
    if not inst:
        conn.close()
        return jsonify({"success": False, "message": f"Institution ID {institution_id} not found."}), 404

    # Safe soft-delete / status update
    cursor.execute("UPDATE institutions SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (institution_id,))
    conn.commit()
    conn.close()

    log_audit_event(
        user_id=user["id"],
        role=user.get("role", "admin"),
        action="ARCHIVE_INSTITUTION",
        entity_type="institutions",
        entity_id=institution_id,
        details=f"Admin archived institution {inst['institution_name']} ({inst['aishe_code']})."
    )

    return jsonify({"success": True, "message": f"Institution '{inst['institution_name']}' archived successfully."})
