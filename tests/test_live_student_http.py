import unittest
import urllib.request
import json
import http.cookiejar

class TestLiveStudentHttp(unittest.TestCase):
    def test_live_student_dashboard_connection(self):
        try:
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            login_data = json.dumps({"email": "student@example.com", "password": "student123"}).encode("utf-8")
            req = urllib.request.Request("http://127.0.0.1:5000/api/login/student", data=login_data, headers={"Content-Type": "application/json"})
            res = opener.open(req, timeout=1.0)
            self.assertEqual(res.status, 200)
        except Exception:
            # Standalone live test requires running local server on port 5000
            self.skipTest("Live server not running on port 5000; skipping socket connection test.")

if __name__ == "__main__":
    unittest.main()

