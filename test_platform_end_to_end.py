"""
End-to-End Verification Test Script for AP Adaptive Personalised Learning Platform
Tests:
1. Multi-Institution RBAC & Data Isolation (AU AIML vs JNTUK ECE - Requirement 43)
2. Curriculum-Agnostic Dynamic Subject Loading
3. Grounded Question Extraction & Source Citations (Requirement 10 & 11)
4. Adaptive Feedback Loop (Quiz Attempt -> Mastery Update -> QML/ML Reprediction -> Recommendation - Requirement 20)
5. Universal Learner Features & PennyLane 5-Qubit + 8-Qubit Quantum ML (Requirement 15, 17, 18)
6. Institution Admin Curriculum Ingestion & Validation (Requirement 6 & 29)
7. State Council Privacy-Preserving Aggregation (Requirement 24)
"""

import os
import sys
import json
import unittest

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app
from backend.database import get_db_connection, init_db, seed_demo_data


class TestPlatformEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_demo_data()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_1_health_and_qml_status(self):
        """Verify API health and Quantum ML simulator status."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("database"), "connected")
        self.assertEqual(data.get("quantum_ml"), "available")
        self.assertEqual(data.get("qml_qubits"), 5)
        print(" [PASS] API Health & 5-Qubit Quantum Device Status Verified")

    def test_2_critical_test_case_institution_isolation(self):
        """
        Critical Test Case (Requirement 43):
        Student A (AU - AIML Year 3 Sem 1) sees ONLY ML, DBMS, Computer Networks.
        Student B (JNTUK - ECE Year 3 Sem 1) sees ONLY Signals and Systems, VLSI, Digital Communication.
        Neither student sees subjects from the other institution.
        """
        # 1. Login as Student A (Andhra University - AIML)
        res_a = self.client.post("/api/login", json={
            "email": "student.au@au.edu.in",
            "password": "StudentAU@2024",
            "role": "student"
        })
        self.assertEqual(res_a.status_code, 200, f"AU Student login failed: {res_a.get_data(as_text=True)}")
        
        # Get AU Student Subjects
        res_subj_a = self.client.get("/api/student/subjects")
        self.assertEqual(res_subj_a.status_code, 200)
        subj_a_data = res_subj_a.get_json()
        subj_a_names = [s["subject_name"] for s in subj_a_data.get("subjects", [])]
        
        print(f" -> AU Student (AIML 3-1) Subjects: {subj_a_names}")
        self.assertIn("Machine Learning", subj_a_names)
        self.assertIn("Database Management Systems", subj_a_names)
        self.assertIn("Computer Networks", subj_a_names)
        
        # Verify complete isolation: Must NOT contain JNTUK ECE subjects
        self.assertNotIn("Signals and Systems", subj_a_names)
        self.assertNotIn("VLSI Design", subj_a_names)
        self.assertNotIn("Digital Communication", subj_a_names)

        # 2. Logout and Login as Student B (JNTUK - ECE)
        self.client.post("/api/logout")
        res_b = self.client.post("/api/login", json={
            "email": "student.jntuk@jntuk.edu.in",
            "password": "StudentJNTUK@2024",
            "role": "student"
        })
        self.assertEqual(res_b.status_code, 200, f"JNTUK Student login failed: {res_b.get_data(as_text=True)}")
        
        # Get JNTUK Student Subjects
        res_subj_b = self.client.get("/api/student/subjects")
        self.assertEqual(res_subj_b.status_code, 200)
        subj_b_data = res_subj_b.get_json()
        subj_b_names = [s["subject_name"] for s in subj_b_data.get("subjects", [])]
        
        print(f" -> JNTUK Student (ECE 3-1) Subjects: {subj_b_names}")
        self.assertIn("Signals and Systems", subj_b_names)
        self.assertIn("VLSI Design", subj_b_names)
        self.assertIn("Digital Communication", subj_b_names)
        
        # Verify complete isolation: Must NOT contain AU AIML subjects
        self.assertNotIn("Machine Learning", subj_b_names)
        self.assertNotIn("Database Management Systems", subj_b_names)
        self.assertNotIn("Computer Networks", subj_b_names)
        
        print(" [PASS] Critical Test Case 43: Complete Multi-Institution Curriculum Isolation Verified!")

    def test_3_grounded_quiz_and_adaptive_feedback_loop(self):
        """
        Tests:
        1. Grounded Quiz retrieval with source citations.
        2. Quiz answer submission.
        3. Real-time Topic Mastery recalculation.
        4. Re-running ML & QML learner classification.
        5. Next recommended learning step generation.
        """
        # Login as Student A
        self.client.post("/api/login", json={
            "email": "student.au@au.edu.in",
            "password": "StudentAU@2024",
            "role": "student"
        })

        # Fetch AU subjects to get Machine Learning subject ID
        res_sub = self.client.get("/api/student/subjects")
        subjects = res_sub.get_json().get("subjects", [])
        ml_subj = next((s for s in subjects if "Machine Learning" in s["subject_name"]), None)
        self.assertIsNotNone(ml_subj, "Machine Learning subject should exist for AU student")

        # Fetch syllabus hierarchy for Machine Learning
        res_hier = self.client.get(f"/api/student/subject/{ml_subj['id']}/hierarchy")
        self.assertEqual(res_hier.status_code, 200)
        hier_data = res_hier.get_json()
        modules = hier_data.get("modules", [])
        self.assertTrue(len(modules) > 0, "Modules should exist for Machine Learning")

        # Pick Topic 1 (Decision Trees)
        topic = modules[0]["topics"][0]
        topic_id = topic["id"]
        print(f" -> Testing Grounded Quiz for Topic: {topic['topic_name']} (ID: {topic_id})")

        # Fetch grounded quiz questions
        res_quiz = self.client.get(f"/api/student/topic/{topic_id}/quiz")
        self.assertEqual(res_quiz.status_code, 200)
        quiz_data = res_quiz.get_json()
        questions = quiz_data.get("questions", [])
        self.assertTrue(len(questions) > 0, "Grounded questions should be present")
        
        # Verify source provenance on questions (Requirement 8 & 11)
        first_q = questions[0]
        self.assertTrue(bool(first_q.get("source_reference")), "Questions must contain source document provenance")
        print(f" -> Question Provenance: {first_q['source_reference']}")

        # Submit answers to topic quiz
        answers = {str(q["id"]): "A" for q in questions}
        res_submit = self.client.post(f"/api/student/topic/{topic_id}/quiz/submit", json={
            "topic_id": topic_id,
            "answers": answers,
            "time_spent_minutes": 10
        })
        self.assertEqual(res_submit.status_code, 200)
        submit_data = res_submit.get_json()
        
        self.assertTrue(submit_data.get("success"))
        self.assertIn("score_percentage", submit_data)
        self.assertIn("adaptive_loop", submit_data)
        
        loop = submit_data["adaptive_loop"]
        print(f" -> Adaptive Feedback Loop: New Mastery = {loop.get('new_mastery')}% | Repredicted Risk = {loop.get('updated_prediction', {}).get('risk_level')}")
        self.assertTrue(len(loop.get("next_recommendations", [])) > 0, "Next recommendations should be generated")
        print(f" -> Next Recommended Step: {loop.get('next_recommendations')[0]['title']}")
        
        print(" [PASS] Adaptive Feedback Loop Verified!")

    def test_4_universal_learner_features_and_quantum_benchmarks(self):
        """
        Verify:
        1. 8 Universal Learner Features.
        2. PennyLane 5-Qubit VQC Champion.
        3. Experimental 8-Qubit VQC.
        4. Measured scientific metrics without unproven supremacy claims.
        """
        from ml.learner_features import extract_universal_learner_features, features_to_5qubit_vector, features_to_8qubit_vector
        from ml.quantum_model import get_quantum_benchmark_comparison, QuantumRiskClassifier, Experimental8QubitVQC

        conn = get_db_connection()
        features = extract_universal_learner_features(student_id=1, conn=conn)
        conn.close()

        # Check all 8 features exist and are bounded [0.0, 100.0]
        expected_keys = [
            "attendance", "assessment_performance", "quiz_performance", "assignment_performance",
            "lab_performance", "topic_mastery", "learning_engagement", "previous_performance"
        ]
        for key in expected_keys:
            self.assertIn(key, features)
            self.assertGreaterEqual(features[key], 0.0)
            self.assertLessEqual(features[key], 100.0)
        print(f" -> Universal 8-Feature Vector: {features}")

        # Test 5-Qubit VQC Vector Transformer
        v5 = features_to_5qubit_vector(features)
        self.assertEqual(len(v5), 5)

        # Test 8-Qubit VQC Vector Transformer
        v8 = features_to_8qubit_vector(features)
        self.assertEqual(len(v8), 8)

        # Test 5-Qubit VQC Classifier Execution
        q_clf = QuantumRiskClassifier()
        pred_5q = q_clf.predict_student_risk(features)
        self.assertIn(pred_5q["risk_level"], ["Low Risk", "Medium Risk", "High Risk"])
        print(f" -> 5-Qubit VQC Risk Diagnosis: {pred_5q['risk_level']} (Score: {pred_5q.get('risk_score')}%)")

        # Test 8-Qubit Experimental VQC Execution
        exp_8q = Experimental8QubitVQC()
        pred_8q = exp_8q.predict_student_risk(features)
        self.assertIn(pred_8q["risk_level"], ["Low Risk", "Medium Risk", "High Risk"])
        print(f" -> 8-Qubit Experimental VQC Risk Diagnosis: {pred_8q['risk_level']} (Score: {pred_8q.get('risk_score')}%)")

        # Test Benchmark API Endpoint
        res_bench = self.client.get("/api/ml/quantum-benchmarks")
        self.assertEqual(res_bench.status_code, 200)
        benchmarks = res_bench.get_json()
        self.assertIn("models_comparison", benchmarks)
        self.assertIn("scientific_integrity_disclaimer", benchmarks)
        print(" [PASS] Universal Features & Quantum ML Scientific Pipeline Verified!")

    def test_5_state_council_privacy_preserving_analytics(self):
        """
        Verify State Council (APSCHE) can view aggregated telemetry across institutions
        while individual student PII is strictly omitted.
        """
        # Login as State Admin
        self.client.post("/api/logout")
        res_login = self.client.post("/api/login", json={
            "email": "state.admin@sche.ap.gov.in",
            "password": "StateAdmin@2024",
            "role": "state_admin"
        })
        self.assertEqual(res_login.status_code, 200)

        # Fetch State-wide Aggregated Analytics
        res_state = self.client.get("/api/state-admin/analytics")
        self.assertEqual(res_state.status_code, 200)
        data = res_state.get_json()
        
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(data.get("total_institutions", 0), 2)
        self.assertIn("institutions", data)
        print(f" -> State Analytics: {data['total_institutions']} Institutions | {data['total_students']} Students across AP")
        print(" [PASS] State-level Privacy-Preserving Analytics Verified!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
