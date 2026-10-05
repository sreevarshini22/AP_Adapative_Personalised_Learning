"""
Verification Test Suite for Interactive Practice Coding Sandbox & Gamification Badges.
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


class TestSandboxAndGamification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

    def test_01_gamification_profile(self):
        """Gamification profile returns XP points, current level, streaks, and unlocked badges."""
        self.login_student()
        res = self.client.get("/api/student/gamification/profile")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        prof = data["profile"]
        self.assertIn("xp_points", prof)
        self.assertIn("current_level", prof)
        self.assertIn("badges", prof)
        self.assertGreaterEqual(len(prof["badges"]), 4)
        self.logout()

    def test_02_sandbox_challenges_list(self):
        """Sandbox challenges endpoint returns seeded curriculum practice problems."""
        self.login_student()
        res = self.client.get("/api/student/sandbox/challenges")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["total_challenges"], 2)
        self.logout()

    def test_03_sandbox_execution_and_badge_unlock(self):
        """Executing valid Python code passes test cases, awards XP, and unlocks badges."""
        self.login_student()
        
        # Challenge: Decision Tree Entropy
        challenges_res = self.client.get("/api/student/sandbox/challenges")
        ch_list = challenges_res.get_json()["challenges"]
        ch = ch_list[0]

        valid_code = "import math\ndef calculate_entropy(p):\n    if p <= 0 or p >= 1: return 0.0\n    return round(-p * math.log2(p) - (1 - p) * math.log2(1 - p), 4)\n"

        exec_payload = {
            "challenge_id": ch["id"],
            "code": valid_code,
            "language": "python"
        }

        res = self.client.post(
            "/api/student/sandbox/execute",
            data=json.dumps(exec_payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["execution"]["success"])
        self.assertEqual(data["execution"]["status"], "Passed")
        self.assertGreater(data["xp_earned"], 0)
        self.assertIn("gamification_profile", data)
        self.logout()


if __name__ == "__main__":
    unittest.main()
