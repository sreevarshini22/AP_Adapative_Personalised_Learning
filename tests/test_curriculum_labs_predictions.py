"""
Test Suite for Complete Academic Curriculum, Labs, Lessons, Assessment Removal & Personalized ML Predictions
"""

import unittest
from backend.app import create_app
from backend.database import get_db_connection, init_db
from data.seed_academic_data import seed_academic_curriculum


class TestCurriculumLabsAndPersonalizedPredictions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_academic_curriculum()

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_01_all_branches_and_semesters_have_subjects(self):
        """Validates that all branches have subjects across years and semesters."""
        conn = get_db_connection()
        c = conn.cursor()
        
        branches = [
            "CSE", "CSE (AI & ML)", "CSE (Data Science)", "ECE", "EEE",
            "Mechanical Engineering", "Civil Engineering", "Information Technology"
        ]
        
        for branch in branches:
            c.execute("SELECT count(*) FROM subjects WHERE branch = ?", (branch,))
            count = c.fetchone()[0]
            self.assertGreater(count, 0, f"Branch {branch} has no subjects seeded!")
            
        # Total subjects check
        c.execute("SELECT count(*) FROM subjects")
        total_subs = c.fetchone()[0]
        self.assertGreaterEqual(total_subs, 60, f"Expected >= 60 subjects, found {total_subs}")
        conn.close()

    def test_02_all_subjects_have_lessons(self):
        """Validates that every single subject in the database has associated lessons."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, subject_code, subject_name FROM subjects")
        subjects = c.fetchall()
        
        for s in subjects:
            c.execute("SELECT count(*) FROM lessons WHERE subject_id = ?", (s["id"],))
            lesson_count = c.fetchone()[0]
            self.assertGreaterEqual(lesson_count, 3, f"Subject {s['subject_code']} ({s['subject_name']}) has only {lesson_count} lessons!")
        conn.close()

    def test_03_integrated_and_lab_subjects_have_labs(self):
        """Validates that integrated and lab subjects have experiments in labs table."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, subject_code, subject_name, subject_type FROM subjects WHERE subject_type IN ('integrated', 'lab')")
        lab_subjects = c.fetchall()
        self.assertGreater(len(lab_subjects), 0)
        
        for s in lab_subjects:
            c.execute("SELECT count(*) FROM labs WHERE subject_id = ?", (s["id"],))
            lab_count = c.fetchone()[0]
            self.assertGreaterEqual(lab_count, 2, f"Subject {s['subject_code']} ({s['subject_name']}) has only {lab_count} labs!")
        conn.close()

    def test_04_student_dashboard_has_no_assessments_module(self):
        """Verifies that the assessments module is removed from student dashboard frontend."""
        res = self.client.get("/student-dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        
        # Check no sidebar nav link for assessments
        self.assertNotIn("switchView('assessments')", html)
        # Check no view-assessments container
        self.assertNotIn('id="view-assessments"', html)
        self.assertNotIn("loadAssessmentsTable()", html)

    def test_05_personalized_learning_predictions_endpoint(self):
        """Verifies that the personalized learning prediction endpoint generates ML outputs."""
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        
        # 1. Prediction endpoint
        pred_res = self.client.get("/api/student/prediction")
        self.assertEqual(pred_res.status_code, 200)
        pred_data = pred_res.get_json()
        self.assertTrue(pred_data["success"])
        
        pred = pred_data["prediction"]
        self.assertIn(pred["risk_level"], ["Low Risk", "Medium Risk", "High Risk"])
        self.assertIsInstance(pred["risk_score"], (int, float))
        self.assertIsInstance(pred["confidence_percentage"], (int, float))
        self.assertIsInstance(pred["top_risk_drivers"], list)
        self.assertGreater(len(pred["top_risk_drivers"]), 0)

        # 2. Learning path endpoint
        path_res = self.client.get("/api/student/learning-path")
        self.assertEqual(path_res.status_code, 200)
        path_data = path_res.get_json()
        self.assertTrue(path_data["success"])
        
        path = path_data["learning_path"]
        self.assertIsInstance(path, list)
        self.assertGreater(len(path), 0)
        first_step = path[0]
        self.assertIn("module", first_step)
        self.assertIn("subject", first_step)
        self.assertIn("priority", first_step)


if __name__ == "__main__":
    unittest.main()
