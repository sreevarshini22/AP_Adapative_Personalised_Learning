"""
Classical ML Model Architecture for AP Adaptive Education Platform
Contains modular model training, prediction, evaluation, and serialization classes.
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List

# Ensure project root is accessible
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from ml.preprocessing import prepare_data, save_pipeline, load_pipeline, FEATURE_COLUMNS, CLASS_NAMES
from ml.evaluation import evaluate_model, print_model_comparison


class ClassicalRiskClassifier:
    """
    Modular Classical Machine Learning model for predicting student academic risk.
    Supports Random Forest, Gradient Boosting, Decision Tree, and Logistic Regression.
    """

    def __init__(self, model_type: str = "Random Forest", random_state: int = 42):
        self.model_type = model_type
        self.random_state = random_state
        self.model = None
        self.pipeline = None
        self.classes = CLASS_NAMES
        self.feature_columns = FEATURE_COLUMNS
        self.feature_importances: Dict[str, float] = {}
        self.evaluation_metrics: Dict[str, Any] = {}
        self._init_model()

    def _init_model(self):
        """Instantiates the underlying scikit-learn estimator."""
        if self.model_type == "Random Forest":
            self.model = RandomForestClassifier(
                n_estimators=120,
                max_depth=12,
                min_samples_split=6,
                random_state=self.random_state,
                n_jobs=-1
            )
        elif self.model_type == "Gradient Boosting":
            self.model = GradientBoostingClassifier(
                n_estimators=120,
                learning_rate=0.08,
                max_depth=4,
                random_state=self.random_state
            )
        elif self.model_type == "Decision Tree":
            self.model = DecisionTreeClassifier(
                max_depth=8,
                min_samples_split=10,
                random_state=self.random_state
            )
        elif self.model_type == "Logistic Regression":
            self.model = LogisticRegression(
                max_iter=1000,
                C=1.0,
                random_state=self.random_state
            )
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def train_on_dataframe(self, df: pd.DataFrame, test_size: float = 0.2) -> Dict[str, Any]:
        """
        Prepares dataset, fits preprocessing pipeline, trains classifier,
        and computes evaluation metrics on held-out test split.
        """
        data_bundle = prepare_data(df, test_size=test_size, random_state=self.random_state)
        X_train_trans = data_bundle["X_train_transformed"]
        X_test_trans = data_bundle["X_test_transformed"]
        y_train = data_bundle["y_train"]
        y_test = data_bundle["y_test"]
        self.pipeline = data_bundle["pipeline"]

        # Train model
        self.model.fit(X_train_trans, y_train)

        # Evaluate on test set
        self.evaluation_metrics = evaluate_model(self.model, X_test_trans, y_test, class_names=self.classes)

        # Compute feature importances
        self._compute_feature_importances()

        return self.evaluation_metrics

    def _compute_feature_importances(self):
        """Calculates global feature importances for explainability."""
        self.feature_importances = {}
        if hasattr(self.model, "feature_importances_"):
            raw_imp = self.model.feature_importances_
            for col, imp in zip(self.feature_columns, raw_imp):
                self.feature_importances[col] = round(float(imp), 4)
        elif hasattr(self.model, "coef_"):
            coef_mean = np.mean(np.abs(self.model.coef_), axis=0)
            norm_coef = coef_mean / np.sum(coef_mean) if np.sum(coef_mean) > 0 else coef_mean
            for col, imp in zip(self.feature_columns, norm_coef):
                self.feature_importances[col] = round(float(imp), 4)
        
        # Sort descending
        self.feature_importances = dict(
            sorted(self.feature_importances.items(), key=lambda item: item[1], reverse=True)
        )

    def predict_single(self, student_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs real-time prediction on a single student dictionary.
        Returns predicted risk level, probability distribution, risk score, and top drivers.
        """
        from ml.preprocessing import extract_features_from_dict
        if self.model is None or self.pipeline is None:
            raise RuntimeError("Model and pipeline must be trained or loaded before prediction.")

        raw_df = extract_features_from_dict(student_dict)
        X_trans = self.pipeline.transform(raw_df)

        pred_class = self.model.predict(X_trans)[0]

        probabilities = {}
        if hasattr(self.model, "predict_proba"):
            probs_arr = self.model.predict_proba(X_trans)[0]
            model_classes = list(self.model.classes_)
            for c in self.classes:
                if c in model_classes:
                    idx = model_classes.index(c)
                    probabilities[c] = round(float(probs_arr[idx]), 3)
                else:
                    probabilities[c] = 0.0
        else:
            probabilities = {c: 1.0 if c == pred_class else 0.0 for c in self.classes}

        # Composite risk score (0 to 100)
        p_high = probabilities.get("High Risk", 0.0)
        p_med = probabilities.get("Medium Risk", 0.0)
        p_low = probabilities.get("Low Risk", 0.0)
        risk_score = round(float((p_high * 100.0) + (p_med * 45.0) + (p_low * 10.0)), 1)
        risk_score = max(0.0, min(100.0, risk_score))

        return {
            "risk_level": pred_class,
            "probabilities": probabilities,
            "risk_score": risk_score,
            "confidence": max(probabilities.values()),
            "feature_importances": self.feature_importances
        }

    def save(self, model_path: str, pipeline_path: str):
        """Serializes model artifact and fitted preprocessing pipeline."""
        os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(pipeline_path)), exist_ok=True)

        artifact = {
            "model_name": self.model_type,
            "model": self.model,
            "classes": self.classes,
            "feature_columns": self.feature_columns,
            "feature_importances": self.feature_importances,
            "evaluation_metrics": self.evaluation_metrics
        }
        joblib.dump(artifact, model_path)
        save_pipeline(self.pipeline, pipeline_path)

    @classmethod
    def load(cls, model_path: str, pipeline_path: str) -> "ClassicalRiskClassifier":
        """Deserializes a saved model artifact and preprocessing pipeline."""
        if not os.path.exists(model_path) or not os.path.exists(pipeline_path):
            raise FileNotFoundError(f"Model or pipeline artifact missing at {model_path}, {pipeline_path}")

        artifact = joblib.load(model_path)
        pipeline = load_pipeline(pipeline_path)

        instance = cls(model_type=artifact.get("model_name", "Random Forest"))
        instance.model = artifact["model"]
        instance.classes = artifact.get("classes", CLASS_NAMES)
        instance.feature_columns = artifact.get("feature_columns", FEATURE_COLUMNS)
        instance.feature_importances = artifact.get("feature_importances", {})
        instance.evaluation_metrics = artifact.get("evaluation_metrics", {})
        instance.pipeline = pipeline

        return instance
