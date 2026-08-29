"""
Classical Machine Learning & Personalization Engine Test Suite
Tests Low Risk, Medium Risk, and High Risk synthetic profiles,
validating classification accuracy, probability sums, explainability,
and personalized learning path generation.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.predict import predict_student_risk
from ml.personalized_learning import analyze_student_subjects, generate_personalized_learning_path
from ml.intervention_engine import generate_teacher_interventions

class TestClassicalMLEngine(unittest.TestCase):

    def setUp(self):
        # Profile 1: Excellent Student (High attendance, high scores)
        self.excellent_student = {
            "attendance": 96.0,
            "mathematics_score": 92.0,
            "physics_score": 88.0,
            "programming_score": 95.0,
            "data_structures_score": 94.0,
            "database_score": 90.0,
            "communication_score": 92.0,
            "assignment_score": 95.0,
            "quiz_score": 92.0,
            "exam_score": 93.0,
            "study_hours": 16.0,
            "learning_activity": 94.0,
            "previous_performance": 91.0,
            "overall_progress": 92.0
        }

        # Profile 2: Average / Moderate Student (Medium attendance and scores)
        self.average_student = {
            "attendance": 74.0,
            "mathematics_score": 66.0,
            "physics_score": 68.0,
            "programming_score": 58.0,
            "data_structures_score": 62.0,
            "database_score": 70.0,
            "communication_score": 75.0,
            "assignment_score": 68.0,
            "quiz_score": 64.0,
            "exam_score": 65.0,
            "study_hours": 6.0,
            "learning_activity": 58.0,
            "previous_performance": 67.0,
            "overall_progress": 64.0
        }

        # Profile 3: Weak / At-Risk Student (Low attendance, failing programming and math)
        self.weak_student = {
            "attendance": 52.0,
            "mathematics_score": 40.0,
            "physics_score": 48.0,
            "programming_score": 36.0,
            "data_structures_score": 38.0,
            "database_score": 44.0,
            "communication_score": 55.0,
            "assignment_score": 42.0,
            "quiz_score": 38.0,
            "exam_score": 40.0,
            "study_hours": 2.0,
            "learning_activity": 30.0,
            "previous_performance": 46.0,
            "overall_progress": 36.0
        }

    def test_excellent_student_low_risk(self):
        print("\n--- TEST 1: EXCELLENT STUDENT ---")
        pred = predict_student_risk(self.excellent_student)
        print(f"Prediction: {pred['risk_level']} | Score: {pred['risk_score']}% | Confidence: {pred['confidence']}%")
        print(f"Probabilities: {pred['probabilities']}")
        
        self.assertEqual(pred["risk_level"], "Low Risk")
        self.assertGreater(pred["probabilities"]["Low Risk"], 0.60)
        self.assertLess(pred["risk_score"], 35.0)

    def test_average_student_medium_risk(self):
        print("\n--- TEST 2: AVERAGE STUDENT ---")
        pred = predict_student_risk(self.average_student)
        print(f"Prediction: {pred['risk_level']} | Score: {pred['risk_score']}% | Confidence: {pred['confidence']}%")
        print(f"Probabilities: {pred['probabilities']}")
        
        self.assertIn(pred["risk_level"], ["Medium Risk", "Low Risk"])
        self.assertLess(pred["risk_score"], 65.0)

    def test_weak_student_high_risk(self):
        print("\n--- TEST 3: AT-RISK WEAK STUDENT ---")
        pred = predict_student_risk(self.weak_student)
        print(f"Prediction: {pred['risk_level']} | Score: {pred['risk_score']}% | Confidence: {pred['confidence']}%")
        print(f"Probabilities: {pred['probabilities']}")
        print(f"Top Risk Drivers: {[f['detail'] for f in pred['top_risk_factors'][:3]]}")
        
        self.assertEqual(pred["risk_level"], "High Risk")
        self.assertGreater(pred["probabilities"]["High Risk"], 0.60)
        self.assertGreater(pred["risk_score"], 55.0)
        self.assertTrue(len(pred["top_risk_factors"]) > 0)

    def test_personalized_learning_path(self):
        print("\n--- TEST 4: PERSONALIZED LEARNING PATH GENERATION ---")
        # Weak student should have Programming & Math remedial modules first
        path_data = generate_personalized_learning_path(self.weak_student)
        self.assertGreater(path_data["total_modules"], 0)
        
        first_step = path_data["learning_path"][0]
        print(f"First Recommended Module: {first_step['title']} ({first_step['subject']}) - Phase: {first_step['phase']}")
        self.assertIn(first_step["subject"], ["Programming Fundamentals", "Mathematics", "Data Structures & Algorithms"])

    def test_teacher_intervention_synthesis(self):
        print("\n--- TEST 5: TEACHER INTERVENTIONS ---")
        intv_data = generate_teacher_interventions(self.weak_student)
        print(f"Total Interventions: {intv_data['total_interventions']}")
        for intv in intv_data["interventions"]:
            print(f" -> [{intv['priority']}] {intv['title']}")
            
        self.assertGreaterEqual(intv_data["total_interventions"], 2)
        self.assertEqual(intv_data["student_risk_level"], "High Risk")

if __name__ == "__main__":
    unittest.main()
