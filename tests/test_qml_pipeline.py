"""
Unit and Integration Test Suite for PennyLane Quantum Machine Learning (QML) Engine
Validates circuit loading, quantum inference, student DB integration, and fallback safety.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import get_db_connection, init_db
from ml.quantum_model import (
    QuantumRiskClassifier,
    load_quantum_model,
    predict_learning_risk,
    get_qml_status,
    NUM_QUBITS,
    NUM_LAYERS,
    DEVICE_NAME
)
from ml.predict import predict_student_risk


class TestQuantumMachineLearningPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_01_qml_system_status(self):
        """Verifies QML status check parameters."""
        status = get_qml_status()
        self.assertEqual(status["quantum_ml_available"], "YES")
        self.assertEqual(status["pennylane"], "installed")
        self.assertEqual(status["device"], DEVICE_NAME)
        self.assertEqual(status["qubits"], NUM_QUBITS)
        self.assertEqual(status["layers"], NUM_LAYERS)
        self.assertEqual(status["weights_loaded"], "YES")
        self.assertEqual(status["training_completed"], "YES")

    def test_02_load_quantum_model_and_weights(self):
        """Verifies that trained quantum weights and scalers load without retraining."""
        model = load_quantum_model()
        self.assertIsNotNone(model.circuit_weights)
        self.assertIsNotNone(model.head_weights)
        self.assertIsNotNone(model.head_bias)
        self.assertEqual(model.circuit_weights.shape, (NUM_LAYERS, NUM_QUBITS, 3))
        self.assertEqual(model.head_weights.shape, (3, NUM_QUBITS))
        self.assertTrue(model.is_trained)

    def test_03_quantum_inference_on_sample_student(self):
        """Verifies real quantum circuit execution on sample student feature vector."""
        sample_student = {
            "attendance": 80.0,
            "mathematics_score": 75.0,
            "physics_score": 70.0,
            "programming_score": 65.0,
            "assignment_score": 85.0
        }
        res = predict_learning_risk(sample_student)
        self.assertIn(res["risk_level"], ["Low Risk", "Medium Risk", "High Risk"])
        self.assertIsInstance(res["risk_score"], (int, float))
        self.assertGreaterEqual(res["risk_score"], 0.0)
        self.assertLessEqual(res["risk_score"], 100.0)
        self.assertEqual(res["model"], "Quantum ML")
        self.assertEqual(res["qubits"], 5)
        self.assertEqual(res["device"], "default.qubit")
        self.assertIn("Low Risk", res["probabilities"])
        self.assertIn("Medium Risk", res["probabilities"])
        self.assertIn("High Risk", res["probabilities"])

    def test_04_active_prediction_gateway_routes_to_qml(self):
        """Verifies that predict_student_risk in predict.py routes directly to QML."""
        sample_student = {
            "attendance": 50.0,
            "mathematics_score": 40.0,
            "physics_score": 45.0,
            "programming_score": 35.0,
            "assignment_score": 50.0
        }
        res = predict_student_risk(sample_student)
        self.assertIn("Quantum", res["model_name"])
        self.assertEqual(res["model"], "Quantum ML")
        self.assertIn("probabilities", res)

    def test_05_authenticated_student_receives_qml_prediction(self):
        """Verifies that logged-in student gets real QML prediction from their database data."""
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        res = self.client.get("/api/student/prediction")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        pred = data["prediction"]
        self.assertEqual(pred["model"], "Quantum ML")
        self.assertEqual(pred["qubits"], 5)
        self.assertEqual(pred["device"], "default.qubit")
        self.assertGreater(len(pred["top_risk_drivers"]), 0)

    def test_06_teacher_dashboard_has_no_ml_insights(self):
        """Verifies that Teacher Dashboard is clean and has no ML/Quantum Insights."""
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        res = self.client.get("/teacher-dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertNotIn("Quantum ML Insights", html)
        self.assertNotIn("Model Risk Probability Distribution", html)


if __name__ == "__main__":
    unittest.main()
