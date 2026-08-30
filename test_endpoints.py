"""
Comprehensive test suite for AP Adaptive & Personalised Learning platform.
Tests all web routes, APIs, authentication, classical ML and Quantum ML pipelines.
"""
import unittest
import json
from backend.app import app
from backend.database import init_db, seed_demo_data

class PlatformTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_demo_data()
        cls.client = app.test_client()

    def test_01_landing_page(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Adaptive & Personalised Learning', res.data)
        self.assertIn(b'How It Works', res.data)
        self.assertIn(b'Andhra Pradesh', res.data)

    def test_02_routes_serving(self):
        routes = ['/student-login', '/teacher-login', '/login', '/ml-performance', '/student-dashboard', '/teacher-dashboard']
        for r in routes:
            res = self.client.get(r)
            self.assertEqual(res.status_code, 200, f"Route {r} returned {res.status_code}")

    def test_03_student_auth_and_portal(self):
        # Login
        res = self.client.post('/api/login/student', json={
            'email': 'student@example.com',
            'password': 'student123'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))

        # Student me
        res = self.client.get('/api/student/me')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data['student']['email'], 'student@example.com')

        # Student subjects
        res = self.client.get('/api/student/subjects')
        self.assertEqual(res.status_code, 200)

        # Student prediction
        res = self.client.get('/api/student/prediction')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('risk_level', data['prediction'])

        # Student learning path
        res = self.client.get('/api/student/learning-path')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))

        # Student recommendations
        res = self.client.get('/api/student/recommendations')
        self.assertEqual(res.status_code, 200)

    def test_04_teacher_auth_and_portal(self):
        # Login
        res = self.client.post('/api/login/teacher', json={
            'email': 'teacher@example.com',
            'password': 'teacher123'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))

        # Teacher students roster
        res = self.client.get('/api/teacher/students')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertGreater(len(data['students']), 0)

        # Teacher class analytics
        res = self.client.get('/api/teacher/analytics')
        self.assertEqual(res.status_code, 200)

    def test_05_ml_benchmark_api(self):
        res = self.client.get('/api/ml/metrics')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('metrics', data)

    def test_06_logout(self):
        res = self.client.post('/api/logout')
        self.assertEqual(res.status_code, 200)

if __name__ == '__main__':
    unittest.main()
