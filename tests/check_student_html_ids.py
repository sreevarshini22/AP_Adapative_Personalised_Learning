import re

with open("frontend/student-dashboard.html", "r", encoding="utf-8") as f:
    html = f.read()

ids_to_check = [
    "welcomeStudentTitle", "studentAcademicTag", "studentRollTag", "studentStreakPill",
    "topOverallProgressText", "profileFullName", "profileRollNo", "profileBranch",
    "profileYearSem", "profileSection", "profileEmail", "kpiActiveSubjects",
    "overviewSubjectsContainer", "subjectsCatalogGrid", "kpiCompletedLessons",
    "kpiCompletedLabs", "kpiAttendance", "overviewWeakAreas", "overviewStrongAreas",
    "overviewRiskLabel", "overviewRiskConfidence", "topRiskBadge",
    "overviewRiskDriversList", "overviewRecommendationsList", "unreadNotifBadge",
    "availableSubjectsList", "selectSubjectsSubtitle", "selectedSubjectCountTag",
    "assignmentsCatalogGrid", "assignmentSubjectTag", "assignmentModalTitle",
    "assignmentTotalMarksText", "assignmentDueDateText", "assignmentStatusBadge",
    "assignmentInstructionsContent", "assignmentSubmissionTextInput",
    "subHubContentArea", "subHubCode", "subHubTitle", "subHubTeacher", "subHubDesc", "subHubMsgBtn"
]

missing = []
for el_id in ids_to_check:
    if f'id="{el_id}"' not in html and f"id='{el_id}'" not in html:
        missing.append(el_id)

print(f"Checked {len(ids_to_check)} element IDs.")
print(f"Missing IDs: {missing}")
