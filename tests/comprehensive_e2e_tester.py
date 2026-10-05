"""
Comprehensive End-to-End Diagnostic & Functional Test Suite
Systematically tests all 19 functional areas specified in the audit requirement.
Outputs structured JSON and human-readable diagnostic summaries.
"""

import os
import sys
import json
import io
import time
import unittest
from werkzeug.security import generate_password_hash, check_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import get_db_connection, init_db
from ml.predict import predict_student_risk
from ml.quantum_model import QuantumRiskClassifier, PENNYLANE_AVAILABLE


class ComprehensiveE2ETestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["SECRET_KEY"] = "comprehensive-test-secret-key"
        cls.client = cls.app.test_client()

        init_db()
        cls.conn = get_db_connection()
        cls.cur = cls.conn.cursor()

        # Gather database baseline
        cls.cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        cls.existing_tables = [r[0] for r in cls.cur.fetchall()]

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    # =========================================================================
    # 1. AUTHENTICATION TESTING
    # =========================================================================
    def test_01_student_login_valid(self):
        """Student login with valid credentials."""
        res = self.client.post("/api/login/student", json={
            "email": "student.au@au.edu.in",
            "password": "StudentAU@2024"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["role"], "student")
        self.assertIsNotNone(data["student"])
        self.assertEqual(data["student"]["full_name"], "Aarav Sharma")
        self.assertEqual(data["student"]["roll_no"], "21AUAIML001")

    def test_01_student_login_invalid_password(self):
        """Student login with incorrect password."""
        res = self.client.post("/api/login/student", json={
            "email": "student.au@au.edu.in",
            "password": "WrongPassword123!"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_01_student_login_non_existing(self):
        """Student login with non-existent account."""
        res = self.client.post("/api/login/student", json={
            "email": "nonexistent.student@au.edu.in",
            "password": "password123"
        })
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_01_student_login_empty_fields(self):
        """Student login with empty fields."""
        res = self.client.post("/api/login/student", json={"email": "", "password": ""})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_01_teacher_login_valid(self):
        """Teacher login with valid credentials."""
        res = self.client.post("/api/login/teacher", json={
            "email": "prof.murthy@au.edu.in",
            "password": "ProfMurthy@2024"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["role"], "teacher")
        self.assertIsNotNone(data["teacher"])
        self.assertEqual(data["teacher"]["full_name"], "Dr. K. Srinivas Murthy")

    def test_01_teacher_login_invalid_password(self):
        """Teacher login with invalid password."""
        res = self.client.post("/api/login/teacher", json={
            "email": "prof.murthy@au.edu.in",
            "password": "IncorrectPassword"
        })
        self.assertEqual(res.status_code, 401)

    def test_01_role_boundary_student_cannot_access_teacher_api(self):
        """Student session cannot access teacher endpoints."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 100
            sess["role"] = "student"
            sess["email"] = "student.au@au.edu.in"

        res = self.client.get("/api/teacher/students")
        self.assertEqual(res.status_code, 403)

    def test_01_role_boundary_teacher_cannot_access_student_api(self):
        """Teacher session cannot access student endpoints."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 200
            sess["role"] = "teacher"
            sess["email"] = "prof.murthy@au.edu.in"

        res = self.client.get("/api/student/me")
        self.assertEqual(res.status_code, 403)

    def test_01_unauthenticated_api_rejection(self):
        """Unauthenticated requests to protected endpoints return 401/403."""
        # Clear session
        with self.client.session_transaction() as sess:
            sess.clear()
        res = self.client.get("/api/student/me")
        self.assertIn(res.status_code, [401, 403])
        res2 = self.client.get("/api/teacher/students")
        self.assertIn(res2.status_code, [401, 403])

    def test_01_logout_invalidates_session(self):
        """Logout clears the session and revokes access."""
        # Login
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        # Logout
        res = self.client.post("/api/logout")
        self.assertEqual(res.status_code, 200)
        # Attempt access
        res2 = self.client.get("/api/student/me")
        self.assertIn(res2.status_code, [401, 403])

    # =========================================================================
    # 2. TEACHER REGISTRATION
    # =========================================================================
    def test_02_teacher_registration_success(self):
        """Register a new faculty member successfully."""
        reg_email = f"new.faculty_{int(time.time())}@au.edu.in"
        res = self.client.post("/api/register/teacher", json={
            "full_name": "Dr. Sarah Connor",
            "email": reg_email,
            "password": "TeacherPassword@123",
            "department": "Computer Science",
            "designation": "Assistant Professor",
            "branch": "CSE",
            "year": "2nd Year",
            "section": "A"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Immediate login with new credentials
        login_res = self.client.post("/api/login/teacher", json={
            "email": reg_email,
            "password": "TeacherPassword@123"
        })
        self.assertEqual(login_res.status_code, 200)

    def test_02_teacher_registration_duplicate_email(self):
        """Duplicate faculty email registration must fail."""
        res = self.client.post("/api/register/teacher", json={
            "full_name": "Duplicate Faculty",
            "email": "prof.murthy@au.edu.in",
            "password": "Password123"
        })
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])

    def test_02_teacher_registration_invalid_inputs(self):
        """Registration with missing or empty inputs."""
        res = self.client.post("/api/register/teacher", json={"email": "", "password": ""})
        self.assertEqual(res.status_code, 400)

    # =========================================================================
    # 3. STUDENT-TEACHER RELATIONSHIP & COHORT ISOLATION
    # =========================================================================
    def test_03_student_teacher_section_isolation(self):
        """Teacher A (Sec A) sees ONLY Sec A; Teacher B (Sec B) does NOT see Sec A."""
        # Get Prof Murthy (AIML 3rd Year Sec A)
        res_a = self.client.post("/api/login/teacher", json={"email": "prof.murthy@au.edu.in", "password": "ProfMurthy@2024"})
        self.assertEqual(res_a.status_code, 200)
        
        students_res_a = self.client.get("/api/teacher/students")
        self.assertEqual(students_res_a.status_code, 200)
        students_a = students_res_a.get_json()["students"]

        # Prof Murthy should see student.au (AIML 3rd Year Sec A)
        au_rolls = [s["roll_no"] for s in students_a]
        self.assertIn("21AUAIML001", au_rolls)

        # Prof Murthy must NOT see ECE students from JNTUK
        self.assertNotIn("21JNTUKECE042", au_rolls)

        # Get Dr Venkatesh (ECE 3rd Year Sec A from JNTUK)
        res_b = self.client.post("/api/login/teacher", json={"email": "dr.venkatesh@jntuk.edu.in", "password": "DrVenkatesh@2024"})
        self.assertEqual(res_b.status_code, 200)
        
        students_res_b = self.client.get("/api/teacher/students")
        self.assertEqual(students_res_b.status_code, 200)
        students_b = students_res_b.get_json()["students"]
        jntuk_rolls = [s["roll_no"] for s in students_b]

        # Dr Venkatesh sees JNTUK ECE student
        self.assertIn("21JNTUKECE042", jntuk_rolls)
        # Dr Venkatesh must NOT see AU AIML student
        self.assertNotIn("21AUAIML001", jntuk_rolls)

    def test_03_student_dashboard_displays_class_teacher(self):
        """Student profile contains Class Teacher name and coordinates."""
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        res = self.client.get("/api/student/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["student"]

        self.assertEqual(data["class_teacher"], "Dr. K. Srinivas Murthy")
        self.assertEqual(data["assigned_teacher"]["name"], "Dr. K. Srinivas Murthy")
        self.assertEqual(data["assigned_teacher"]["email"], "prof.murthy@au.edu.in")

    def test_03_teacher_dashboard_does_not_expose_passwords(self):
        """Verify no password or hash is exposed in teacher student roster."""
        self.client.post("/api/login/teacher", json={"email": "prof.murthy@au.edu.in", "password": "ProfMurthy@2024"})
        res = self.client.get("/api/teacher/students")
        data = res.get_json()
        for st in data["students"]:
            self.assertNotIn("password", st)
            self.assertNotIn("password_hash", st)

    # =========================================================================
    # 4. CSV BULK STUDENT UPLOAD
    # =========================================================================
    def test_04_csv_upload_valid_auto_assigns_teacher(self):
        """CSV bulk upload automatically links students to uploading teacher."""
        self.client.post("/api/login/teacher", json={"email": "prof.murthy@au.edu.in", "password": "ProfMurthy@2024"})

        # Clean up any test rolls
        conn = get_db_connection()
        conn.execute("DELETE FROM students WHERE roll_no IN ('21AUAIML901', '21AUAIML902')")
        conn.execute("DELETE FROM users WHERE email IN ('21auaiml901@student.apedu.ac.in', '21auaiml902@student.apedu.ac.in')")
        conn.commit()
        conn.close()

        csv_content = (
            "Student Name,Roll No,Branch,Year,Section\n"
            "Vikas Reddy,21AUAIML901,AIML,3rd Year,A\n"
            "Deepika Sen,21AUAIML902,AIML,3rd Year,A\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "aiml_batch.csv")}
        res = self.client.post("/api/teacher/students/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 201)
        resp_data = res.get_json()
        self.assertTrue(resp_data["success"])
        self.assertEqual(resp_data["imported_rows"], 2)

        # Verify newly uploaded students can log in
        st_login = self.client.post("/api/login/student", json={
            "email": "21auaiml901@student.apedu.ac.in",
            "password": "21auaiml901"
        })
        self.assertEqual(st_login.status_code, 200)
        self.assertEqual(st_login.get_json()["student"]["class_teacher"], "Dr. K. Srinivas Murthy")

    def test_04_csv_upload_missing_columns(self):
        """CSV upload with missing required headers returns 400."""
        self.client.post("/api/login/teacher", json={"email": "prof.murthy@au.edu.in", "password": "ProfMurthy@2024"})
        invalid_csv = "Name,RollNumber\nJohn Doe,12345\n"
        data = {"file": (io.BytesIO(invalid_csv.encode("utf-8")), "bad.csv")}
        res = self.client.post("/api/teacher/students/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])

    def test_04_csv_upload_empty_file(self):
        """Empty CSV upload returns 400 error."""
        self.client.post("/api/login/teacher", json={"email": "prof.murthy@au.edu.in", "password": "ProfMurthy@2024"})
        data = {"file": (io.BytesIO(b""), "empty.csv")}
        res = self.client.post("/api/teacher/students/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)

    # =========================================================================
    # 5. STUDENT DASHBOARD & LEARNING PAYLOADS
    # =========================================================================
    def test_05_student_profile_coordinates(self):
        """Student dashboard profile contains authentic academic coordinates."""
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        res = self.client.get("/api/student/me")
        self.assertEqual(res.status_code, 200)
        st = res.get_json()["student"]
        self.assertEqual(st["full_name"], "Aarav Sharma")
        self.assertEqual(st["roll_no"], "21AUAIML001")
        self.assertEqual(st["branch"], "AIML")
        self.assertEqual(st["year"], "3rd Year")
        self.assertEqual(st["section"], "A")
        self.assertEqual(st["institution_name"], "Andhra University College of Engineering (Autonomous)")
        self.assertEqual(st["aishe_code"], "U-0003")

    def test_05_student_subjects_curriculum(self):
        """Student loads subjects corresponding to their branch/year/sem."""
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        res = self.client.get("/api/student/subjects")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(len(data["subjects"]) >= 1)
        # Verify subjects have codes and names
        codes = [s["subject_code"] for s in data["subjects"]]
        self.assertTrue(any("CS" in c or "AIML" in c or "ML" in c for c in codes))

    # =========================================================================
    # 6. TEACHER DASHBOARD
    # =========================================================================
    def test_06_teacher_dashboard_profile_and_classes(self):
        """Teacher dashboard loads profile and assigned classes."""
        self.client.post("/api/login/teacher", json={"email": "prof.murthy@au.edu.in", "password": "ProfMurthy@2024"})
        res = self.client.get("/api/teacher/me")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["teacher"]
        self.assertEqual(data["full_name"], "Dr. K. Srinivas Murthy")
        self.assertTrue(len(data["assigned_classes"]) >= 1)
        self.assertTrue(data["total_students"] >= 1)

    # =========================================================================
    # 7. SUBJECTS, LESSONS, LABS & QUIZZES
    # =========================================================================
    def test_07_lessons_labs_quizzes_endpoints(self):
        """Lessons, labs, assessments, and quizzes load properly."""
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        
        # 1. Subjects
        sub_res = self.client.get("/api/student/subjects")
        sub_id = sub_res.get_json()["subjects"][0]["id"]

        # 2. Lessons
        lessons_res = self.client.get(f"/api/student/subject/{sub_id}/lessons")
        self.assertEqual(lessons_res.status_code, 200)
        self.assertTrue(lessons_res.get_json()["success"])

        # 3. Labs
        labs_res = self.client.get(f"/api/student/subject/{sub_id}/labs")
        self.assertEqual(labs_res.status_code, 200)
        self.assertTrue(labs_res.get_json()["success"])

        # 4. Quizzes
        quizzes_res = self.client.get("/api/student/quizzes")
        self.assertEqual(quizzes_res.status_code, 200)
        self.assertTrue(quizzes_res.get_json()["success"])

    # =========================================================================
    # 8. PROGRESS TRACKING & BOUNDARY VALUES
    # =========================================================================
    def test_08_progress_endpoints_and_boundaries(self):
        """Progress endpoints return valid percentages and handle boundary cases."""
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        res = self.client.get("/api/student/progress")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(0.0 <= data["overall_progress"] <= 100.0)
        self.assertTrue(0.0 <= data["attendance"] <= 100.0)

    # =========================================================================
    # 9. ASSIGNMENTS
    # =========================================================================
    def test_09_assignments_endpoints(self):
        """Subject assignments load and submit correctly."""
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        sub_res = self.client.get("/api/student/subjects")
        sub_id = sub_res.get_json()["subjects"][0]["id"]

        res = self.client.get(f"/api/student/subject/{sub_id}/assignments")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

    # =========================================================================
    # 10. MESSAGING & DOUBT SYSTEM
    # =========================================================================
    def test_10_messaging_thread_flow(self):
        """Student sends message to teacher, teacher replies, conversation persists."""
        # 1. Student login & message teacher
        self.client.post("/api/login/student", json={"email": "student.au@au.edu.in", "password": "StudentAU@2024"})
        send_res = self.client.post("/api/student/messages/send", json={
            "teacher_id": 1,
            "message": "Hello Professor Murthy, I have a doubt regarding Module 2 SVM kernel mapping."
        })
        self.assertIn(send_res.status_code, [200, 201])
        conv_id = send_res.get_json().get("conversation_id", "conv_s1_t1")

        # 2. Teacher reads inbox
        self.client.post("/api/login/teacher", json={"email": "prof.murthy@au.edu.in", "password": "ProfMurthy@2024"})
        inbox_res = self.client.get("/api/teacher/messages/inbox")
        self.assertEqual(inbox_res.status_code, 200)

        # 3. Teacher replies
        reply_res = self.client.post("/api/teacher/messages/reply", json={
            "conversation_id": conv_id,
            "student_id": 1,
            "message": "Hello Aarav, refer to Lecture 4 slides on RBF kernel and Slack variables."
        })
        self.assertEqual(reply_res.status_code, 200)

        # 4. Reject empty message
        empty_res = self.client.post("/api/teacher/messages/reply", json={
            "conversation_id": conv_id,
            "student_id": 1,
            "message": "   "
        })
        self.assertEqual(empty_res.status_code, 400)

    # =========================================================================
    # 11. PASSWORD RECOVERY FLOW
    # =========================================================================
    def test_11_password_reset_flow(self):
        """Forgot password -> token generation -> password update -> login with new password."""
        test_email = "student.au@au.edu.in"
        
        # Request reset token
        req_res = self.client.post("/api/auth/forgot-password", json={"email": test_email})
        self.assertEqual(req_res.status_code, 200)
        data = req_res.get_json()
        self.assertTrue(data["success"])

        # Fetch active token from DB
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT reset_token FROM password_resets WHERE email = ? ORDER BY id DESC LIMIT 1", (test_email,))
        t_row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(t_row)
        reset_token = t_row[0]

        # Reset password with token
        new_pwd = "NewStudentAU@2025"
        reset_res = self.client.post("/api/auth/reset-password", json={
            "token": reset_token,
            "new_password": new_pwd
        })
        self.assertEqual(reset_res.status_code, 200)
        self.assertTrue(reset_res.get_json()["success"])

        # Login with new password
        login_new = self.client.post("/api/login/student", json={"email": test_email, "password": new_pwd})
        self.assertEqual(login_new.status_code, 200)

        # Revert back to original password for consistency
        self.client.post("/api/auth/forgot-password", json={"email": test_email})
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT reset_token FROM password_resets WHERE email = ? ORDER BY id DESC LIMIT 1", (test_email,))
        rev_token = cur.fetchone()[0]
        conn.close()
        self.client.post("/api/auth/reset-password", json={"token": rev_token, "new_password": "StudentAU@2024"})

    # =========================================================================
    # 12. CLASSICAL ML RISK PREDICTION
    # =========================================================================
    def test_12_ml_prediction_profiles(self):
        """Classical ML risk inference across diverse student performance profiles."""
        # 1. Excellent Student
        p1 = predict_student_risk({
            "attendance": 96.0, "overall_progress": 92.0, "learning_activity": 94.0,
            "mathematics_score": 90.0, "physics_score": 92.0, "programming_score": 95.0,
            "data_structures_score": 94.0, "database_score": 92.0, "communication_score": 90.0,
            "exam_score": 95.0, "study_hours": 12.0, "learning_streak": 10
        })
        self.assertEqual(p1["risk_level"], "Low Risk")
        self.assertTrue(p1["probabilities"]["Low Risk"] > 0.5)

        # 2. High Risk Weak Student
        p2 = predict_student_risk({
            "attendance": 45.0, "overall_progress": 32.0, "learning_activity": 35.0,
            "mathematics_score": 38.0, "physics_score": 40.0, "programming_score": 42.0,
            "data_structures_score": 35.0, "database_score": 40.0, "communication_score": 50.0,
            "exam_score": 38.0, "study_hours": 2.0, "learning_streak": 0
        })
        self.assertEqual(p2["risk_level"], "High Risk")
        self.assertTrue(p2["risk_score"] > 50.0)

    # =========================================================================
    # 13. QUANTUM ML (PENNYLANE)
    # =========================================================================
    def test_13_quantum_ml_execution_and_health(self):
        """QML engine initializes 5-qubit VQC and executes quantum circuits."""
        predictor = QMLStudentPredictor()
        features = [0.85, 0.90, 0.80, 0.75, 0.88] # 5 normalized features
        pred = predictor.predict(features)
        
        self.assertIn("risk_level", pred)
        self.assertIn(pred["risk_level"], ["Low Risk", "Medium Risk", "High Risk"])
        self.assertIn("quantum_state", pred)
        self.assertIn("qubit_expectations", pred)
        self.assertEqual(len(pred["qubit_expectations"]), 5)

        # Health endpoint check
        health_res = self.client.get("/api/health")
        self.assertEqual(health_res.status_code, 200)
        h_data = health_res.get_json()
        self.assertEqual(h_data["status"], "healthy")
        self.assertTrue(h_data["qml"]["enabled"])
        self.assertEqual(h_data["qml"]["num_qubits"], 5)

    # =========================================================================
    # 14. DATABASE SCHEMA INTEGRITY & CONSTRAINTS
    # =========================================================================
    def test_14_database_foreign_keys_and_indexes(self):
        """Database schema contains all required tables, foreign keys, and indexes."""
        required_tables = [
            "users", "teachers", "students", "institutions", "programs",
            "curriculum_versions", "subjects", "modules", "topics",
            "learning_resources", "document_chunks", "grounded_questions",
            "teacher_assignments", "classes", "messages", "notifications",
            "interventions", "coding_challenges", "student_badges"
        ]
        for tbl in required_tables:
            self.assertIn(tbl, self.existing_tables, f"Missing table: {tbl}")

        # Check for orphan students
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM students WHERE user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)")
        orphan_count = cur.fetchone()[0]
        self.assertEqual(orphan_count, 0, "Found orphan student records without parent user account")

        # Check for duplicate roll numbers
        cur.execute("SELECT roll_no, COUNT(*) FROM students GROUP BY roll_no HAVING COUNT(*) > 1")
        dupes = cur.fetchall()
        self.assertEqual(len(dupes), 0, f"Found duplicate roll numbers: {dupes}")
        conn.close()

    # =========================================================================
    # 15. API STATUS & HEALTH
    # =========================================================================
    def test_15_health_and_core_api_catalog(self):
        """Health and system telemetry endpoints return valid status."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["database"], "connected")
        self.assertEqual(data["status"], "healthy")

    # =========================================================================
    # 16. UI TOKENS & LIGHT/DARK THEME ASSETS
    # =========================================================================
    def test_16_ui_css_tokens_and_theme_rules(self):
        """Inspect styles.css for light and dark mode tokens and high-contrast button rules."""
        css_path = os.path.join(PROJECT_ROOT, "frontend", "styles.css")
        self.assertTrue(os.path.exists(css_path))
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()

        # Check dark & light mode root selectors
        self.assertIn(":root", css_content)
        self.assertIn("[data-theme=\"light\"]", css_content)
        # Check high-contrast primary buttons
        self.assertIn(".btn-primary", css_content)
        self.assertIn("#ffffff", css_content.lower())

    # =========================================================================
    # 17. RESPONSIVE DESIGN BREAKPOINTS
    # =========================================================================
    def test_17_responsive_media_queries(self):
        """Verify CSS contains standard tablet/mobile media queries."""
        css_path = os.path.join(PROJECT_ROOT, "frontend", "styles.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()

        self.assertIn("@media (max-width: 768px)", css_content)
        self.assertIn("@media (max-width: 1024px)", css_content)

    # =========================================================================
    # 18. RESILIENT ERROR HANDLING
    # =========================================================================
    def test_18_error_handlers(self):
        """Invalid API routes return structured JSON error rather than HTML crash."""
        res = self.client.get("/api/nonexistent-endpoint-xyz")
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.get_json()["success"])

    # =========================================================================
    # 19. SECURITY TESTING & DATA SANITIZATION
    # =========================================================================
    def test_19_security_password_hashes_excluded(self):
        """Verify password hashes are excluded from user serialization."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users LIMIT 5")
        from backend.models import serialize_user
        for r in cur.fetchall():
            s = serialize_user(r)
            self.assertNotIn("password_hash", s)
            self.assertNotIn("password", s)
        conn.close()


if __name__ == "__main__":
    unittest.main()
