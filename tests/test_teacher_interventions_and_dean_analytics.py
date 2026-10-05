"""
Verification Test Suite for 1-Click Teacher Remedial Interventions & Institutional Dean Analytics.
"""

import os
import sys
import unittest
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app
from backend.database import get_db_connection


class TestTeacherInterventionsAndDeanAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def login_teacher(self):
        res = self.client.post(
            "/api/login",
            data=json.dumps({"email": "prof.murthy@au.edu.in", "password": "teacher123"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)

    def login_admin(self):
        res = self.client.post(
            "/api/login",
            data=json.dumps({"email": "admin@au.edu.in", "password": "admin123"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)

    def logout(self):
        self.client.post("/api/logout")

    def test_01_recommended_interventions(self):
        """Teacher can fetch ML-generated 1-click remedial action templates for an assigned student."""
        self.login_teacher()
        
        # Get assigned students
        st_res = self.client.get("/api/teacher/students")
        self.assertEqual(st_res.status_code, 200)
        st_data = st_res.get_json()
        self.assertTrue(st_data["success"])
        self.assertGreater(len(st_data["students"]), 0)

        student_id = st_data["students"][0]["id"]

        # Fetch recommended templates
        res = self.client.get(f"/api/teacher/students/{student_id}/recommended-interventions")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("recommended_templates", data)
        self.assertGreaterEqual(len(data["recommended_templates"]), 2)
        
        tpl = data["recommended_templates"][0]
        self.assertIn("action_type", tpl)
        self.assertIn("title", tpl)
        self.assertIn("priority", tpl)
        self.logout()

    def test_02_dispatch_single_intervention(self):
        """Teacher can dispatch a 1-click intervention and track it in interventions table."""
        self.login_teacher()

        st_res = self.client.get("/api/teacher/students")
        st_data = st_res.get_json()
        student_id = st_data["students"][0]["id"]

        payload = {
            "action_type": "Remedial Quiz",
            "title": "Automated Unit Test Remedial Drill",
            "description": "Please complete the 5-question diagnostic drill on Decision Trees.",
            "priority": "High",
            "notes": "Follow up after mid-term."
        }

        res = self.client.post(
            f"/api/teacher/students/{student_id}/intervene",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("intervention_id", data)

        interv_id = data["intervention_id"]

        # Verify listed in interventions
        list_res = self.client.get("/api/teacher/interventions")
        self.assertEqual(list_res.status_code, 200)
        list_data = list_res.get_json()
        self.assertTrue(list_data["success"])
        self.assertGreater(list_data["summary"]["total"], 0)

        # Update status to Completed
        status_res = self.client.post(
            f"/api/teacher/interventions/{interv_id}/status",
            data=json.dumps({"status": "Completed", "notes": "Drill completed successfully."}),
            content_type="application/json"
        )
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(status_res.get_json()["success"])
        self.logout()

    def test_03_bulk_interventions(self):
        """Teacher can dispatch 1-click bulk interventions to all high-risk students in assigned section."""
        self.login_teacher()

        payload = {
            "risk_filter": "high",
            "action_type": "Remedial Quiz",
            "title": "Cohort-wide High Risk Diagnostic Review",
            "description": "All students with attendance below 70% must review Module 2 notes.",
            "priority": "Urgent"
        }

        res = self.client.post(
            "/api/teacher/students/bulk-intervene",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("intervened_count", data)
        self.logout()

    def test_04_dean_institutional_analytics(self):
        """Institution Admin / Dean can fetch cross-department pass-rate heatmaps and attrition metrics."""
        self.login_admin()

        res = self.client.get("/api/institution-admin/dean-analytics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("kpis", data)
        self.assertIn("institutional_health_score", data["kpis"])
        self.assertIn("department_heatmaps", data)
        self.assertIn("year_level_attrition", data)
        self.assertIn("interventions_analytics", data)
        self.assertIn("executive_dean_recommendations", data)

        self.assertGreater(len(data["department_heatmaps"]), 0)
        dept = data["department_heatmaps"][0]
        self.assertIn("department", dept)
        self.assertIn("estimated_pass_rate", dept)
        self.logout()


if __name__ == "__main__":
    unittest.main()
