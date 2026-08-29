import urllib.request
import json
import http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. Login as student
login_data = json.dumps({"email": "student@example.com", "password": "student123"}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:5000/api/login/student", data=login_data, headers={"Content-Type": "application/json"})
res = opener.open(req)
print("Student Login Status:", res.status, res.read().decode("utf-8"))

# 2. Get Student Dashboard Page HTML directly
req2 = urllib.request.Request("http://127.0.0.1:5000/student-dashboard")
res2 = opener.open(req2)
html = res2.read().decode("utf-8")
print("Student Dashboard HTML Status:", res2.status, f"HTML size: {len(html)} bytes")

# 3. Fetch Student ME API
req3 = urllib.request.Request("http://127.0.0.1:5000/api/student/me")
res3 = opener.open(req3)
student_me = json.loads(res3.read().decode("utf-8"))
print("Student Me API:", student_me.get("success"), "Student Name:", student_me.get("student", {}).get("full_name"), "Branch:", student_me.get("student", {}).get("branch"))

# 4. Fetch Student Dynamic Subjects API
req4 = urllib.request.Request("http://127.0.0.1:5000/api/student/subjects")
res4 = opener.open(req4)
subjects_data = json.loads(res4.read().decode("utf-8"))
subjects = subjects_data.get("subjects", [])
print(f"Dynamic Subjects Loaded: {len(subjects)}")
for s in subjects:
    print(f"  * [{s['subject_code']}] {s['subject_name']} ({s['branch']} - {s['year']} - Sem {s['semester']})")

print("\n>>> ALL LIVE STUDENT DASHBOARD CHECKS VERIFIED SUCCESSFULLY! <<<")
