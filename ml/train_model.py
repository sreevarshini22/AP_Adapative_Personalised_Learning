import os
import sys
import json
import joblib
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

from ml.preprocessing import prepare_data, save_pipeline, FEATURE_COLUMNS, CLASS_NAMES
from ml.evaluation import evaluate_model, print_model_comparison
from data.generate_dataset import generate_student_dataset

def train_and_evaluate_all():
    print("=" * 70)
    print("      AP ADAPTIVE EDUCATION PLATFORM — ML TRAINING PIPELINE")
    print("=" * 70)
    
    data_dir = "data"
    models_dir = "models"
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    
    csv_path = os.path.join(data_dir, "student_learning_dataset.csv")
    if not os.path.exists(csv_path):
        print("Dataset not found. Generating realistic synthetic dataset (5,500 records)...")
        df = generate_student_dataset(n_samples=5500, seed=42)
        df.to_csv(csv_path, index=False)
    else:
        print(f"Loading existing dataset from: {csv_path}")
        df = pd.read_csv(csv_path)
        
    print(f"Total dataset records: {len(df)}")
    
    # Preprocessing and train/test split
    data_bundle = prepare_data(df, test_size=0.2, random_state=42)
    X_train_trans = data_bundle["X_train_transformed"]
    X_test_trans = data_bundle["X_test_transformed"]
    y_train = data_bundle["y_train"]
    y_test = data_bundle["y_test"]
    pipeline = data_bundle["pipeline"]
    
    # Save fitted preprocessing pipeline
    save_pipeline(pipeline, os.path.join(models_dir, "preprocessing_pipeline.pkl"))
    
    # Define candidate models
    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42, C=1.0),
        "Decision Tree": DecisionTreeClassifier(max_depth=8, min_samples_split=10, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=120, max_depth=12, min_samples_split=6, random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=120, learning_rate=0.08, max_depth=4, random_state=42)
    }
    
    benchmark_results = {}
    trained_models = {}
    
    print("\nTraining and evaluating candidate classical ML models...")
    for name, model in models.items():
        print(f" -> Training {name}...")
        model.fit(X_train_trans, y_train)
        metrics = evaluate_model(model, X_test_trans, y_test, class_names=CLASS_NAMES)
        benchmark_results[name] = metrics
        trained_models[name] = model
        print(f"    {name} F1-Weighted: {metrics['f1_weighted']:.4f} | Accuracy: {metrics['accuracy']:.4f}")
        
    # Print comparison table
    print_model_comparison(benchmark_results)
    
    # Select best model based on highest f1_weighted
    best_model_name = max(benchmark_results.keys(), key=lambda k: benchmark_results[k]["f1_weighted"])
    best_model = trained_models[best_model_name]
    best_metrics = benchmark_results[best_model_name]
    
    print(f"[*] BEST PERFORMING MODEL SELECTED: {best_model_name} (F1-Weighted: {best_metrics['f1_weighted']:.4f})")
    
    # Compute global feature importances
    feature_importances = {}
    if hasattr(best_model, "feature_importances_"):
        raw_imp = best_model.feature_importances_
        for col, imp in zip(FEATURE_COLUMNS, raw_imp):
            feature_importances[col] = round(float(imp), 4)
    elif hasattr(best_model, "coef_"):
        # For Logistic Regression, average absolute coefficient across classes
        coef_mean = np.mean(np.abs(best_model.coef_), axis=0)
        norm_coef = coef_mean / np.sum(coef_mean)
        for col, imp in zip(FEATURE_COLUMNS, norm_coef):
            feature_importances[col] = round(float(imp), 4)
            
    # Sort feature importances descending
    sorted_features = dict(sorted(feature_importances.items(), key=lambda item: item[1], reverse=True))
    
    # Package final model artifact
    model_artifact = {
        "model_name": best_model_name,
        "model": best_model,
        "classes": CLASS_NAMES,
        "feature_columns": FEATURE_COLUMNS,
        "feature_importances": sorted_features
    }
    
    model_save_path = os.path.join(models_dir, "learning_risk_model.pkl")
    joblib.dump(model_artifact, model_save_path)
    print(f"Best model artifact saved to: {model_save_path}")
    
    # Save full metrics summary JSON
    metrics_summary = {
        "best_model_name": best_model_name,
        "best_model_metrics": best_metrics,
        "benchmark_comparison": benchmark_results,
        "feature_importances": sorted_features,
        "dataset_summary": {
            "total_samples": len(df),
            "train_samples": len(y_train),
            "test_samples": len(y_test),
            "risk_distribution": df["risk_level"].value_counts().to_dict(),
            "branches": df["branch"].unique().tolist()
        }
    }
    
    metrics_json_path = os.path.join(models_dir, "model_metrics.json")
    with open(metrics_json_path, "w") as f:
        json.dump(metrics_summary, f, indent=2)
    print(f"Model metrics JSON saved to: {metrics_json_path}")
    print("=" * 70 + "\n")
    
    return metrics_summary

if __name__ == "__main__":
    train_and_evaluate_all()
