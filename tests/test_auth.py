"""
Dedicated Authentication & Role-Based Access Control Test Suite
Validates real database lookups, password hashing, role boundaries,
teacher-student creation flow, and session destruction.
"""

import os
import sys
import unittest
import sqlite3

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import get_db_connection

class TestDatabaseAuthentication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cleanup_test_data()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_test_data()

    @classmethod
    def cleanup_test_data(cls):
        test_emails = [
            "test.student.reg@apedu.ac.in",
            "test.teacher.reg@apedu.ac.in",
            "newly.created.student@apedu.ac.in"
        ]
        conn = get_db_connection()
        cursor = conn.cursor()
        for em in test_emails:
            cursor.execute("DELETE FROM students WHERE LOWER(email) = ?", (em.lower(),))
            cursor.execute("DELETE FROM teachers WHERE LOWER(email) = ?", (em.lower(),))
            cursor.execute("DELETE FROM users WHERE LOWER(email) = ?", (em.lower(),))
        conn.commit()
        conn.close()

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_01_create_student_registration(self):
        """Test 1: Student registration stores student in database."""
        email = "test.student.reg@apedu.ac.in"
        roll_no = "23A91A9901"
        res = self.client.post("/api/register/student", json={
            "full_name": "Arun Kumar",
            "roll_no": roll_no,
            "email": email,
            "password": "ArunPassword123",
            "year": "2nd Year",
            "branch": "CSE",
            "section": "A",
            "semester": 3
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Check DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower(),))
        user = cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "student")
        
        cursor.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,))
        student = cursor.fetchone()
        self.assertIsNotNone(student)
        conn.close()

    def test_02_create_teacher_registration(self):
        """Test 2: Teacher registration stores teacher in database."""
        email = "test.teacher.reg@apedu.ac.in"
        res = self.client.post("/api/register/teacher", json={
            "full_name": "Prof. Ravi Shankar",
            "email": email,
            "password": "RaviPassword123",
            "branch": "ECE",
            "year": "3rd Year",
            "section": "B"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Check DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower(),))
        user = cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "teacher")
        conn.close()

    def test_03_student_login_success(self):
        """Test 3: Student login with correct credentials -> SUCCESS."""
        res = self.client.post("/api/login/student", json={
            "email": "test.student.reg@apedu.ac.in",
            "password": "ArunPassword123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "student")

    def test_04_student_login_wrong_password(self):
        """Test 4: Student login with wrong password -> FAIL."""
        res = self.client.post("/api/login/student", json={
            "email": "test.student.reg@apedu.ac.in",
            "password": "WrongPassword999"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_05_student_credentials_in_teacher_login(self):
        """Test 5: Student credentials used in Teacher Login -> FAIL."""
        res = self.client.post("/api/login/teacher", json={
            "email": "test.student.reg@apedu.ac.in",
            "password": "ArunPassword123"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_06_teacher_credentials_in_student_login(self):
        """Test 6: Teacher credentials used in Student Login -> FAIL."""
        res = self.client.post("/api/login/student", json={
            "email": "test.teacher.reg@apedu.ac.in",
            "password": "RaviPassword123"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_07_teacher_adds_student(self):
        """Test 7: Teacher adds student via dashboard API -> Student appears in database."""
        # 1. Login as teacher
        self.client.post("/api/login/teacher", json={
            "email": "test.teacher.reg@apedu.ac.in",
            "password": "RaviPassword123"
        })

        # 2. Add student
        new_email = "newly.created.student@apedu.ac.in"
        new_roll = "23A91A8802"
        res = self.client.post("/api/teacher/student", json={
            "full_name": "Sita Lakshmi",
            "roll_no": new_roll,
            "email": new_email,
            "password": "SitaSecurePassword456",
            "year": "2nd Year",
            "branch": "CSE",
            "section": "B",
            "semester": 4,
            "attendance": 82.0,
            "programming_score": 75.0,
            "mathematics_score": 80.0
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])

        # 3. Check DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE roll_no = ?", (new_roll,))
        st = cursor.fetchone()
        self.assertIsNotNone(st)
        self.assertEqual(st["full_name"], "Sita Lakshmi")
        conn.close()

        # Logout teacher
        self.client.post("/api/logout")

    def test_08_newly_added_student_logs_in(self):
        """Test 8: Newly created student logs in with their credentials -> SUCCESS."""
        res = self.client.post("/api/login/student", json={
            "email": "newly.created.student@apedu.ac.in",
            "password": "SitaSecurePassword456"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["role"], "student")

        # Verify /api/me returns safe student info
        res_me = self.client.get("/api/me")
        me_data = res_me.get_json()
        self.assertTrue(me_data["logged_in"])
        self.assertEqual(me_data["role"], "student")
        self.assertEqual(me_data["full_name"], "Sita Lakshmi")
        self.assertEqual(me_data["roll_no"], "23A91A8802")
        self.assertNotIn("password", me_data)
        self.assertNotIn("password_hash", me_data)

    def test_09_student_tries_teacher_routes(self):
        """Test 9: Student attempts to access teacher-only API / dashboard -> DENIED (403)."""
        # Login as student
        self.client.post("/api/login/student", json={
            "email": "newly.created.student@apedu.ac.in",
            "password": "SitaSecurePassword456"
        })

        # Try accessing teacher analytics
        res = self.client.get("/api/teacher/analytics")
        self.assertEqual(res.status_code, 403)

        # Try accessing teacher students list
        res_stu = self.client.get("/api/teacher/students")
        self.assertEqual(res_stu.status_code, 403)

        # Try accessing student details by teacher
        res_det = self.client.get("/api/teacher/student/1")
        self.assertEqual(res_det.status_code, 403)

    def test_10_teacher_tries_student_route(self):
        """Test 10: Teacher attempts to access student-only route -> DENIED (403)."""
        # Login as teacher
        self.client.post("/api/login/teacher", json={
            "email": "test.teacher.reg@apedu.ac.in",
            "password": "RaviPassword123"
        })

        # Try accessing student-only endpoint
        res = self.client.get("/api/student/me")
        self.assertEqual(res.status_code, 403)

        res_path = self.client.get("/api/student/learning-path")
        self.assertEqual(res_path.status_code, 403)

    def test_11_logout_destroys_session(self):
        """Test 11: Logout destroys session -> Protected endpoints return 401."""
        # 1. Login
        self.client.post("/api/login/student", json={
            "email": "test.student.reg@apedu.ac.in",
            "password": "ArunPassword123"
        })

        # Verify logged in
        me_before = self.client.get("/api/me").get_json()
        self.assertTrue(me_before["logged_in"])

        # 2. Logout
        res_logout = self.client.post("/api/logout")
        self.assertEqual(res_logout.status_code, 200)

        # 3. Verify logged out
        me_after = self.client.get("/api/me").get_json()
        self.assertFalse(me_after["logged_in"])

        # Accessing protected endpoint should now be 401
        res_prot = self.client.get("/api/student/me")
        self.assertEqual(res_prot.status_code, 401)

    def test_12_database_passwords_are_hashed(self):
        """Test 12: Database inspection confirms passwords are HASHED and never plaintext."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email, password_hash FROM users")
        rows = cursor.fetchall()
        conn.close()

        self.assertGreater(len(rows), 0)
        for r in rows:
            pwd_hash = r["password_hash"]
            # Must not be plaintext passwords
            self.assertNotEqual(pwd_hash, "ArunPassword123")
            self.assertNotEqual(pwd_hash, "RaviPassword123")
            self.assertNotEqual(pwd_hash, "SitaSecurePassword456")
            self.assertNotEqual(pwd_hash, "student123")
            self.assertNotEqual(pwd_hash, "teacher123")
            # Must be a valid werkzeug hash format (scrypt: or pbkdf2:)
            self.assertTrue(pwd_hash.startswith("scrypt:") or pwd_hash.startswith("pbkdf2:"))

if __name__ == "__main__":
    unittest.main()
