"""
Academic Learning Portal Automated Test Suite
Validates dynamic branch/year/sem subject resolution, lesson/lab progress tracking,
adaptive quiz evaluation, and threaded teacher messaging.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import get_db_connection, init_db
from data.seed_academic_data import seed_academic_curriculum

class TestAcademicLearningPortal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_academic_curriculum()

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_01_dynamic_subject_resolution_by_branch_year_sem(self):
        """Test 1: Student receives only subjects strictly matching their branch, year, semester."""
        # 1. Login as Rahul (CSE, 2nd Year, 3rd Sem, Sec A)
        res = self.client.post("/api/login/student", json={
            "email": "rahul.2ndyear@apedu.ac.in",
            "password": "student123"
        })
        self.assertEqual(res.status_code, 200)

        # 2. Fetch subjects
        res_sub = self.client.get("/api/student/subjects")
        self.assertEqual(res_sub.status_code, 200)
        data = res_sub.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["branch"], "CSE")
        self.assertEqual(data["year"], "2nd Year")
        self.assertEqual(data["semester"], 3)
        
        subject_codes = [s["subject_code"] for s in data["subjects"]]
        self.assertIn("CS201", subject_codes) # Data Structures
        self.assertIn("CS202", subject_codes) # DBMS
        self.assertIn("CS203", subject_codes) # OS
        
        # Verify 3rd Year / 5th Sem and ECE subjects are NOT in Rahul's list
        self.assertNotIn("CS301", subject_codes) # 5th Sem Machine Learning
        self.assertNotIn("EC401", subject_codes) # ECE VLSI Design

    def test_02_assigned_teacher_resolution(self):
        """Test 2: Teacher assignment is correctly resolved for student's section."""
        self.client.post("/api/login/student", json={
            "email": "rahul.2ndyear@apedu.ac.in",
            "password": "student123"
        })
        res_sub = self.client.get("/api/student/subjects")
        data = res_sub.get_json()
        
        ds_subject = next(s for s in data["subjects"] if s["subject_code"] == "CS201")
        self.assertEqual(ds_subject["teacher"]["name"], "Dr. Ravi Kumar")

    def test_03_lesson_completion_workflow(self):
        """Test 3: Completing a lesson updates database and recalculates progress."""
        self.client.post("/api/login/student", json={
            "email": "rahul.2ndyear@apedu.ac.in",
            "password": "student123"
        })
        
        # 1. Fetch lessons for Data Structures
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM subjects WHERE subject_code = 'CS201'")
        ds_id = c.fetchone()[0]
        conn.close()
        
        res_les = self.client.get(f"/api/student/subjects/{ds_id}/lessons")
        les_data = res_les.get_json()
        self.assertTrue(len(les_data["lessons"]) > 0)
        first_lesson_id = les_data["lessons"][0]["id"]
        
        # 2. Complete the lesson
        res_comp = self.client.post(f"/api/student/lessons/{first_lesson_id}/complete")
        self.assertEqual(res_comp.status_code, 200)
        
        # 3. Verify in database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT status, progress_percentage FROM lesson_progress WHERE lesson_id = ?", (first_lesson_id,))
        prog = c.fetchone()
        self.assertEqual(prog["status"], "Completed")
        self.assertEqual(prog["progress_percentage"], 100.0)
        conn.close()

    def test_04_lab_completion_workflow(self):
        """Test 4: Completing a lab experiment persists score in database."""
        self.client.post("/api/login/student", json={
            "email": "rahul.2ndyear@apedu.ac.in",
            "password": "student123"
        })
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM subjects WHERE subject_code = 'CS201'")
        ds_id = c.fetchone()[0]
        c.execute("SELECT id FROM labs WHERE subject_id = ? LIMIT 1", (ds_id,))
        lab_id = c.fetchone()[0]
        conn.close()
        
        res_lab = self.client.post(f"/api/student/labs/{lab_id}/complete", json={"score": 95.0})
        self.assertEqual(res_lab.status_code, 200)
        
        # Verify in DB
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT status, score FROM lab_progress WHERE lab_id = ?", (lab_id,))
        l_prog = c.fetchone()
        self.assertEqual(l_prog["status"], "Completed")
        self.assertEqual(l_prog["score"], 95.0)
        conn.close()

    def test_05_adaptive_quiz_evaluation_and_recommendations(self):
        """Test 5: Submitting quiz calculates score and builds adaptive recommendations."""
        self.client.post("/api/login/student", json={
            "email": "rahul.2ndyear@apedu.ac.in",
            "password": "student123"
        })
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM subjects WHERE subject_code = 'CS201'")
        ds_id = c.fetchone()[0]
        c.execute("SELECT id FROM quizzes WHERE subject_id = ? LIMIT 1", (ds_id,))
        quiz_id = c.fetchone()[0]
        c.execute("SELECT id, correct_option FROM quiz_questions WHERE quiz_id = ?", (quiz_id,))
        questions = c.fetchall()
        conn.close()
        
        # Intentionally submit 1 correct, remaining incorrect to test adaptive remediation
        user_answers = {}
        for idx, q in enumerate(questions):
            if idx == 0:
                user_answers[str(q["id"])] = q["correct_option"] # Correct
            else:
                user_answers[str(q["id"])] = "Z" # Incorrect
                
        res_submit = self.client.post(f"/api/student/quizzes/{quiz_id}/submit", json={"answers": user_answers})
        self.assertEqual(res_submit.status_code, 200)
        data = res_submit.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["score"], 1.0)
        self.assertLess(data["percentage"], 50.0)
        self.assertTrue(len(data["adaptive_recommendations"]) > 0)
        self.assertEqual(data["adaptive_recommendations"][0]["type"], "Remedial Revision")

    def test_06_student_to_teacher_messaging_thread(self):
        """Test 6: Student messages assigned teacher, and teacher views & replies."""
        # 1. Student sends message
        self.client.post("/api/login/student", json={
            "email": "rahul.2ndyear@apedu.ac.in",
            "password": "student123"
        })
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM subjects WHERE subject_code = 'CS201'")
        ds_id = c.fetchone()[0]
        conn.close()
        
        res_msg = self.client.post("/api/student/messages", json={
            "subject_id": ds_id,
            "message": "Dr. Ravi, can you please clarify tree traversals?"
        })
        self.assertEqual(res_msg.status_code, 201)
        conv_id = res_msg.get_json()["conversation_id"]
        
        # 2. Teacher logs in and reads thread
        self.client.post("/api/login/teacher", json={
            "email": "dr.ravi@apedu.ac.in",
            "password": "teacher123"
        })
        
        res_t_threads = self.client.get("/api/teacher/messages")
        self.assertEqual(res_t_threads.status_code, 200)
        
        res_t_chat = self.client.get(f"/api/teacher/messages/{conv_id}")
        self.assertEqual(res_t_chat.status_code, 200)
        chat_data = res_t_chat.get_json()
        self.assertTrue(any("tree traversals" in m["message"] for m in chat_data["messages"]))
        
        # 3. Teacher replies
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM students WHERE LOWER(email) = 'rahul.2ndyear@apedu.ac.in'")
        rahul_id = c.fetchone()[0]
        conn.close()
        
        res_reply = self.client.post("/api/teacher/messages", json={
            "conversation_id": conv_id,
            "student_id": rahul_id,
            "subject_id": ds_id,
            "message": "Inorder traversal for BST always visits nodes in ascending order."
        })
        self.assertEqual(res_reply.status_code, 201)
        
        # 4. Student logs back in and checks notifications
        self.client.post("/api/login/student", json={
            "email": "rahul.2ndyear@apedu.ac.in",
            "password": "student123"
        })
        
        res_notif = self.client.get("/api/student/notifications")
        self.assertEqual(res_notif.status_code, 200)
        notifs = res_notif.get_json()["notifications"]
        self.assertTrue(any("Dr. Ravi Kumar" in n["title"] or "Dr. Ravi Kumar" in n["message"] for n in notifs))

if __name__ == "__main__":
    unittest.main()
