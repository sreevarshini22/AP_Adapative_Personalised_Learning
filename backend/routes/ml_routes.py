"""
Machine Learning Explainability and Metrics REST API Routes
"""

import os
import json
from flask import Blueprint, request, jsonify
from backend.database import get_db_connection
from backend.models import serialize_student
from ml.predict import predict_student_risk
from ml.train_model import train_and_evaluate_all

ml_bp = Blueprint("ml", __name__)

METRICS_JSON_PATH = os.path.join("models", "model_metrics.json")

@ml_bp.route("/api/ml/metrics", methods=["GET"])
def get_ml_metrics():
    """
    Returns benchmark comparison metrics across Logistic Regression,
    Decision Tree, Random Forest, and Gradient Boosting models,
    including confusion matrices and global feature importances.
    """
    if not os.path.exists(METRICS_JSON_PATH):
        metrics_summary = train_and_evaluate_all()
    else:
        with open(METRICS_JSON_PATH, "r") as f:
            metrics_summary = json.load(f)
            
    return jsonify({
        "success": True,
        "metrics": metrics_summary
    })

@ml_bp.route("/api/student/<int:student_id>/risk-explanation", methods=["GET"])
def get_student_risk_explanation(student_id):
    """
    Returns explainable AI diagnosis detailing the factors driving a student's risk category.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"success": False, "error": f"Student with ID {student_id} not found."}), 404
        
    st = serialize_student(row)
    prediction = predict_student_risk(st)
    
    return jsonify({
        "success": True,
        "student_id": student_id,
        "full_name": st["full_name"],
        "roll_no": st["roll_no"],
        "risk_level": prediction["risk_level"],
        "risk_score": prediction["risk_score"],
        "confidence": prediction["confidence"],
        "probabilities": prediction["probabilities"],
        "important_features": prediction["important_features"],
        "top_risk_factors": prediction["top_risk_factors"],
        "top_strengths": prediction["top_strengths"],
        "explanations": prediction["explanations"],
        "model_name": prediction["model_name"]
    })

@ml_bp.route("/api/ml/predict-custom", methods=["POST"])
def predict_custom_features():
    """
    Interactive API for developers/judges to test ML prediction with custom input features.
    """
    data = request.get_json() or {}
    prediction = predict_student_risk(data)
    return jsonify({
        "success": True,
        "input_features": data,
        "prediction": prediction
    })
