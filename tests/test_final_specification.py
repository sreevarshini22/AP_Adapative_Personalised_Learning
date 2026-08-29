"""
Comprehensive Final Specification Automated Test Suite
AP Quantum Adaptive Learning Platform
"""

import io
import json
import unittest
from werkzeug.security import check_password_hash

from backend.app import create_app
from backend.database import init_db, get_db_connection
from data.seed_academic_data import seed_academic_curriculum
from ml.predict import predict_student_risk
from ml.classical_model import ClassicalRiskClassifier


class TestFinalPlatformSpecification(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_academic_curriculum()

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self._cleanup_test_data()

    def tearDown(self):
        self._cleanup_test_data()

    def _cleanup_test_data(self):
        conn = get_db_connection()
        c = conn.cursor()
        test_emails = [
            "final.student@apedu.ac.in",
            "csv.student1@apedu.ac.in",
            "csv.student2@apedu.ac.in",
            "divya.ai@apedu.ac.in",
            "fresh.mech@apedu.ac.in"
        ]
        test_rolls = ["23CSE999", "23AI888", "23ECE777", "23ME666"]
        for email in test_emails:
            c.execute("DELETE FROM students WHERE LOWER(email) = ?", (email,))
            c.execute("DELETE FROM users WHERE LOWER(email) = ?", (email,))
        for roll in test_rolls:
            c.execute("DELETE FROM students WHERE UPPER(roll_no) = ?", (roll,))
        conn.commit()
        conn.close()

    # ================= 1. ENTRYPOINT & LOGIN =================
    def test_01_entrypoint_routes_directly_to_login(self):
        """Test 1: Entrypoint / and /login serve login.html directly (No home page)."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"STUDENT LOGIN", res.data)
        self.assertIn(b"TEACHER LOGIN", res.data)

        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"AP QUANTUM ADAPTIVE LEARNING PLATFORM", res_login.data)

    def test_02_database_authentication_and_role_isolation(self):
        """Test 2: Real SQLite DB auth with password hashing & role enforcement."""
        # 1. Student login succeeds
        res_stu = self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        self.assertEqual(res_stu.status_code, 200)
        data_stu = res_stu.get_json()
        self.assertTrue(data_stu["success"])
        self.assertEqual(data_stu["user"]["role"], "student")
        self.client.post("/api/logout")

        # 2. Teacher login succeeds
        res_tch = self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        self.assertEqual(res_tch.status_code, 200)
        data_tch = res_tch.get_json()
        self.assertTrue(data_tch["success"])
        self.assertEqual(data_tch["user"]["role"], "teacher")
        self.client.post("/api/logout")

        # 3. Student cannot use teacher login endpoint
        res_cross = self.client.post("/api/login/teacher", json={
            "email": "student@example.com",
            "password": "student123"
        })
        self.assertEqual(res_cross.status_code, 401)

    # ================= 2. STUDENT SUBJECT SELECTION =================
    def test_03_student_subject_selection_and_persistence(self):
        """Test 3: Student queries available subjects by Branch+Year+Sem, selects them, and saves to student_subjects."""
        # 1. Log in as student (CSE, 3rd Year, 5th Sem)
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })

        # 2. Get available subjects for student's branch+year+sem
        res_avail = self.client.get("/api/student/subjects/available")
        self.assertEqual(res_avail.status_code, 200)
        data_avail = res_avail.get_json()
        self.assertTrue(data_avail["success"])
        self.assertEqual(data_avail["branch"], "CSE")
        self.assertEqual(data_avail["year"], "3rd Year")
        self.assertEqual(data_avail["semester"], 5)
        self.assertGreaterEqual(len(data_avail["subjects"]), 3)

        available_sub_ids = [s["id"] for s in data_avail["subjects"]]
        select_subset = available_sub_ids[:3]

        # 3. Save selected subjects
        res_sel = self.client.post("/api/student/subjects/select", json={
            "subject_ids": select_subset
        })
        self.assertEqual(res_sel.status_code, 200)
        data_sel = res_sel.get_json()
        self.assertTrue(data_sel["success"])
        self.assertEqual(data_sel["selected_count"], 3)

        # 4. Query student's subjects to verify persistence in student_subjects
        res_my_subs = self.client.get("/api/student/subjects")
        self.assertEqual(res_my_subs.status_code, 200)
        data_my_subs = res_my_subs.get_json()
        self.assertEqual(data_my_subs["total_subjects"], 3)

    def test_04_prevent_cross_branch_subject_selection(self):
        """Test 4: Backend rejects subject selection belonging to another Branch/Year/Sem."""
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })

        # Query a Civil Engineering subject ID from DB
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM subjects WHERE branch = 'Civil Engineering' LIMIT 1")
        civil_row = c.fetchone()
        conn.close()

        if civil_row:
            res_invalid = self.client.post("/api/student/subjects/select", json={
                "subject_ids": [civil_row["id"]]
            })
            self.assertEqual(res_invalid.status_code, 400)
            data_invalid = res_invalid.get_json()
            self.assertFalse(data_invalid["success"])

    # ================= 3. ASSIGNMENTS & MESSAGING =================
    def test_05_coursework_assignment_workflow(self):
        """Test 5: Students view assignments for their subjects and submit coursework answers."""
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })

        # 1. Fetch student assignments
        res_asg = self.client.get("/api/student/assignments")
        self.assertEqual(res_asg.status_code, 200)
        data_asg = res_asg.get_json()
        self.assertTrue(data_asg["success"])
        self.assertGreaterEqual(len(data_asg["assignments"]), 1)

        target_assignment = data_asg["assignments"][0]
        asg_id = target_assignment["id"]

        # 2. Submit coursework solution
        res_sub = self.client.post(f"/api/student/assignments/{asg_id}/submit", json={
            "submission_text": "Implemented AVL Tree balancing algorithm with rotations in Python."
        })
        self.assertEqual(res_sub.status_code, 200)
        data_sub = res_sub.get_json()
        self.assertTrue(data_sub["success"])

        # 3. Verify in database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT status, score FROM assignment_submissions WHERE assignment_id = ?", (asg_id,))
        sub_row = c.fetchone()
        self.assertIsNotNone(sub_row)
        self.assertEqual(sub_row["status"], "Submitted")
        conn.close()

    def test_06_student_teacher_messaging_thread(self):
        """Test 6: Student messages subject teacher and teacher can reply."""
        # 1. Student sends message for their 5th semester subject
        self.client.post("/api/login/student", json={
            "email": "student@example.com",
            "password": "student123"
        })
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM subjects WHERE subject_code = 'CS301'")
        sub_row = c.fetchone()
        sub_id = sub_row["id"] if sub_row else 1
        
        c.execute("SELECT id FROM students WHERE email = 'student@example.com'")
        student_id = c.fetchone()["id"]
        conn.close()

        res_msg = self.client.post("/api/student/messages", json={
            "subject_id": sub_id,
            "message": "Professor, could you clarify the time complexity of QuickSort average case?"
        })
        self.assertEqual(res_msg.status_code, 201)
        data_msg = res_msg.get_json()
        conv_id = data_msg["conversation_id"]
        self.client.post("/api/logout")

        # 2. Teacher views messages
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })
        res_tch_msgs = self.client.get("/api/teacher/messages")
        self.assertEqual(res_tch_msgs.status_code, 200)

        # 3. Teacher replies
        res_reply = self.client.post("/api/teacher/messages", json={
            "conversation_id": conv_id,
            "student_id": student_id,
            "subject_id": sub_id,
            "message": "QuickSort operates in O(N log N) on average when using randomized pivots."
        })
        self.assertEqual(res_reply.status_code, 201)

    # ================= 4. TEACHER CSV BULK UPLOAD =================
    def test_07_teacher_bulk_csv_upload_and_student_login(self):
        """Test 7: Bulk CSV upload with password hashing & immediate student login."""
        self.client.post("/api/login/teacher", json={
            "email": "teacher@example.com",
            "password": "teacher123"
        })

        csv_content = (
            "student_name,roll_no,email,password,year,branch,section,semester\n"
            "Final Spec Student,23CSE999,final.student@apedu.ac.in,SpecPass999,2nd Year,CSE,A,3\n"
        )
        data = {
            "file": (io.BytesIO(csv_content.encode("utf-8")), "spec_upload.csv")
        }

        # 1. Preview
        res_prev = self.client.post(
            "/api/teacher/students/upload/preview",
            data={"file": (io.BytesIO(csv_content.encode("utf-8")), "spec_upload.csv")},
            content_type="multipart/form-data"
        )
        self.assertEqual(res_prev.status_code, 200)
        self.assertEqual(res_prev.get_json()["valid_rows"], 1)

        # 2. Bulk Upload
        res_up = self.client.post(
            "/api/teacher/students/upload",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res_up.status_code, 201)
        self.assertEqual(res_up.get_json()["imported_rows"], 1)
        self.client.post("/api/logout")

        # 3. Verify password is NOT plaintext in SQLite
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE email = 'final.student@apedu.ac.in'")
        user_row = c.fetchone()
        self.assertIsNotNone(user_row)
        self.assertNotEqual(user_row["password_hash"], "SpecPass999")
        self.assertTrue(check_password_hash(user_row["password_hash"], "SpecPass999"))
        conn.close()

        # 4. Student can log in immediately
        res_stu_login = self.client.post("/api/login/student", json={
            "email": "final.student@apedu.ac.in",
            "password": "SpecPass999"
        })
        self.assertEqual(res_stu_login.status_code, 200)
        self.assertTrue(res_stu_login.get_json()["success"])

    # ================= 5. CLASSICAL ML VERIFICATION =================
    def test_08_classical_ml_pipeline_and_modular_inference(self):
        """Test 8: Verify Classical ML model artifacts, metrics, and live inference."""
        test_student_profile = {
            "attendance": 55.0,
            "mathematics_score": 48.0,
            "physics_score": 52.0,
            "programming_score": 45.0,
            "data_structures_score": 40.0,
            "database_score": 50.0,
            "communication_score": 60.0,
            "assignment_score": 45.0,
            "quiz_score": 42.0,
            "exam_score": 46.0,
            "study_hours": 4.0,
            "learning_activity": 35.0,
            "previous_performance": 52.0,
            "overall_progress": 32.0
        }

        # 1. Test live inference
        pred = predict_student_risk(test_student_profile)
        self.assertIn("risk_level", pred)
        self.assertIn(pred["risk_level"], ["High Risk", "Medium Risk", "Low Risk"])
        self.assertIn("probabilities", pred)
        self.assertIn("High Risk", pred["probabilities"])
        self.assertGreaterEqual(pred["risk_score"], 0.0)
        self.assertLessEqual(pred["risk_score"], 100.0)

        # 2. Test modular ClassicalRiskClassifier class
        clf = ClassicalRiskClassifier.load("models/learning_risk_model.pkl", "models/preprocessing_pipeline.pkl")
        clf_pred = clf.predict_single(test_student_profile)
        self.assertEqual(clf_pred["risk_level"], pred["risk_level"])


if __name__ == "__main__":
    unittest.main()
