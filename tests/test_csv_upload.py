"""
Automated Test Suite for Teacher CSV Student Bulk Upload & Dynamic Subject Filtering
Validates CSV template download, pre-import validation, duplicate detection,
password hashing in SQLite, immediate student login, and branch/year/sem subject isolation.
"""

import os
import sys
import io
import unittest
from werkzeug.security import check_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import get_db_connection, init_db
from data.seed_academic_data import seed_academic_curriculum

class TestStudentCsvUploadAndSubjectFiltering(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_academic_curriculum()

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self._cleanup_test_records()

    def tearDown(self):
        self._cleanup_test_records()

    def _cleanup_test_records(self):
        conn = get_db_connection()
        c = conn.cursor()
        test_emails = [
            'ananya.test@apedu.ac.in', 'divya.ai@apedu.ac.in',
            'kiran.ece@apedu.ac.in', 'fresh.mech@apedu.ac.in',
            '23ai701@student.apedu.ac.in', '23me901@student.apedu.ac.in',
            '23ece801@student.apedu.ac.in', '23cse501@student.apedu.ac.in'
        ]
        test_rolls = ['23CSE501', '23AI701', '23ECE801', '23ME901']
        for email in test_emails:
            c.execute("DELETE FROM students WHERE LOWER(email) = ?", (email,))
            c.execute("DELETE FROM users WHERE LOWER(email) = ?", (email,))
        for roll in test_rolls:
            c.execute("DELETE FROM students WHERE UPPER(roll_no) = ?", (roll,))
        conn.commit()
        conn.close()

    def test_01_download_csv_template(self):
        """Test 1: Teacher can download the CSV template with 5 mandatory columns."""
        # 1. Login as teacher
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        
        # 2. Download template
        res = self.client.get("/api/teacher/students/template")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.content_type)
        csv_text = res.get_data(as_text=True)
        self.assertIn("Student Name", csv_text)
        self.assertIn("Roll No", csv_text)
        self.assertIn("Branch", csv_text)
        self.assertIn("Year", csv_text)
        self.assertIn("Section", csv_text)
        self.assertIn("Rahul Kumar", csv_text)
        self.assertIn("23A91A0501", csv_text)

    def test_02_csv_preview_validation(self):
        """Test 2: CSV preview endpoint validates rows, detects invalid records & missing values."""
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        
        # Valid + Invalid mix 5-column CSV
        csv_content = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Ananya Sen,23CSE501,CSE,2nd Year,A\n"
            ",23CSE502,CSE,2nd Year,A\n"
            "Missing Year,23CSE503,CSE,,A\n"
        )
        
        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "students_test.csv")
        }
        
        res = self.client.post(
            "/api/teacher/students/upload/preview",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 200)
        preview_data = res.get_json()
        self.assertTrue(preview_data["success"])
        self.assertEqual(preview_data["total_rows"], 3)
        self.assertEqual(preview_data["valid_count"], 1)
        self.assertEqual(preview_data["invalid_count"], 2)
        self.assertEqual(len(preview_data["preview"]), 1)
        self.assertEqual(preview_data["preview"][0]["student_name"], "Ananya Sen")
        self.assertEqual(preview_data["preview"][0]["roll_no"], "23CSE501")
        self.assertEqual(preview_data["preview"][0]["branch"], "CSE")

    def test_03_missing_header_validation_error(self):
        """Test 3: Missing required column returns exact error message."""
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        
        # CSV missing Section column
        csv_content = (
            "Student Name,Roll No,Branch,Year\n"
            "Ananya Sen,23CSE501,CSE,2nd Year\n"
        )
        
        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "missing_header.csv")
        }
        
        res = self.client.post(
            "/api/teacher/students/upload/preview",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 400)
        preview_data = res.get_json()
        self.assertFalse(preview_data["success"])
        self.assertEqual(preview_data["message"], "Invalid CSV. Required columns: Student Name, Roll No, Branch, Year, Section.")

    def test_04_bulk_csv_upload_and_password_hashing(self):
        """Test 4: Teacher uploads 5-column CSV -> Students inserted into SQLite with hashed passwords."""
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        
        csv_content = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Divya Reddy,23AI701,AIML,2,B\n"
            "Kiran Rao,23ECE801,ECE,3,A\n"
        )
        
        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "bulk_students.csv")
        }
        
        res = self.client.post(
            "/api/teacher/students/upload",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 201)
        res_data = res.get_json()
        self.assertTrue(res_data["success"])
        self.assertEqual(res_data["imported_rows"], 2)
        self.assertEqual(res_data["skipped_rows"], 0)
        
        # Verify in SQLite database that password is NOT stored in plaintext
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT email, password_hash FROM users WHERE email = '23ai701@student.apedu.ac.in'")
        user_row = c.fetchone()
        self.assertIsNotNone(user_row)
        self.assertTrue(check_password_hash(user_row["password_hash"], "23ai701"))
        
        # Verify import history table
        c.execute("SELECT file_name, imported_rows FROM student_import_history ORDER BY id DESC LIMIT 1")
        hist_row = c.fetchone()
        self.assertEqual(hist_row["file_name"], "bulk_students.csv")
        self.assertEqual(hist_row["imported_rows"], 2)
        conn.close()

    def test_05_duplicate_handling(self):
        """Test 5: Re-uploading existing roll numbers skips duplicates safely."""
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        
        # 1. Initial upload for Divya
        csv_initial = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Divya Reddy,23AI701,AIML,2nd Year,B\n"
        )
        self.client.post(
            "/api/teacher/students/upload",
            data={"file": (io.BytesIO(csv_initial.encode("utf-8")), "init_test.csv")},
            content_type="multipart/form-data"
        )
        
        # 2. Second upload containing Divya (duplicate) and Fresh Student (new)
        csv_duplicate = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Divya Reddy,23AI701,AIML,2nd Year,B\n"
            "Fresh Student,23ME901,Mechanical Engineering,4th Year,A\n"
        )
        
        data = {
            "file": (io.BytesIO(csv_duplicate.encode("utf-8")), "dup_test.csv")
        }
        
        res = self.client.post(
            "/api/teacher/students/upload",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 201)
        res_data = res.get_json()
        self.assertEqual(res_data["imported_rows"], 1) # Fresh Student imported
        self.assertEqual(res_data["skipped_rows"], 1) # Divya duplicate skipped

    def test_06_new_student_immediate_login_and_dynamic_subject_isolation(self):
        """Test 6: Imported student can immediately login & sees strictly only their matching subjects."""
        # 1. Teacher uploads student
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        csv_content = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Divya Reddy,23AI701,AIML,2nd Year,B\n"
        )
        self.client.post(
            "/api/teacher/students/upload",
            data={"file": (io.BytesIO(csv_content.encode("utf-8")), "divya_upload.csv")},
            content_type="multipart/form-data"
        )
        self.client.post("/api/logout")

        # 2. Student login using credentials from CSV upload (email generated or roll_no)
        res_login = self.client.post("/api/login/student", json={
            "email": "23ai701@student.apedu.ac.in",
            "password": "23ai701"
        })
        self.assertEqual(res_login.status_code, 200)
        login_data = res_login.get_json()
        self.assertTrue(login_data["success"])
        self.assertEqual(login_data["user"]["role"], "student")
        
        # 3. Student calls /api/student/subjects
        res_sub = self.client.get("/api/student/subjects")
        self.assertEqual(res_sub.status_code, 200)
        sub_data = res_sub.get_json()
        self.assertTrue(sub_data["success"])
        self.assertEqual(sub_data["branch"], "CSE (AI & ML)")
        self.assertEqual(sub_data["year"], "2nd Year")
        self.assertEqual(sub_data["semester"], 3)
        
        subject_codes = [s["subject_code"] for s in sub_data["subjects"]]
        # Divya (CSE AI&ML, 2nd Year, 3rd Sem) must receive AIML201, AIML202, MA202
        self.assertIn("AIML201", subject_codes)
        self.assertIn("AIML202", subject_codes)
        self.assertIn("MA202", subject_codes)
        
        # Must NOT receive CSE 5th sem, Mechanical, or ECE subjects
        self.assertNotIn("CS301", subject_codes)
        self.assertNotIn("EC401", subject_codes)
        self.assertNotIn("ME201", subject_codes)

    def test_07_student_cannot_upload_csv(self):
        """Test 7: Role isolation - Student is forbidden from calling teacher upload endpoints."""
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        
        res = self.client.post(
            "/api/teacher/students/upload",
            data={"file": (io.BytesIO(b"data"), "test.csv")},
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 403)

if __name__ == "__main__":
    unittest.main()
