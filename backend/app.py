"""
Flask Application Entry Point for AP Adaptive Education Platform
Configured for production WSGI servers (Gunicorn) and local development.
"""

import os
from flask import Flask, send_from_directory, redirect, url_for, session, jsonify
from flask_cors import CORS

from backend.database import init_db, seed_demo_data, get_db_connection
from backend.routes.auth_routes import auth_bp
from backend.routes.student_routes import student_bp
from backend.routes.teacher_routes import teacher_bp
from backend.routes.ml_routes import ml_bp


def create_app():
    # Frontend directory path
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    
    app = Flask(__name__, static_folder=frontend_dir, static_url_path="")
    
    # Production security configuration from environment
    secret_key = os.environ.get("SECRET_KEY", "ap_adaptive_edu_secret_key_2024_quantum_ml_production_secure")
    app.config["SECRET_KEY"] = secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    
    # Enable HTTPS-only cookies in production environment
    is_prod = os.environ.get("FLASK_ENV") == "production" or os.environ.get("ENVIRONMENT") == "production"
    app.config["SESSION_COOKIE_SECURE"] = is_prod
    
    # Maximum upload size for student CSV imports (16MB)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    
    # Enable CORS for safe API requests
    CORS(app, supports_credentials=True)
    
    # Safe database initialization (preserves existing data)
    init_db()
    seed_demo_data()
    
    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(ml_bp)
    
    # Health Check API
    @app.route("/api/health", methods=["GET"])
    def health_check():
        db_status = "disconnected"
        try:
            conn = get_db_connection()
            conn.execute("SELECT 1").fetchone()
            conn.close()
            db_status = "connected"
        except Exception:
            db_status = "error"
            
        try:
            from ml.quantum_model import get_qml_status
            qml_status = get_qml_status()
            qml_avail = "available" if qml_status.get("quantum_ml_available") == "YES" else "unavailable"
            qml_dev = qml_status.get("device", "default.qubit")
            qml_qubits = qml_status.get("qubits", 5)
            qml_weights = qml_status.get("weights_loaded", "NO")
        except Exception:
            qml_avail = "unavailable"
            qml_dev = "default.qubit"
            qml_qubits = 5
            qml_weights = "NO"
            
        return jsonify({
            "status": "ok" if db_status == "connected" else "degraded",
            "database": db_status,
            "quantum_ml": qml_avail,
            "qml_device": qml_dev,
            "qml_qubits": qml_qubits,
            "weights_loaded": qml_weights
        }), 200
    
    # Frontend HTML Page Routes
    @app.route("/")
    @app.route("/login")
    @app.route("/student-login")
    @app.route("/teacher-login")
    def login_page():
        return send_from_directory(frontend_dir, "login.html")
        
    @app.route("/student-dashboard")
    def student_dashboard_page():
        return send_from_directory(frontend_dir, "student-dashboard.html")
        
    @app.route("/teacher-dashboard")
    def teacher_dashboard_page():
        return send_from_directory(frontend_dir, "teacher-dashboard.html")
        
    @app.route("/student-details")
    def student_details_page():
        if session.get("role") != "teacher" or not session.get("user_id"):
            return redirect(url_for("login_page"))
        return send_from_directory(frontend_dir, "student-details.html")
        
    @app.route("/ml-performance")
    def ml_performance_page():
        return send_from_directory(frontend_dir, "ml-performance.html")
        
    @app.route("/<path:path>")
    def serve_static(path):
        if os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "login.html")
        
    # Production Error Handlers
    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"success": False, "error": "Endpoint or resource not found"}), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        return jsonify({"success": False, "error": "Internal server error occurred"}), 500
        
    return app


# Production WSGI application instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
