"""
Verification Test Suite for Real-Time Dynamic Adaptive Quiz Engine & Remedial Recovery Paths.
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
from data.seed_academic_data import seed_academic_curriculum


class TestAdaptiveQuizEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_academic_curriculum()
        cls.client = app.test_client()

    def login_student(self):
        res = self.client.post(
            "/api/login",
            data=json.dumps({"email": "student.au@au.edu.in", "password": "student123"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)

    def logout(self):
        self.client.post("/api/logout")

    def test_01_adaptive_session_start(self):
        """Adaptive start endpoint initializes session with calibrated difficulty."""
        self.login_student()
        conn = get_db_connection()
        t_id = conn.cursor().execute("SELECT id FROM topics LIMIT 1").fetchone()[0]
        conn.close()

        res = self.client.get(f"/api/student/topic/{t_id}/adaptive/start")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("starting_difficulty", data)
        self.assertIn("question", data)
        self.assertEqual(data["total_steps"], 5)
        self.logout()

    def test_02_adaptive_step_difficulty_scaling(self):
        """Adaptive step endpoint correctly grades answer and calculates difficulty transition."""
        self.login_student()
        conn = get_db_connection()
        t_id = conn.cursor().execute("SELECT id FROM topics LIMIT 1").fetchone()[0]
        conn.close()

        # Start session
        start_res = self.client.get(f"/api/student/topic/{t_id}/adaptive/start")
        q = start_res.get_json()["question"]

        # Step 1: Submit correct answer (option A)
        step_payload = {
            "question_id": q["id"],
            "selected_option": "A",
            "current_difficulty": "Intermediate",
            "answered_ids": [],
            "step_number": 1,
            "total_steps": 5
        }
        step_res = self.client.post(
            f"/api/student/topic/{t_id}/adaptive/step",
            data=json.dumps(step_payload),
            content_type="application/json"
        )
        self.assertEqual(step_res.status_code, 200)
        step_data = step_res.get_json()
        self.assertTrue(step_data["success"])
        self.assertIn("is_correct", step_data)
        self.assertIn("difficulty_transition", step_data)
        self.logout()

    def test_03_adaptive_finish_and_remedial_recovery_path(self):
        """Adaptive finish endpoint updates mastery, runs ML prediction, and builds 3-step remedial path."""
        self.login_student()
        conn = get_db_connection()
        t_id = conn.cursor().execute("SELECT id FROM topics LIMIT 1").fetchone()[0]
        conn.close()

        # Finish quiz with low score (1 / 5 = 20%) to trigger remedial recovery path
        finish_payload = {
            "topic_id": t_id,
            "total_questions": 5,
            "correct_count": 1,
            "time_spent_minutes": 7.5,
            "progression": [
                {"step": 1, "difficulty": "Intermediate", "is_correct": False, "shifted_to": "Beginner"},
                {"step": 2, "difficulty": "Beginner", "is_correct": True, "shifted_to": "Intermediate"},
                {"step": 3, "difficulty": "Intermediate", "is_correct": False, "shifted_to": "Beginner"},
                {"step": 4, "difficulty": "Beginner", "is_correct": False, "shifted_to": "Beginner"},
                {"step": 5, "difficulty": "Beginner", "is_correct": False, "shifted_to": "Beginner"}
            ]
        }

        finish_res = self.client.post(
            f"/api/student/topic/{t_id}/adaptive/finish",
            data=json.dumps(finish_payload),
            content_type="application/json"
        )
        self.assertEqual(finish_res.status_code, 200)
        finish_data = finish_res.get_json()
        self.assertTrue(finish_data["success"])
        self.assertEqual(finish_data["score_percentage"], 20.0)
        
        # Verify Remedial Recovery Path was generated
        remedial = finish_data["remedial_path"]
        self.assertEqual(remedial["status"], "needs_remediation")
        self.assertEqual(len(remedial["action_steps"]), 3)
        self.assertIn("Review Grounded Textbook Reading", remedial["action_steps"][0]["title"])
        self.assertIn("Complete Diagnostic Practice Drill", remedial["action_steps"][1]["title"])
        self.assertIn("Unlock Mastery Re-Test Challenge", remedial["action_steps"][2]["title"])
        self.logout()


if __name__ == "__main__":
    unittest.main()
