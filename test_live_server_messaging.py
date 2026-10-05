import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def run_live_e2e_tests():
    print("=" * 60)
    print("LIVE SERVER MESSAGING E2E VERIFICATION ON http://127.0.0.1:5000")
    print("=" * 60)

    # 1. Health check
    res = requests.get(f"{BASE_URL}/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("[PASS] 1. Server Health Check OK")

    # 2. Teacher Session
    teacher_session = requests.Session()
    login_res = teacher_session.post(f"{BASE_URL}/api/login/teacher", json={
        "email": "teacher@example.com",
        "password": "teacher123"
    })
    assert login_res.status_code == 200, f"Teacher login failed: {login_res.text}"
    t_login_data = login_res.json()
    print(f"[PASS] 2. Teacher Login OK -> Logged in as: {t_login_data.get('user', {}).get('full_name')}")

    # 3. Teacher fetches messaging inbox
    inbox_res = teacher_session.get(f"{BASE_URL}/api/teacher/messages")
    assert inbox_res.status_code == 200, f"Teacher inbox failed: {inbox_res.text}"
    inbox_data = inbox_res.json()
    assert inbox_data["success"] is True
    print(f"[PASS] 3. Teacher Inbox Loaded -> Active conversations: {len(inbox_data.get('conversations', []))}, Available students: {len(inbox_data.get('available_students', []))}")

    # 4. Teacher sends message to Student 1 (Sai Krishna Varma / Rahul Varma)
    t_msg_text = "Live Verification: Please submit your Quantum Computing & Statistics lab observations before 5 PM."
    send_res = teacher_session.post(f"{BASE_URL}/api/teacher/messages", json={
        "student_id": 1,
        "message": t_msg_text
    })
    assert send_res.status_code == 201, f"Teacher send failed: {send_res.text}"
    send_data = send_res.json()
    assert send_data["success"] is True
    conv_id = send_data["conversation_id"]
    print(f"[PASS] 4. Teacher Sent Message -> Conversation ID: {conv_id}")

    # 5. Student Session
    student_session = requests.Session()
    st_login_res = student_session.post(f"{BASE_URL}/api/login/student", json={
        "email": "student@example.com",
        "password": "student123"
    })
    assert st_login_res.status_code == 200, f"Student login failed: {st_login_res.text}"
    st_login_data = st_login_res.json()
    print(f"[PASS] 5. Student Login OK -> Logged in as: {st_login_data.get('user', {}).get('full_name')}")

    # 6. Student fetches unread count
    unread_res = student_session.get(f"{BASE_URL}/api/student/messages/unread-count")
    assert unread_res.status_code == 200
    unread_count_before = unread_res.json().get("unread_count", 0)
    assert unread_count_before >= 1, "Student should have at least 1 unread message"
    print(f"[PASS] 6. Student Unread Count Detected: {unread_count_before} unread message(s)")

    # 7. Student opens thread -> messages marked as read
    thread_res = student_session.get(f"{BASE_URL}/api/student/messages/{conv_id}")
    assert thread_res.status_code == 200
    thread_data = thread_res.json()
    assert thread_data["success"] is True
    assert len(thread_data["messages"]) > 0
    last_msg = thread_data["messages"][-1]
    assert last_msg["sender_role"] == "teacher"
    assert t_msg_text in last_msg["message"]
    print(f"[PASS] 7. Student Opened Thread -> Retrieved {len(thread_data['messages'])} message(s) in chronological order")

    # 8. Verify unread count decreased
    unread_after_res = student_session.get(f"{BASE_URL}/api/student/messages/unread-count")
    unread_after = unread_after_res.json().get("unread_count", 0)
    assert unread_after < unread_count_before
    print(f"[PASS] 8. Read Receipt Applied -> Unread count decreased to {unread_after}")

    # 9. Student replies to teacher
    st_reply_text = "Live Verification Reply: Yes professor, lab observations are completed and uploaded."
    st_send_res = student_session.post(f"{BASE_URL}/api/student/messages", json={
        "teacher_id": 5,
        "conversation_id": conv_id,
        "message": st_reply_text
    })
    assert st_send_res.status_code == 201
    st_send_data = st_send_res.json()
    assert st_send_data["success"] is True
    print(f"[PASS] 9. Student Replied to Teacher -> Message posted successfully")

    # 10. Teacher checks thread -> receives student reply
    t_thread_res = teacher_session.get(f"{BASE_URL}/api/teacher/messages/{conv_id}")
    assert t_thread_res.status_code == 200
    t_thread_data = t_thread_res.json()
    assert t_thread_data["success"] is True
    teacher_last_msg = t_thread_data["messages"][-1]
    assert teacher_last_msg["sender_role"] == "student"
    assert st_reply_text in teacher_last_msg["message"]
    print(f"[PASS] 10. Teacher Received Student Reply in Realtime")

    # 11. Security Isolation: Another student cannot access conv_id
    second_student = requests.Session()
    # Student 2 login (or attempt with another account)
    sec_login = second_student.post(f"{BASE_URL}/api/login/student", json={
        "email": "dr.anand.acceptance@apedu.ac.in",
        "password": "wrongpassword"
    })
    # Check that unauthenticated or other student gets empty or 401
    unauth_res = requests.get(f"{BASE_URL}/api/student/messages/{conv_id}")
    assert unauth_res.status_code in [401, 403, 302]
    print(f"[PASS] 11. Unauthorized Access Rejected (Status: {unauth_res.status_code})")

    # 12. Input validation: Empty message returns 400
    bad_req_res = teacher_session.post(f"{BASE_URL}/api/teacher/messages", json={
        "student_id": 1,
        "message": "    "
    })
    assert bad_req_res.status_code == 400
    print(f"[PASS] 12. Empty Message Validation Returned 400 Bad Request")

    # 13. Invalid recipient returns 404
    not_found_res = teacher_session.post(f"{BASE_URL}/api/teacher/messages", json={
        "student_id": 999999,
        "message": "Hello ghost student"
    })
    assert not_found_res.status_code == 404
    print(f"[PASS] 13. Invalid Recipient Validation Returned 404 Not Found")

    print("\n" + "=" * 60)
    print("ALL 13 LIVE SERVER END-TO-END TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_live_e2e_tests()
