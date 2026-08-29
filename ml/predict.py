"""
Predictive Assessment Gateway for AP Adaptive Education Platform
Directs live student risk evaluation to the PennyLane Quantum Machine Learning (QML) engine.
Maintains classical ML fallback with explicit model provenance tagging.
"""

import os
import sys
import joblib
import numpy as np

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.preprocessing import extract_features_from_dict, FEATURE_COLUMNS, CLASS_NAMES

_CLASSICAL_MODEL_CACHE = None
_CLASSICAL_PIPELINE_CACHE = None

FEATURE_DISPLAY_NAMES = {
    "attendance": "Class Attendance (%)",
    "mathematics_score": "Mathematics Score",
    "physics_score": "Physics Score",
    "programming_score": "Programming Score",
    "data_structures_score": "Data Structures Score",
    "database_score": "DBMS Score",
    "communication_score": "Communication Skills",
    "assignment_score": "Assignment Performance",
    "quiz_score": "Quiz Performance",
    "exam_score": "Semester Exam Score",
    "study_hours": "Weekly Study Hours",
    "learning_activity": "LMS Learning Activity",
    "previous_performance": "Historical Performance (GPA)",
    "overall_progress": "Curriculum Completion Progress"
}

FEATURE_BENCHMARKS = {
    "attendance": 75.0,
    "mathematics_score": 60.0,
    "physics_score": 60.0,
    "programming_score": 60.0,
    "data_structures_score": 60.0,
    "database_score": 60.0,
    "communication_score": 60.0,
    "assignment_score": 65.0,
    "quiz_score": 60.0,
    "exam_score": 60.0,
    "study_hours": 8.0,
    "learning_activity": 60.0,
    "previous_performance": 65.0,
    "overall_progress": 60.0
}


def get_classical_model_and_pipeline(models_dir="models"):
    """Loads and caches classical fallback model and preprocessing pipeline."""
    global _CLASSICAL_MODEL_CACHE, _CLASSICAL_PIPELINE_CACHE
    if _CLASSICAL_MODEL_CACHE is None or _CLASSICAL_PIPELINE_CACHE is None:
        model_path = os.path.join(models_dir, "learning_risk_model.pkl")
        pipeline_path = os.path.join(models_dir, "preprocessing_pipeline.pkl")
        
        if not os.path.exists(model_path) or not os.path.exists(pipeline_path):
            from ml.train_model import train_and_evaluate_all
            train_and_evaluate_all()
            
        _CLASSICAL_MODEL_CACHE = joblib.load(model_path)
        _CLASSICAL_PIPELINE_CACHE = joblib.load(pipeline_path)
        
    return _CLASSICAL_MODEL_CACHE, _CLASSICAL_PIPELINE_CACHE


def _predict_classical_fallback(student_data):
    """Fallback predictive evaluation using Classical ML."""
    model_artifact, pipeline = get_classical_model_and_pipeline()
    model = model_artifact["model"]
    classes = model_artifact.get("classes", CLASS_NAMES)
    global_importances = model_artifact.get("feature_importances", {})
    
    raw_df = extract_features_from_dict(student_data)
    transformed_features = pipeline.transform(raw_df)
    
    pred_class = model.predict(transformed_features)[0]
    
    if hasattr(model, "predict_proba"):
        probs_array = model.predict_proba(transformed_features)[0]
        model_classes = list(model.classes_)
        probabilities = {}
        for c in classes:
            if c in model_classes:
                idx = model_classes.index(c)
                probabilities[c] = round(float(probs_array[idx]), 3)
            else:
                probabilities[c] = 0.0
    else:
        probabilities = {c: 1.0 if c == pred_class else 0.0 for c in classes}
        
    p_high = probabilities.get("High Risk", 0.0)
    p_med = probabilities.get("Medium Risk", 0.0)
    p_low = probabilities.get("Low Risk", 0.0)
    risk_score = round(float((p_high * 100.0) + (p_med * 45.0) + (p_low * 10.0)), 1)
    risk_score = max(0.0, min(100.0, risk_score))
    
    important_features = []
    explanations = []
    
    for col in FEATURE_COLUMNS:
        val = float(raw_df[col].iloc[0])
        benchmark = FEATURE_BENCHMARKS.get(col, 60.0)
        display_name = FEATURE_DISPLAY_NAMES.get(col, col.replace("_", " ").title())
        importance_weight = global_importances.get(col, 0.05)
        diff = val - benchmark
        
        if diff < 0:
            impact_type = "Risk Factor"
            severity = abs(diff) * importance_weight
            detail = f"{display_name} ({val:g}) is below benchmark ({benchmark:g})"
        else:
            impact_type = "Strength Buffer"
            severity = abs(diff) * importance_weight * 0.5
            detail = f"{display_name} ({val:g}) meets/exceeds standard ({benchmark:g})"
            
        important_features.append({
            "feature_key": col,
            "feature_name": display_name,
            "value": val,
            "benchmark": benchmark,
            "difference": round(diff, 1),
            "global_importance": importance_weight,
            "impact_type": impact_type,
            "severity_score": round(float(severity), 4),
            "detail": detail
        })
        
    risk_factors = [f for f in important_features if f["impact_type"] == "Risk Factor"]
    risk_factors.sort(key=lambda x: (x["global_importance"] * abs(x["difference"])), reverse=True)
    
    confidence = round(float(max(probabilities.values()) * 100), 1)
    risk_drivers = [rf["detail"] for rf in risk_factors[:4]]
    
    return {
        "risk_level": pred_class,
        "risk_score": risk_score,
        "probabilities": probabilities,
        "confidence": confidence,
        "confidence_percentage": confidence,
        "important_features": important_features,
        "top_risk_factors": risk_factors[:4],
        "top_strengths": [],
        "risk_drivers": risk_drivers,
        "top_risk_drivers": risk_drivers,
        "explanations": explanations,
        "model": "Classical ML fallback",
        "model_name": "Classical ML fallback (Random Forest / Logistic Regression)"
    }


def predict_student_risk(student_data):
    """
    Primary Prediction Entrypoint:
    Executes PennyLane Quantum Machine Learning (QML) as the champion active production engine.
    Falls back gracefully to Classical ML if QML dependencies/weights are unavailable.
    """
    try:
        from ml.quantum_model import predict_learning_risk
        return predict_learning_risk(student_data)
    except Exception as e:
        print(f"[!] QML Prediction failed or unavailable ({e}). Invoking Classical ML fallback.")
        return _predict_classical_fallback(student_data)
