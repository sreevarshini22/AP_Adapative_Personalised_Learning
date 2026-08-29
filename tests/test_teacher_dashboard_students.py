"""
Comprehensive Test Suite for Teacher Dashboard Student Persistence & CSV Upload
Tests all 7 explicit test requirements from the user request.
"""

import io
import json
import unittest

from backend.app import create_app
from backend.database import get_db_connection, DB_PATH


class TestTeacherDashboardStudentPersistence(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self._clean_test_records()

    def tearDown(self):
        self._clean_test_records()

    def _clean_test_records(self):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM students WHERE email IN ('rahul.test@gmail.com', 'ananya.test@gmail.com')")
        c.execute("DELETE FROM users WHERE email IN ('rahul.test@gmail.com', 'ananya.test@gmail.com')")
        c.execute("DELETE FROM students WHERE roll_no IN ('23CSE101_TEST', '23AI102_TEST')")
        conn.commit()
        conn.close()

    def test_complete_teacher_student_persistence_lifecycle(self):
        # 1. Login as teacher
        login_res = self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        self.assertEqual(login_res.status_code, 200)

        # 2. Upload CSV with Rahul Kumar
        csv1 = (
            "student_name,roll_no,email,password,year,branch,section,semester,attendance,mathematics_score,physics_score,programming_score\n"
            "Rahul Kumar,23CSE101_TEST,rahul.test@gmail.com,RahulPass123,2nd Year,CSE,A,3,82.0,75.0,78.0,85.0\n"
        )
        up_res = self.client.post("/api/teacher/students/upload", data={
            "file": (io.BytesIO(csv1.encode("utf-8")), "test_rahul.csv")
        }, content_type="multipart/form-data")
        self.assertEqual(up_res.status_code, 201)
        self.assertEqual(up_res.get_json()["imported_rows"], 1)

        # 3. Confirm student is inserted into SQLite
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT full_name, roll_no, email, branch, year, semester, section FROM students WHERE email = 'rahul.test@gmail.com'")
        rahul_db = c.fetchone()
        conn.close()
        self.assertIsNotNone(rahul_db)
        self.assertEqual(rahul_db["full_name"], "Rahul Kumar")
        self.assertEqual(rahul_db["roll_no"], "23CSE101_TEST")

        # 4. Refresh Teacher Dashboard (/api/teacher/students) - Rahul must appear
        get_res = self.client.get("/api/teacher/students")
        self.assertEqual(get_res.status_code, 200)
        students_data = get_res.get_json()
        self.assertTrue(students_data["success"])
        rahul_in_api = next((s for s in students_data["students"] if s["email"] == "rahul.test@gmail.com"), None)
        self.assertIsNotNone(rahul_in_api)
        self.assertEqual(rahul_in_api["roll_no"], "23CSE101_TEST")

        # 5. Restart Flask App (simulate fresh instance) - Rahul must still appear
        fresh_app = create_app()
        fresh_app.config["TESTING"] = True
        fresh_client = fresh_app.test_client()
        fresh_client.post("/api/login/teacher", json={"email": "teacher@example.com", "password": "teacher123"})
        get_res2 = fresh_client.get("/api/teacher/students")
        self.assertEqual(get_res2.status_code, 200)
        rahul_restarted = next((s for s in get_res2.get_json()["students"] if s["email"] == "rahul.test@gmail.com"), None)
        self.assertIsNotNone(rahul_restarted)

        # 6. Logout & Login again as teacher - Rahul must still appear
        fresh_client.post("/api/logout")
        fresh_client.post("/api/login/teacher", json={"email": "teacher@example.com", "password": "teacher123"})
        get_res3 = fresh_client.get("/api/teacher/students")
        rahul_relogin = next((s for s in get_res3.get_json()["students"] if s["email"] == "rahul.test@gmail.com"), None)
        self.assertIsNotNone(rahul_relogin)

        # 7. Upload another student (Ananya Verma) - Both Rahul and Ananya must appear
        csv2 = (
            "student_name,roll_no,email,password,year,branch,section,semester,attendance,mathematics_score,physics_score,programming_score\n"
            "Ananya Verma,23AI102_TEST,ananya.test@gmail.com,AnanyaPass123,2nd Year,CSE (AI & ML),B,3,90.0,88.0,84.0,92.0\n"
        )
        up_res2 = fresh_client.post("/api/teacher/students/upload", data={
            "file": (io.BytesIO(csv2.encode("utf-8")), "test_ananya.csv")
        }, content_type="multipart/form-data")
        self.assertEqual(up_res2.status_code, 201)

        get_res4 = fresh_client.get("/api/teacher/students")
        all_students = get_res4.get_json()["students"]
        has_rahul = any(s["email"] == "rahul.test@gmail.com" for s in all_students)
        has_ananya = any(s["email"] == "ananya.test@gmail.com" for s in all_students)
        self.assertTrue(has_rahul)
        self.assertTrue(has_ananya)

        # 8. Search Rahul's roll number - only Rahul appears
        search_res = fresh_client.get("/api/teacher/students?search=23CSE101_TEST")
        search_list = search_res.get_json()["students"]
        self.assertEqual(len(search_list), 1)
        self.assertEqual(search_list[0]["roll_no"], "23CSE101_TEST")

        # 9. Verify API NEVER returns passwords or password hashes
        for s in all_students:
            self.assertNotIn("password", s)
            self.assertNotIn("password_hash", s)


if __name__ == "__main__":
    unittest.main()
