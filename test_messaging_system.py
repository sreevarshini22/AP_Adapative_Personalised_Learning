"""
Comprehensive Test Suite for Messaging System:
Verifies Teacher -> Student, Student -> Teacher messaging, database persistence,
mark as read, unread count badge calculation, and cross-student isolation security.
"""
import unittest
import json
from backend.app import app
from backend.database import init_db, seed_demo_data, get_db_connection

class MessagingSystemTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_demo_data()
        cls.client = app.test_client()

    def login_teacher(self):
        res = self.client.post('/api/login/teacher', json={
            'email': 'teacher@example.com',
            'password': 'teacher123'
        })
        self.assertEqual(res.status_code, 200)
        return res

    def login_student(self, email='student@example.com', password='student123'):
        res = self.client.post('/api/login/student', json={
            'email': email,
            'password': password
        })
        self.assertEqual(res.status_code, 200)
        return res

    def logout(self):
        return self.client.post('/api/logout')

    def test_01_teacher_sends_message_to_student(self):
        """Test 1: Teacher logs in, selects Student, and sends a message."""
        self.login_teacher()

        # 1. Fetch teacher conversations
        res = self.client.get('/api/teacher/messages')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('conversations', data)
        self.assertIn('available_students', data)

        # 2. Teacher sends message to student 1 (Rahul Varma)
        send_res = self.client.post('/api/teacher/messages', json={
            'student_id': 1,
            'message': 'Hello Rahul, please complete the Statistics revision quiz by Friday.'
        })
        self.assertEqual(send_res.status_code, 201)
        send_data = send_res.get_json()
        self.assertTrue(send_data['success'])
        self.assertIn('conversation_id', send_data)
        conv_id = send_data['conversation_id']
        self.assertTrue(conv_id.startswith('conv_s1_t'))

        self.logout()

    def test_02_student_receives_message_and_unread_count(self):
        """Test 2 & 6: Student logs in, sees unread message, opens it and unread count decreases."""
        self.login_student()

        # 1. Check unread count before opening
        res_unread = self.client.get('/api/student/messages/unread-count')
        self.assertEqual(res_unread.status_code, 200)
        unread_data = res_unread.get_json()
        self.assertGreaterEqual(unread_data['unread_count'], 1)

        # 2. Fetch conversations
        res = self.client.get('/api/student/messages')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(len(data['conversations']), 0)
        
        target_conv = data['conversations'][0]
        conv_id = target_conv['conversation_id']

        # 3. Open thread (marks unread as read)
        res_thread = self.client.get(f'/api/student/messages/{conv_id}')
        self.assertEqual(res_thread.status_code, 200)
        thread_data = res_thread.get_json()
        self.assertTrue(thread_data['success'])
        self.assertGreater(len(thread_data['messages']), 0)
        self.assertIn('Statistics revision quiz', thread_data['messages'][-1]['message'])

        # 4. Check unread count after opening (should decrease by thread unread count)
        res_unread_after = self.client.get('/api/student/messages/unread-count')
        self.assertEqual(res_unread_after.get_json()['unread_count'], unread_data['unread_count'] - target_conv['unread_count'])

        self.logout()

    def test_03_student_replies_and_teacher_receives(self):
        """Test 3: Student replies -> Teacher logs in and receives the reply."""
        self.login_student()

        # Fetch conversation to get teacher_id
        res = self.client.get('/api/student/messages')
        conv = res.get_json()['conversations'][0]
        teacher_id = conv['teacher_id']

        # Student replies
        reply_res = self.client.post('/api/student/messages', json={
            'teacher_id': teacher_id,
            'message': 'Thank you sir, I have reviewed the Statistics concepts and submitted the quiz.'
        })
        self.assertEqual(reply_res.status_code, 201)
        self.logout()

        # Teacher logs in to verify reply received
        self.login_teacher()
        res_teacher_thread = self.client.get(f"/api/teacher/messages/{conv['conversation_id']}")
        self.assertEqual(res_teacher_thread.status_code, 200)
        t_data = res_teacher_thread.get_json()
        self.assertTrue(t_data['success'])
        last_msg = t_data['messages'][-1]
        self.assertEqual(last_msg['sender_role'], 'student')
        self.assertIn('Thank you sir', last_msg['message'])
        self.logout()

    def test_04_message_persistence_and_ordering(self):
        """Test 4 & 5: Messages persist in SQLite database with correct chronological ordering."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE conversation_id LIKE 'conv_s1%' ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()

        self.assertGreaterEqual(len(rows), 2)
        # First message was from teacher, second was from student
        self.assertEqual(rows[0]['sender_role'], 'teacher')
        self.assertEqual(rows[1]['sender_role'], 'student')

    def test_05_cross_student_privacy_isolation(self):
        """Test 7: Security check - another student cannot access student 1's messages."""
        # Create a second student in DB if needed or query with student 2
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE role = 'student' AND email != 'student@example.com' LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            second_email = row['email']
            self.login_student(email=second_email, password='student123')
            # Try to fetch student 1's conversation
            res = self.client.get('/api/student/messages/conv_s1_t1')
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            # Must return empty messages for unauthorized thread
            self.assertEqual(len(data['messages']), 0)
            self.logout()

    def test_06_empty_message_validation(self):
        """Test 8: Input validation - empty message returns 400 Bad Request."""
        self.login_teacher()
        res = self.client.post('/api/teacher/messages', json={
            'student_id': 1,
            'message': '   '
        })
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])
        self.logout()

        self.login_student()
        res_st = self.client.post('/api/student/messages', json={
            'teacher_id': 1,
            'message': ''
        })
        self.assertEqual(res_st.status_code, 400)
        self.assertFalse(res_st.get_json()['success'])
        self.logout()

    def test_07_invalid_recipient_validation(self):
        """Test 9: Invalid recipient handling returns appropriate error code."""
        self.login_teacher()
        res = self.client.post('/api/teacher/messages', json={
            'student_id': 999999,
            'message': 'Hello nonexistent student'
        })
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.get_json()['success'])
        self.logout()

    def test_08_multiple_messages_ordering(self):
        """Test 5 & 10: Send multiple messages and verify correct ascending chronological ordering."""
        import time
        run_tag = f"seq_{int(time.time() * 1000)}"
        self.login_teacher()
        sent_conv_id = None
        for i in range(3):
            s_res = self.client.post('/api/teacher/messages', json={
                'student_id': 1,
                'message': f'{run_tag} guidance note #{i+1}'
            })
            self.assertEqual(s_res.status_code, 201)
            sent_conv_id = s_res.get_json()['conversation_id']
        self.logout()

        self.login_student()
        # Student fetches thread
        res = self.client.get(f'/api/student/messages/{sent_conv_id}')
        self.assertEqual(res.status_code, 200)
        msgs = res.get_json()['messages']
        teacher_msgs = [m['message'] for m in msgs if run_tag in m['message']]
        self.assertEqual(len(teacher_msgs), 3)
        self.assertEqual(teacher_msgs, [
            f'{run_tag} guidance note #1',
            f'{run_tag} guidance note #2',
            f'{run_tag} guidance note #3'
        ])
        self.logout()

    def test_09_database_persistence_across_connection_restarts(self):
        """Test 4: Messages persist directly in SQLite database across fresh connections."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM messages WHERE conversation_id LIKE 'conv_s1%'")
        count = cursor.fetchone()['total']
        conn.close()
        self.assertGreaterEqual(count, 5)

    def test_10_teacher_cannot_access_unauthorized_conversations(self):
        """Test 7b: Security check - a faculty member cannot see messages they are not a participant of."""
        other_teacher_email = 'dr.ravi@apedu.ac.in'
        self.login_student()
        # Student sends message to teacher@example.com (id=5)
        s_res = self.client.post('/api/student/messages', json={
            'teacher_id': 5,
            'message': 'Confidential project inquiry for primary advisor'
        })
        self.assertEqual(s_res.status_code, 201)
        conv_id = s_res.get_json()['conversation_id']
        self.logout()

        # Other teacher logs in
        login_res = self.client.post('/api/login/teacher', json={
            'email': other_teacher_email,
            'password': 'teacher123'
        })
        self.assertEqual(login_res.status_code, 200)
        # Other teacher tries to access conv_id between student 1 and teacher 5
        res = self.client.get(f'/api/teacher/messages/{conv_id}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data['messages']), 0)
        self.logout()

if __name__ == '__main__':
    unittest.main()
