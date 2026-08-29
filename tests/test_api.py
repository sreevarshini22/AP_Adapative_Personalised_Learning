"""
REST API and End-to-End Endpoint Test Suite
"""

import os
import sys
import unittest
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import init_db, seed_demo_data

class TestAPAdaptiveAPI(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_01_student_login_and_endpoints(self):
        # 1. Student Login
        res = self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "student")

        # 2. Get Student Profile
        res_me = self.client.get("/api/student/me")
        self.assertEqual(res_me.status_code, 200)
        st_data = res_me.get_json()
        self.assertTrue(st_data["success"])
        self.assertEqual(st_data["student"]["email"], "student@example.com")

        # 3. Get Student Prediction
        res_pred = self.client.get("/api/student/prediction")
        self.assertEqual(res_pred.status_code, 200)
        pred_data = res_pred.get_json()
        self.assertTrue(pred_data["success"])
        self.assertIn("risk_level", pred_data["prediction"])

        # 4. Get Student Learning Path
        res_path = self.client.get("/api/student/learning-path")
        self.assertEqual(res_path.status_code, 200)
        path_data = res_path.get_json()
        self.assertTrue(path_data["success"])
        self.assertGreater(len(path_data["path_data"]["learning_path"]), 0)

        # 5. Update Student Progress
        res_update = self.client.post("/api/student/progress/update", json={
            "module_id": "PROG-101",
            "action": "complete_step"
        })
        self.assertEqual(res_update.status_code, 200)
        self.assertTrue(res_update.get_json()["success"])

        # 6. Logout
        self.client.post("/api/logout")

    def test_02_teacher_login_and_analytics(self):
        # 1. Teacher Login
        res = self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "teacher")

        # 2. Class Analytics
        res_an = self.client.get("/api/teacher/analytics")
        self.assertEqual(res_an.status_code, 200)
        an_data = res_an.get_json()
        self.assertTrue(an_data["success"])
        self.assertGreater(an_data["total_students"], 0)
        self.assertIn("High Risk", an_data["risk_distribution_counts"])

        # 3. Get Filtered Student List
        res_stu = self.client.get("/api/teacher/students?branch=CSE")
        self.assertEqual(res_stu.status_code, 200)
        stu_data = res_stu.get_json()
        self.assertTrue(stu_data["success"])
        self.assertGreater(stu_data["total"], 0)

        # 4. Get Student Detail
        student_id = stu_data["students"][0]["id"]
        res_det = self.client.get(f"/api/teacher/student/{student_id}")
        self.assertEqual(res_det.status_code, 200)
        det_data = res_det.get_json()
        self.assertTrue(det_data["success"])

        # 5. Log Intervention
        res_intv = self.client.post(f"/api/teacher/student/{student_id}/intervention", json={
            "title": "Remedial Coding Clinic",
            "category": "Remedial Lab Coaching",
            "priority": "High",
            "description": "Assigned to Tuesday coding lab for pointer and memory debugging."
        })
        self.assertEqual(res_intv.status_code, 201)
        self.assertTrue(res_intv.get_json()["success"])

        # 6. Logout
        self.client.post("/api/logout")

    def test_03_role_access_control(self):
        # Unauthenticated access to teacher analytics should be 401
        res = self.client.get("/api/teacher/analytics")
        self.assertEqual(res.status_code, 401)

        # Student trying to access teacher endpoint should be 403
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        res_forbidden = self.client.get("/api/teacher/analytics")
        self.assertEqual(res_forbidden.status_code, 403)
        self.client.post("/api/logout")

    def test_04_ml_metrics_api(self):
        res = self.client.get("/api/ml/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("best_model_name", data["metrics"])
        self.assertIn("benchmark_comparison", data["metrics"])

if __name__ == "__main__":
    unittest.main()
