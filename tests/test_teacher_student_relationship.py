"""
Test Suite for Teacher-to-Student Relational Architecture
Validates:
1. Teacher assignment based on (teacher_id, branch, year, section)
2. Section isolation: Teacher A (CSE 1st Year Sec A) sees only Sec A; Teacher B (Sec B) does not see Sec A
3. Student login identification of coordinates and associated Class Teacher
4. Student profile endpoint returns "Class Teacher: [Teacher Name]"
5. CSV student upload auto-associates with uploading teacher's assigned class
6. Student passwords/hashes are strictly excluded from API outputs
"""

import os
import sys
import json
import io
import unittest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import get_db_connection, init_db

class TestTeacherStudentRelationship(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["SECRET_KEY"] = "test-secret-key"
        cls.client = cls.app.test_client()

        # Initialize schema
        init_db()

        # Seed specific test cohorts
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create Test Institution
        cursor.execute("SELECT id FROM institutions WHERE code = 'TEST_UNIV'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO institutions (code, name, institution_name, aishe_code, institution_type, state, district, city, website, contact_email)
            VALUES ('TEST_UNIV', 'Test University of Technology', 'Test University of Technology', 'U-TEST-99', 'University', 'Andhra Pradesh', 'Visakhapatnam', 'Visakhapatnam', 'https://test.edu.in', 'test@test.edu.in')
            """)
            cls.inst_id = cursor.lastrowid
        else:
            cls.inst_id = row["id"]

        # 1. Create Teacher A (CSE, 1st Year, Sec A)
        pwd_hash = generate_password_hash("teacher123")
        cursor.execute("SELECT id FROM users WHERE email = 'teacher.a@test.edu.in'")
        u_row = cursor.fetchone()
        if not u_row:
            cursor.execute("INSERT INTO users (email, password_hash, role, full_name, institution_id) VALUES (?, ?, 'teacher', 'Prof. Alice Archer', ?)", ('teacher.a@test.edu.in', pwd_hash, cls.inst_id))
            cls.teacher_a_user_id = cursor.lastrowid
        else:
            cls.teacher_a_user_id = u_row["id"]

        cursor.execute("SELECT id FROM teachers WHERE email = 'teacher.a@test.edu.in'")
        t_row = cursor.fetchone()
        if not t_row:
            cursor.execute("""
            INSERT INTO teachers (user_id, full_name, email, branch, department, designation, year, section, institution_id)
            VALUES (?, 'Prof. Alice Archer', 'teacher.a@test.edu.in', 'CSE', 'Computer Science', 'Professor & Head', '1st Year', 'A', ?)
            """, (cls.teacher_a_user_id, cls.inst_id))
            cls.teacher_a_id = cursor.lastrowid
        else:
            cls.teacher_a_id = t_row["id"]

        # Ensure teacher_assignments for Teacher A
        cursor.execute("""
        INSERT OR REPLACE INTO teacher_assignments (teacher_id, branch, year, section, academic_year, is_class_teacher)
        VALUES (?, 'CSE', '1st Year', 'A', '2024-2025', 1)
        """, (cls.teacher_a_id,))

        # 2. Create Teacher B (CSE, 1st Year, Sec B)
        cursor.execute("SELECT id FROM users WHERE email = 'teacher.b@test.edu.in'")
        u_row = cursor.fetchone()
        if not u_row:
            cursor.execute("INSERT INTO users (email, password_hash, role, full_name, institution_id) VALUES (?, ?, 'teacher', 'Dr. Bob Bennett', ?)", ('teacher.b@test.edu.in', pwd_hash, cls.inst_id))
            cls.teacher_b_user_id = cursor.lastrowid
        else:
            cls.teacher_b_user_id = u_row["id"]

        cursor.execute("SELECT id FROM teachers WHERE email = 'teacher.b@test.edu.in'")
        t_row = cursor.fetchone()
        if not t_row:
            cursor.execute("""
            INSERT INTO teachers (user_id, full_name, email, branch, department, designation, year, section, institution_id)
            VALUES (?, 'Dr. Bob Bennett', 'teacher.b@test.edu.in', 'CSE', 'Computer Science', 'Associate Professor', '1st Year', 'B', ?)
            """, (cls.teacher_b_user_id, cls.inst_id))
            cls.teacher_b_id = cursor.lastrowid
        else:
            cls.teacher_b_id = t_row["id"]

        cursor.execute("""
        INSERT OR REPLACE INTO teacher_assignments (teacher_id, branch, year, section, academic_year, is_class_teacher)
        VALUES (?, 'CSE', '1st Year', 'B', '2024-2025', 1)
        """, (cls.teacher_b_id,))

        # 3. Create Student A1 in Sec A (linked to Teacher A)
        st_pwd = generate_password_hash("student123")
        cursor.execute("SELECT id FROM users WHERE email = 'student.a1@test.edu.in'")
        u_row = cursor.fetchone()
        if not u_row:
            cursor.execute("INSERT INTO users (email, password_hash, role, full_name, institution_id) VALUES (?, ?, 'student', 'Charlie Section A', ?)", ('student.a1@test.edu.in', st_pwd, cls.inst_id))
            cls.st_a1_uid = cursor.lastrowid
        else:
            cls.st_a1_uid = u_row["id"]
        st_a1_uid = cls.st_a1_uid

        cursor.execute("SELECT id FROM students WHERE roll_no = '24TESTCSE001'")
        st_row = cursor.fetchone()
        if not st_row:
            cursor.execute("""
            INSERT INTO students (
                user_id, full_name, roll_no, email, year, branch, section, semester,
                attendance, mathematics_score, physics_score, programming_score,
                data_structures_score, database_score, communication_score,
                assignment_score, quiz_score, exam_score, study_hours,
                learning_activity, previous_performance, overall_progress, learning_streak,
                teacher_id, institution_id
            ) VALUES (
                ?, 'Charlie Section A', '24TESTCSE001', 'student.a1@test.edu.in', '1st Year', 'CSE', 'A', 1,
                85.0, 75.0, 75.0, 80.0,
                75.0, 80.0, 75.0,
                78.0, 75.0, 75.0, 8.5,
                80.0, 75.0, 78.0, 4,
                ?, ?
            )
            """, (st_a1_uid, cls.teacher_a_id, cls.inst_id))
            cls.student_a1_id = cursor.lastrowid
        else:
            cls.student_a1_id = st_row["id"]
            cursor.execute("UPDATE students SET teacher_id = ? WHERE id = ?", (cls.teacher_a_id, cls.student_a1_id))

        # 4. Create Student B1 in Sec B (linked to Teacher B)
        cursor.execute("SELECT id FROM users WHERE email = 'student.b1@test.edu.in'")
        u_row = cursor.fetchone()
        if not u_row:
            cursor.execute("INSERT INTO users (email, password_hash, role, full_name, institution_id) VALUES (?, ?, 'student', 'Daisy Section B', ?)", ('student.b1@test.edu.in', st_pwd, cls.inst_id))
            st_b1_uid = cursor.lastrowid
        else:
            st_b1_uid = u_row["id"]

        cursor.execute("SELECT id FROM students WHERE roll_no = '24TESTCSE050'")
        st_row = cursor.fetchone()
        if not st_row:
            cursor.execute("""
            INSERT INTO students (
                user_id, full_name, roll_no, email, year, branch, section, semester,
                attendance, mathematics_score, physics_score, programming_score,
                data_structures_score, database_score, communication_score,
                assignment_score, quiz_score, exam_score, study_hours,
                learning_activity, previous_performance, overall_progress, learning_streak,
                teacher_id, institution_id
            ) VALUES (
                ?, 'Daisy Section B', '24TESTCSE050', 'student.b1@test.edu.in', '1st Year', 'CSE', 'B', 1,
                90.0, 80.0, 82.0, 85.0,
                80.0, 85.0, 80.0,
                82.0, 80.0, 80.0, 9.0,
                85.0, 80.0, 82.0, 5,
                ?, ?
            )
            """, (st_b1_uid, cls.teacher_b_id, cls.inst_id))
            cls.student_b1_id = cursor.lastrowid
        else:
            cls.student_b1_id = st_row["id"]
            cursor.execute("UPDATE students SET teacher_id = ? WHERE id = ?", (cls.teacher_b_id, cls.student_b1_id))

        conn.commit()
        conn.close()

    def test_teacher_a_roster_shows_only_section_a(self):
        """Teacher A (CSE 1st Year Sec A) must only see Section A students."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.teacher_a_user_id
            sess["role"] = "teacher"
            sess["email"] = "teacher.a@test.edu.in"
            sess["teacher_id"] = self.teacher_a_id

        res = self.client.get("/api/teacher/students")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        
        rolls = [s["roll_no"] for s in data["students"]]

        # Section A student must be present
        self.assertIn("24TESTCSE001", rolls)
        # Section B student must NOT be present
        self.assertNotIn("24TESTCSE050", rolls)
        # All returned students must have section 'A'
        for s in data["students"]:
            if s["branch"] == "CSE" and s["year"] == "1st Year":
                self.assertEqual(s["section"], "A")

    def test_teacher_b_roster_shows_only_section_b(self):
        """Teacher B (CSE 1st Year Sec B) must only see Section B students, not Section A."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.teacher_b_user_id
            sess["role"] = "teacher"
            sess["email"] = "teacher.b@test.edu.in"
            sess["teacher_id"] = self.teacher_b_id

        res = self.client.get("/api/teacher/students")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        
        rolls = [s["roll_no"] for s in data["students"]]

        # Section B student must be present
        self.assertIn("24TESTCSE050", rolls)
        # Section A student must NOT be present
        self.assertNotIn("24TESTCSE001", rolls)

    def test_teacher_me_profile_endpoint(self):
        """Teacher profile endpoint returns assigned classes and student counts."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.teacher_a_user_id
            sess["role"] = "teacher"
            sess["email"] = "teacher.a@test.edu.in"
            sess["teacher_id"] = self.teacher_a_id

        res = self.client.get("/api/teacher/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        teacher = data["teacher"]
        self.assertEqual(teacher["full_name"], "Prof. Alice Archer")
        self.assertEqual(teacher["id"], self.teacher_a_id)
        self.assertTrue(len(teacher["assigned_classes"]) >= 1)
        self.assertEqual(teacher["assigned_classes"][0]["section"], "A")

    def test_student_login_identifies_class_teacher(self):
        """Student login identifies coordinates and associated Class Teacher name."""
        res = self.client.post("/api/login/student", json={
            "email": "student.a1@test.edu.in",
            "password": "student123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        student = data["student"]
        self.assertEqual(student["full_name"], "Charlie Section A")
        self.assertEqual(student["roll_no"], "24TESTCSE001")
        self.assertEqual(student["branch"], "CSE")
        self.assertEqual(student["year"], "1st Year")
        self.assertEqual(student["section"], "A")
        self.assertEqual(student["class_teacher"], "Prof. Alice Archer")
        self.assertIn("Class Teacher: Prof. Alice Archer", student["class_teacher_display"])
        self.assertEqual(student["assigned_teacher"]["name"], "Prof. Alice Archer")

    def test_student_profile_endpoint_shows_class_teacher(self):
        """Student profile endpoint /api/student/me returns Class Teacher coordinates."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.st_a1_uid
            sess["role"] = "student"
            sess["email"] = "student.a1@test.edu.in"

        res = self.client.get("/api/student/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        student = data["student"]
        self.assertEqual(student["class_teacher"], "Prof. Alice Archer")
        self.assertEqual(student["assigned_teacher"]["name"], "Prof. Alice Archer")
        self.assertEqual(student["assigned_teacher"]["email"], "teacher.a@test.edu.in")
        
        # Verify no password hash is returned
        self.assertNotIn("password_hash", student)
        self.assertNotIn("password", student)

    def test_csv_upload_auto_associates_with_teacher(self):
        """CSV bulk upload automatically links students to uploading teacher's teacher_id."""
        # Clean up any leftover test rolls from previous runs
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE roll_no IN ('24TESTCSE002', '24TESTCSE003')")
        cursor.execute("DELETE FROM users WHERE email IN ('24testcse002@student.apedu.ac.in', '24testcse003@student.apedu.ac.in')")
        conn.commit()
        conn.close()

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.teacher_a_user_id
            sess["role"] = "teacher"
            sess["email"] = "teacher.a@test.edu.in"
            sess["teacher_id"] = self.teacher_a_id

        csv_content = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Ella Evans,24TESTCSE002,CSE,1st Year,A\n"
            "Frank Foster,24TESTCSE003,CSE,1st Year,A\n"
        )
        
        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "students_sec_a.csv")
        }
        
        res = self.client.post(
            "/api/teacher/students/upload",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 201)
        resp_data = res.get_json()
        self.assertTrue(resp_data["success"], f"Upload failed: {resp_data}")
        self.assertEqual(resp_data["imported_rows"], 2, f"Expected 2 imported rows, got: {resp_data}")

        # Verify in DB that these students have teacher_id set to Teacher A
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT teacher_id, section, branch, year FROM students WHERE roll_no = '24TESTCSE002'")
        st_row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(st_row)
        self.assertEqual(st_row["teacher_id"], self.teacher_a_id)
        self.assertEqual(st_row["section"], "A")

if __name__ == "__main__":
    unittest.main()
