"""
Preprocessing Pipeline for AP Adaptive Education Platform
Handles feature selection, validation, imputation, scaling, and train-test splitting.
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

# Numerical features used for student risk prediction
FEATURE_COLUMNS = [
    "attendance",
    "mathematics_score",
    "physics_score",
    "programming_score",
    "data_structures_score",
    "database_score",
    "communication_score",
    "assignment_score",
    "quiz_score",
    "exam_score",
    "study_hours",
    "learning_activity",
    "previous_performance",
    "overall_progress"
]

TARGET_COLUMN = "risk_level"
CLASS_NAMES = ["Low Risk", "Medium Risk", "High Risk"]

def create_preprocessing_pipeline():
    """Creates scikit-learn preprocessing pipeline for numeric features."""
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])
    return pipeline

def prepare_data(df, test_size=0.2, random_state=42):
    """
    Validates data, handles missing values, extracts features & target,
    and performs a stratified train/test split.
    """
    # Verify required columns exist
    missing_cols = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in dataset: {missing_cols}")
        
    X = df[FEATURE_COLUMNS].copy()
    y = df[TARGET_COLUMN].copy()
    
    # Stratified split to preserve risk class distribution
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    
    pipeline = create_preprocessing_pipeline()
    X_train_transformed = pipeline.fit_transform(X_train)
    X_test_transformed = pipeline.transform(X_test)
    
    return {
        "X_train": X_train,
        "X_test": X_test,
        "X_train_transformed": X_train_transformed,
        "X_test_transformed": X_test_transformed,
        "y_train": y_train,
        "y_test": y_test,
        "pipeline": pipeline,
        "feature_columns": FEATURE_COLUMNS,
        "classes": CLASS_NAMES
    }

def save_pipeline(pipeline, file_path="models/preprocessing_pipeline.pkl"):
    """Saves fitted preprocessing pipeline to disk."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    joblib.dump(pipeline, file_path)
    print(f"Preprocessing pipeline saved to: {file_path}")

def load_pipeline(file_path="models/preprocessing_pipeline.pkl"):
    """Loads fitted preprocessing pipeline from disk."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Pipeline file not found: {file_path}")
    return joblib.load(file_path)

def extract_features_from_dict(student_dict):
    """
    Extracts ordered feature vector from student dictionary or DB model
    as a pandas DataFrame with proper column headers.
    """
    features = {}
    for col in FEATURE_COLUMNS:
        val = student_dict.get(col, 0)
        try:
            val = float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            val = 0.0
        features[col] = [val]
    return pd.DataFrame(features)
