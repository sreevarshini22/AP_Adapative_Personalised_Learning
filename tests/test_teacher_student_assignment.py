"""
Comprehensive Verification Test Suite for Teacher-Student Assignment,
Multi-Class Cohort Isolation, CSV Upload Binding, and API Authorization Security.
"""

import os
import io
import sys
import unittest
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app
from backend.database import get_db_connection, init_db
from data.seed_academic_data import seed_academic_curriculum


class TestTeacherStudentAssignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_academic_curriculum()
        cls.client = app.test_client()

    def cleanup_temp_data(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM student_subjects WHERE student_id IN (SELECT id FROM students WHERE roll_no IN ('21AUAIML099', '21AUAIML100', '21AUAIML105'))")
        cursor.execute("DELETE FROM students WHERE roll_no IN ('21AUAIML099', '21AUAIML100', '21AUAIML105')")
        cursor.execute("DELETE FROM users WHERE email IN ('21auaiml099@student.apedu.ac.in', '21auaiml100@student.apedu.ac.in', 'kiran.kumar@student.au.edu.in')")
        conn.commit()
        conn.close()

    def setUp(self):
        self.cleanup_temp_data()

    def tearDown(self):
        self.cleanup_temp_data()

    def login(self, email, password):
        res = self.client.post(
            "/api/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json"
        )
        data = res.get_json()
        self.assertEqual(res.status_code, 200, f"Login failed for {email}: {data}")
        return data

    def logout(self):
        self.client.post("/api/logout")

    def test_01_teacher_a_sees_only_assigned_students(self):
        """Teacher A (AU AIML 3rd Year Sec A) must see Student 1 and NOT Student 2."""
        self.login("prof.murthy@au.edu.in", "ProfMurthy@2024")
        res = self.client.get("/api/teacher/students")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        
        emails = [s["email"].lower() for s in data["students"]]
        rolls = [s["roll_no"] for s in data["students"]]
        
        self.assertIn("student.au@au.edu.in", emails, "Teacher A must see Student 1 (Aarav Sharma).")
        self.assertNotIn("student.jntuk@jntuk.edu.in", emails, "Teacher A must NOT see Student 2 (Bhavya Reddy).")
        self.logout()

    def test_02_teacher_b_sees_only_assigned_students(self):
        """Teacher B (JNTUK ECE 3rd Year Sec A) must see Student 2 and NOT Student 1."""
        self.login("dr.venkatesh@jntuk.edu.in", "DrVenkatesh@2024")
        res = self.client.get("/api/teacher/students")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        
        emails = [s["email"].lower() for s in data["students"]]
        self.assertIn("student.jntuk@jntuk.edu.in", emails, "Teacher B must see Student 2 (Bhavya Reddy).")
        self.assertNotIn("student.au@au.edu.in", emails, "Teacher B must NOT see Student 1 (Aarav Sharma).")
        self.logout()

    def test_03_student_1_profile_identifies_teacher_and_university(self):
        """Student 1 profile must return assigned Teacher A, University AU, Branch AIML, Year 3rd Year, Sec A."""
        self.login("student.au@au.edu.in", "StudentAU@2024")
        res = self.client.get("/api/student/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        st = data["student"]
        
        self.assertEqual(st["branch"], "AIML")
        self.assertEqual(st["year"], "3rd Year")
        self.assertEqual(st["section"], "A")
        self.assertIn("Andhra University", st.get("university", ""))
        self.assertIsNotNone(st.get("assigned_teacher"), "Student profile must have assigned_teacher")
        self.assertEqual(st["assigned_teacher"]["name"], "Dr. K. Srinivas Murthy")
        self.logout()

    def test_04_student_2_profile_identifies_teacher_and_university(self):
        """Student 2 profile must return assigned Teacher B, University JNTUK, Branch ECE, Year 3rd Year, Sec A."""
        self.login("student.jntuk@jntuk.edu.in", "StudentJNTUK@2024")
        res = self.client.get("/api/student/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        st = data["student"]
        
        self.assertEqual(st["branch"], "ECE")
        self.assertEqual(st["year"], "3rd Year")
        self.assertEqual(st["section"], "A")
        self.assertIn("JNTUK", st.get("university", ""))
        self.assertIsNotNone(st.get("assigned_teacher"), "Student profile must have assigned_teacher")
        self.assertEqual(st["assigned_teacher"]["name"], "Dr. P. Venkatesh")
        self.logout()

    def test_05_messaging_reaches_correct_teacher_and_blocks_unassigned(self):
        """Student 1 messaging sends only to Teacher A and rejects unauthorized messaging to Teacher B."""
        # Get Teacher A and Teacher B IDs
        conn = get_db_connection()
        cursor = conn.cursor()
        t_a_id = cursor.execute("SELECT id FROM teachers WHERE email = 'prof.murthy@au.edu.in'").fetchone()[0]
        t_b_id = cursor.execute("SELECT id FROM teachers WHERE email = 'dr.venkatesh@jntuk.edu.in'").fetchone()[0]
        conn.close()

        # Login Student 1
        self.login("student.au@au.edu.in", "StudentAU@2024")
        
        # 1. Student 1 messages Teacher A (authorized)
        msg_payload = {
            "teacher_id": t_a_id,
            "message": "Hello Dr. Murthy, I have a doubt regarding Decision Trees in Unit 1."
        }
        res = self.client.post("/api/student/messages", data=json.dumps(msg_payload), content_type="application/json")
        self.assertEqual(res.status_code, 201)
        
        # 2. Student 1 attempts to message Teacher B (unauthorized - cross institution/class)
        msg_payload_unauth = {
            "teacher_id": t_b_id,
            "message": "Hello Dr. Venkatesh, this should be blocked."
        }
        res_unauth = self.client.post("/api/student/messages", data=json.dumps(msg_payload_unauth), content_type="application/json")
        self.assertEqual(res_unauth.status_code, 403, "Student must not be allowed to message unassigned faculty.")
        self.logout()

        # 3. Check Teacher A's inbox
        self.login("prof.murthy@au.edu.in", "ProfMurthy@2024")
        res = self.client.get("/api/teacher/messages")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(any("Decision Trees" in c["last_message"] for c in data["conversations"]))
        self.logout()

        # 4. Check Teacher B's inbox does NOT contain Student 1's message
        self.login("dr.venkatesh@jntuk.edu.in", "DrVenkatesh@2024")
        res = self.client.get("/api/teacher/messages")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(any("Decision Trees" in c["last_message"] for c in data["conversations"]))
        self.logout()

    def test_06_cross_teacher_data_isolation_and_idor_protection(self):
        """Teacher A cannot view details, predictions, or log interventions on Teacher B's students."""
        conn = get_db_connection()
        cursor = conn.cursor()
        st_b_id = cursor.execute("SELECT id FROM students WHERE email = 'student.jntuk@jntuk.edu.in'").fetchone()[0]
        conn.close()

        self.login("prof.murthy@au.edu.in", "ProfMurthy@2024")
        
        # 1. Direct detail access attempt (IDOR)
        res = self.client.get(f"/api/teacher/student/{st_b_id}")
        self.assertEqual(res.status_code, 403, "Teacher A must be blocked with HTTP 403 from viewing Student B.")

        # 2. Prediction detail access attempt
        res = self.client.get(f"/api/teacher/student/{st_b_id}/prediction")
        self.assertEqual(res.status_code, 403, "Teacher A must be blocked with HTTP 403 from prediction.")

        # 3. Unauthorized intervention logging attempt
        interv_payload = {
            "title": "Unauthorized Remedial",
            "description": "Should fail",
            "risk_level": "High Risk"
        }
        res = self.client.post(f"/api/teacher/student/{st_b_id}/intervention", data=json.dumps(interv_payload), content_type="application/json")
        self.assertEqual(res.status_code, 403, "Teacher A must be blocked with HTTP 403 from logging intervention.")

        # 4. Unauthorized message sending to foreign student
        msg_payload = {
            "student_id": st_b_id,
            "message": "Unauthorized message"
        }
        res = self.client.post("/api/teacher/messages", data=json.dumps(msg_payload), content_type="application/json")
        self.assertEqual(res.status_code, 403, "Teacher A must be blocked from messaging foreign student.")
        self.logout()

    def test_07_csv_bulk_upload_assigns_to_uploading_teacher(self):
        """CSV uploaded students by Teacher A must belong to Teacher A and remain isolated from Teacher B."""
        self.login("prof.murthy@au.edu.in", "ProfMurthy@2024")
        
        csv_data = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Chaitanya Varma,21AUAIML099,AIML,3rd Year,A\n"
            "Divya Krishna,21AUAIML100,AIML,3rd Year,A\n"
        )
        
        data = {
            "file": (io.BytesIO(csv_data.encode("utf-8")), "aiml_students.csv")
        }
        
        res = self.client.post("/api/teacher/students/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        upload_resp = res.get_json()
        self.assertEqual(upload_resp["imported_rows"], 2)
        
        # Verify Teacher A can now see the imported students
        res_list = self.client.get("/api/teacher/students")
        rolls = [s["roll_no"] for s in res_list.get_json()["students"]]
        self.assertIn("21AUAIML099", rolls)
        self.assertIn("21AUAIML100", rolls)
        self.logout()

        # Verify Teacher B CANNOT see these newly uploaded students
        self.login("dr.venkatesh@jntuk.edu.in", "DrVenkatesh@2024")
        res_list_b = self.client.get("/api/teacher/students")
        rolls_b = [s["roll_no"] for s in res_list_b.get_json()["students"]]
        self.assertNotIn("21AUAIML099", rolls_b)
        self.assertNotIn("21AUAIML100", rolls_b)
        self.logout()

    def test_08_analytics_and_cohort_risk_isolation(self):
        """Teacher A analytics must aggregate strictly across Teacher A's students."""
        self.login("prof.murthy@au.edu.in", "ProfMurthy@2024")
        res = self.client.get("/api/teacher/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        # Teacher A has assigned students in AU AIML 3rd Year Sec A
        self.assertGreaterEqual(data["total_students"], 1)
        self.assertIn("risk_distribution_counts", data)
        self.logout()

        self.login("dr.venkatesh@jntuk.edu.in", "DrVenkatesh@2024")
        res_b = self.client.get("/api/teacher/analytics")
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.get_json()
        self.assertTrue(data_b["success"])
        self.assertEqual(data_b["total_students"], 1)
        self.logout()

    def test_09_manual_student_creation_assigns_teacher_cohort(self):
        """Manual student creation by Teacher A sets institution and auto-enrolls into teacher's subjects."""
        self.login("prof.murthy@au.edu.in", "ProfMurthy@2024")
        st_data = {
            "full_name": "Kiran Kumar",
            "roll_no": "21AUAIML105",
            "email": "kiran.kumar@student.au.edu.in",
            "password": "Password@123",
            "branch": "AIML",
            "year": "3rd Year",
            "section": "A",
            "semester": 1
        }
        res = self.client.post("/api/teacher/student", data=json.dumps(st_data), content_type="application/json")
        self.assertEqual(res.status_code, 201)
        new_st_id = res.get_json()["student_id"]

        # Verify Teacher A sees this student
        res_list = self.client.get("/api/teacher/students")
        rolls = [s["roll_no"] for s in res_list.get_json()["students"]]
        self.assertIn("21AUAIML105", rolls)
        self.logout()

        # Verify Teacher B does NOT see this student
        self.login("dr.venkatesh@jntuk.edu.in", "DrVenkatesh@2024")
        res_list_b = self.client.get("/api/teacher/students")
        rolls_b = [s["roll_no"] for s in res_list_b.get_json()["students"]]
        self.assertNotIn("21AUAIML105", rolls_b)
        self.logout()

        # Clean up
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE id = ?", (new_st_id,))
        cursor.execute("DELETE FROM users WHERE email = 'kiran.kumar@student.au.edu.in'")
        conn.commit()
        conn.close()

    def test_10_database_relationship_and_schema_integrity(self):
        """Verify database relationship integrity across teacher_subjects and student cohorts."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify teachers have valid institution and department
        cursor.execute("SELECT id, full_name, branch, year, section, institution_id FROM teachers WHERE email = 'prof.murthy@au.edu.in'")
        t_row = cursor.fetchone()
        self.assertIsNotNone(t_row)
        self.assertEqual(t_row["branch"], "AIML")
        self.assertEqual(t_row["section"], "A")
        
        # Verify teacher_subjects has active mapping
        cursor.execute("SELECT COUNT(*) FROM teacher_subjects WHERE teacher_id = ?", (t_row["id"],))
        sub_count = cursor.fetchone()[0]
        self.assertGreaterEqual(sub_count, 1)
        
        conn.close()


if __name__ == "__main__":
    unittest.main()
