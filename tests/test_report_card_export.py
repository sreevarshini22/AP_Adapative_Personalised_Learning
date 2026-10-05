"""
Unit tests for Step 5: Automated Student PDF Report Card & Transcript Export
Verifies student dossier generation, Quantum ML diagnostics, Bloom cognitive mastery index,
gamification badges, gradebook SGPA/CGPA, and teacher access controls.
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


class TestReportCardExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def login_student(self):
        res = self.client.post(
            "/api/login",
            data=json.dumps({"email": "student.au@au.edu.in", "password": "student123"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200, "Student should log in successfully")

    def login_teacher(self):
        res = self.client.post(
            "/api/login",
            data=json.dumps({"email": "prof.murthy@au.edu.in", "password": "teacher123"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200, "Teacher should log in successfully")

    def logout(self):
        self.client.post("/api/logout")

    def test_01_student_report_card_export(self):
        """Student can fetch their complete verifiable academic dossier and report card."""
        self.login_student()

        # Fetch report card
        res = self.client.get("/api/student/report-card")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data.get("success"))
        report = data.get("report_card")
        self.assertIsNotNone(report)

        # 1. Verification & Identity
        self.assertTrue(report["report_id"].startswith("AP-AU-2025-"))
        self.assertIn("verification_hash", report)
        self.assertIn("institution", report)
        self.assertIn(report["institution"]["code"], ["AU_ENG", "AU-ENG-01"])

        # 2. Student Info
        student_info = report["student"]
        self.assertEqual(student_info["email"], "student.au@au.edu.in")
        self.assertIn("roll_no", student_info)
        self.assertIn("xp_points", student_info)

        # 3. Quantum ML Diagnostics
        qml = report["quantum_ml_evaluation"]
        self.assertIn("risk_level", qml)
        self.assertIn("confidence", qml)
        self.assertIn("quantum_circuit", qml)

        # 4. Academic Metrics & Subjects
        metrics = report["academic_metrics"]
        self.assertIn("sgpa", metrics)
        self.assertIn("cgpa", metrics)
        self.assertIsInstance(metrics["subjects"], list)
        self.assertGreater(len(metrics["subjects"]), 0)
        for s in metrics["subjects"]:
            self.assertIn("subject_name", s)
            self.assertIn("grade", s)
            self.assertIn("grade_point", s)

        # 5. Bloom's Cognitive Mastery Index
        bloom = report["bloom_mastery"]
        for level in ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]:
            self.assertIn(level, bloom)

        # 6. Gamification & Signatories
        self.assertIn("gamification", report)
        self.assertIn("signatories", report)
        self.assertIn("dean_academics", report["signatories"])

    def test_02_teacher_can_export_assigned_student_report_card(self):
        """Teacher can view and export report card for an assigned student."""
        self.login_teacher()

        # Find an assigned student
        st_res = self.client.get("/api/teacher/students")
        self.assertEqual(st_res.status_code, 200)
        st_data = st_res.get_json()
        self.assertTrue(st_data["success"])
        self.assertGreater(len(st_data["students"]), 0)
        student_id = st_data["students"][0]["id"]

        # Fetch report card
        res = self.client.get(f"/api/teacher/students/{student_id}/report-card")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["report_card"]["student"]["id"], student_id)

    def test_03_teacher_denied_for_unassigned_student_report_card(self):
        """Teacher cannot export report card for a student outside assigned cohort."""
        self.login_teacher()

        # Try to access a non-existent or unassigned student ID (e.g. 99999)
        res = self.client.get("/api/teacher/students/99999/report-card")
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
