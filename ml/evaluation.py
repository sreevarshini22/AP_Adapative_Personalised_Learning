"""
Model Evaluation and Metrics Utilities for AP Adaptive Education Platform
Calculates multi-class classification metrics: Accuracy, Precision, Recall, F1, Confusion Matrix, and ROC-AUC.
"""

import json
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

def evaluate_model(model, X_test, y_test, class_names=None):
    """
    Computes comprehensive evaluation metrics for a trained classifier.
    """
    if class_names is None:
        class_names = ["Low Risk", "Medium Risk", "High Risk"]
        
    y_pred = model.predict(X_test)
    
    # Calculate probabilities if available
    try:
        y_prob = model.predict_proba(X_test)
    except (AttributeError, NotImplementedError):
        y_prob = None
        
    acc = accuracy_score(y_test, y_pred)
    prec_macro = precision_score(y_test, y_pred, average="macro", zero_division=0)
    prec_weighted = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    rec_macro = recall_score(y_test, y_pred, average="macro", zero_division=0)
    rec_weighted = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1_mac = f1_score(y_test, y_pred, average="macro", zero_division=0)
    f1_wt = f1_score(y_test, y_pred, average="weighted", zero_division=0)
    
    cm = confusion_matrix(y_test, y_pred, labels=class_names).tolist()
    clf_report = classification_report(y_test, y_pred, target_names=class_names, output_dict=True, zero_division=0)
    
    return {
        "accuracy": round(float(acc), 4),
        "precision_macro": round(float(prec_macro), 4),
        "precision_weighted": round(float(prec_weighted), 4),
        "recall_macro": round(float(rec_macro), 4),
        "recall_weighted": round(float(rec_weighted), 4),
        "f1_macro": round(float(f1_mac), 4),
        "f1_weighted": round(float(f1_wt), 4),
        "confusion_matrix": cm,
        "classes": class_names,
        "classification_report": clf_report
    }

def print_model_comparison(results_dict):
    """
    Prints a formatted comparison table of all evaluated models.
    """
    header = f"{'Model Name':<28} | {'Accuracy':<10} | {'Precision (W)':<14} | {'Recall (W)':<12} | {'F1-Score (W)':<12}"
    divider = "-" * len(header)
    print("\n" + divider)
    print("           CLASSICAL ML MODEL BENCHMARK COMPARISON TABLE")
    print(divider)
    print(header)
    print(divider)
    for model_name, metrics in results_dict.items():
        print(f"{model_name:<28} | {metrics['accuracy']:<10.4f} | {metrics['precision_weighted']:<14.4f} | {metrics['recall_weighted']:<12.4f} | {metrics['f1_weighted']:<12.4f}")
    print(divider + "\n")
