"""
Comprehensive End-to-End Verification Test for PennyLane Quantum ML Integration
Verifies the complete pipeline from student login, database data retrieval,
quantum circuit execution, to personalized learning pathway generation.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import init_db, seed_demo_data
from ml.quantum_model import get_qml_status


class TestEndToEndQuantumMLVerification(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_demo_data()

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_01_backend_startup_quantum_status(self):
        """Step 1: Check Quantum Model Status on backend startup."""
        status = get_qml_status()
        self.assertEqual(status["quantum_ml_available"], "YES")
        self.assertEqual(status["pennylane"], "installed")
        self.assertEqual(status["device"], "default.qubit")
        self.assertEqual(status["qubits"], 5)
        self.assertEqual(status["layers"], 2)
        self.assertEqual(status["weights_loaded"], "YES")
        self.assertEqual(status["training_completed"], "YES")

    def test_02_student_login_to_quantum_prediction_flow(self):
        """Step 2: Authenticate student, fetch profile, progress, subjects, and QML prediction."""
        # 1. Login
        login_res = self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertTrue(login_data["success"])
        student = login_data["student"]
        
        # Verify real database features exist
        self.assertIn("attendance", student)
        self.assertIn("mathematics_score", student)
        self.assertIn("physics_score", student)
        self.assertIn("programming_score", student)
        self.assertIn("assignment_score", student)

        # 2. Student Dashboard
        dash_res = self.client.get("/student-dashboard")
        self.assertEqual(dash_res.status_code, 200)

        # 3. Load Profile & Subjects
        me_res = self.client.get("/api/student/me")
        self.assertEqual(me_res.status_code, 200)
        
        sub_res = self.client.get("/api/student/subjects")
        self.assertEqual(sub_res.status_code, 200)
        sub_data = sub_res.get_json()
        self.assertTrue(sub_data["success"])
        self.assertGreater(len(sub_data["subjects"]), 0)

        # 4. Request Quantum ML Prediction
        pred_res = self.client.get("/api/student/prediction")
        self.assertEqual(pred_res.status_code, 200)
        pred_data = pred_res.get_json()
        self.assertTrue(pred_data["success"])
        
        # Verify top-level QML keys
        self.assertEqual(pred_data["model"], "Quantum ML")
        self.assertIn(pred_data["risk_level"], ["Low Risk", "Medium Risk", "High Risk"])
        self.assertIsInstance(pred_data["risk_score"], (int, float))

        # Verify prediction inner object
        pred = pred_data["prediction"]
        self.assertEqual(pred["model"], "Quantum ML")
        self.assertEqual(pred["device"], "default.qubit")
        self.assertEqual(pred["qubits"], 5)
        self.assertEqual(pred["layers"], 2)
        self.assertIn("probabilities", pred)
        self.assertIn("Low Risk", pred["probabilities"])
        self.assertIn("Medium Risk", pred["probabilities"])
        self.assertIn("High Risk", pred["probabilities"])
        self.assertGreater(len(pred["top_risk_drivers"]), 0)

        # 5. Request Personalized Learning Pathway
        path_res = self.client.get("/api/student/learning-path")
        self.assertEqual(path_res.status_code, 200)
        path_data = path_res.get_json()
        self.assertTrue(path_data["success"])
        self.assertIsInstance(path_data["learning_path"], list)
        self.assertGreater(len(path_data["learning_path"]), 0)

    def test_03_teacher_dashboard_cleanliness(self):
        """Step 3: Verify Teacher Dashboard has no ML/Quantum Insights."""
        login_res = self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        self.assertEqual(login_res.status_code, 200)

        dash_res = self.client.get("/teacher-dashboard")
        self.assertEqual(dash_res.status_code, 200)
        html = dash_res.get_data(as_text=True)
        self.assertNotIn("Quantum ML Insights", html)
        self.assertNotIn("Model Risk Probability Distribution", html)
        self.assertNotIn("quantum_model", html)

        students_res = self.client.get("/api/teacher/students")
        self.assertEqual(students_res.status_code, 200)
        students_data = students_res.get_json()
        self.assertTrue(students_data["success"])
        for s in students_data["students"]:
            self.assertNotIn("password", s)
            self.assertNotIn("password_hash", s)


if __name__ == "__main__":
    unittest.main()
