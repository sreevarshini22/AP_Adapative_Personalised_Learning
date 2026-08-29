"""
Dataset Generation Script for AP Adaptive Education Platform
Generates 5,000+ realistic synthetic B.Tech student records with natural correlations,
multidimensional academic scores, attendance, behavioral engagement metrics, and risk categories.
"""

import os
import random
import numpy as np
import pandas as pd

FIRST_NAMES = [
    "Sai", "Venkata", "Karthik", "Ananya", "Pooja", "Rahul", "Harika", "Suresh",
    "Divya", "Rohit", "Sneha", "Aditya", "Bhavya", "Manoj", "Pranavi", "Nikhil",
    "Kavya", "Varun", "Tejaswi", "Pavan", "Sireesha", "Charan", "Keerthi", "Srikanth",
    "Manasa", "Tarun", "Deepika", "Ganesh", "Lavanya", "Mahesh", "Sravani", "Ravi",
    "Sandhya", "Akhil", "Chaitanya", "Yamini", "Naresh", "Swathi", "Ramesh", "Gayatri"
]

LAST_NAMES = [
    "Reddy", "Rao", "Naidu", "Chowdary", "Varma", "Goud", "Sharma", "Verma",
    "Raju", "Gupta", "Patel", "Kumar", "Prasad", "Murthy", "Babu", "Sastry",
    "Mishra", "Joshi", "Bhatt", "Chary", "Yadav", "Kulkarni", "Somayajulu"
]

BRANCHES = [
    "CSE",
    "CSE (AI & ML)",
    "CSE (Data Science)",
    "ECE",
    "EEE",
    "Mechanical Engineering",
    "Civil Engineering",
    "Information Technology"
]

YEAR_SEM_MAP = {
    "1st Year": [1, 2],
    "2nd Year": [3, 4],
    "3rd Year": [5, 6],
    "4th Year": [7, 8]
}

SECTIONS = ["A", "B", "C", "D"]

def generate_student_dataset(n_samples=5200, seed=42):
    random.seed(seed)
    np.random.seed(seed)

    records = []
    
    for i in range(1, n_samples + 1):
        student_id = f"AP2024_{1000 + i}"
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        
        # Roll number format: e.g., 22A91A0501
        year_name = random.choice(["1st Year", "2nd Year", "3rd Year", "4th Year"])
        admission_year = 24 - (int(year_name[0]) - 1)
        sem = random.choice(YEAR_SEM_MAP[year_name])
        branch = random.choice(BRANCHES)
        sec = random.choice(SECTIONS)
        
        branch_code_map = {
            "CSE": "05", "CSE (AI & ML)": "42", "CSE (Data Science)": "44",
            "ECE": "04", "EEE": "02", "Mechanical Engineering": "03",
            "Civil Engineering": "01", "Information Technology": "12"
        }
        b_code = branch_code_map.get(branch, "05")
        roll_no = f"{admission_year}A91A{b_code}{i%90 + 1:02d}"
        
        email_clean = f"{first_name.lower()}.{last_name.lower()}{i%999}@apedu.ac.in"
        
        # Latent student aptitude and discipline variables
        # base_aptitude ~ N(68, 14), discipline ~ N(70, 15)
        base_aptitude = np.random.normal(68, 13)
        discipline = np.random.normal(70, 14)
        
        # Attendance heavily linked to discipline
        attendance = np.clip(discipline * 0.8 + np.random.normal(15, 7), 38.0, 99.5)
        
        # Weekly study hours (linked to discipline)
        study_hours = np.clip(int(discipline * 0.22 + np.random.normal(2, 2)), 1, 28)
        
        # LMS Activity (10-100)
        learning_activity = np.clip(int(discipline * 0.7 + attendance * 0.2 + np.random.normal(5, 6)), 12, 98)
        
        # Academic subject scores
        # Students might have specific weak or strong domains
        math_factor = np.random.normal(0, 9)
        prog_factor = np.random.normal(0, 10)
        phys_factor = np.random.normal(0, 9)
        ds_factor = np.random.normal(0, 9)
        db_factor = np.random.normal(0, 8)
        comm_factor = np.random.normal(5, 8)
        
        math_score = np.clip(int(base_aptitude * 0.75 + discipline * 0.2 + math_factor), 22, 99)
        phys_score = np.clip(int(base_aptitude * 0.70 + discipline * 0.2 + phys_factor), 24, 98)
        prog_score = np.clip(int(base_aptitude * 0.80 + discipline * 0.15 + prog_factor), 20, 100)
        ds_score = np.clip(int(prog_score * 0.65 + base_aptitude * 0.25 + ds_factor), 20, 99)
        db_score = np.clip(int(base_aptitude * 0.65 + discipline * 0.25 + db_factor), 25, 99)
        comm_score = np.clip(int(base_aptitude * 0.50 + discipline * 0.35 + comm_factor), 35, 98)
        
        # Formative and summative assessments
        assignment_score = np.clip(int(discipline * 0.65 + attendance * 0.25 + np.random.normal(6, 5)), 25, 100)
        quiz_score = np.clip(int(base_aptitude * 0.5 + discipline * 0.35 + np.random.normal(8, 6)), 22, 100)
        exam_score = np.clip(int((math_score + phys_score + prog_score + ds_score + db_score)/5.0 * 0.85 + np.random.normal(5, 6)), 20, 99)
        
        # Historical & Progress
        previous_performance = np.clip(int(base_aptitude * 0.7 + discipline * 0.25 + np.random.normal(3, 5)), 30, 98)
        overall_progress = np.clip(int(attendance * 0.4 + assignment_score * 0.3 + learning_activity * 0.3), 15, 99)
        
        # Compute ground-truth Risk Category
        # Composite score with clear academic risk thresholds:
        # High Risk: poor attendance (<65%) OR failing core subjects (<50%) OR poor exam/assignment performance
        core_avg = (math_score + phys_score + prog_score + ds_score + db_score + comm_score) / 6.0
        
        # Risk index: higher value means higher risk (0 to 100)
        risk_index = (
            (100 - attendance) * 0.30 +
            (100 - core_avg) * 0.30 +
            (100 - exam_score) * 0.15 +
            (100 - quiz_score) * 0.10 +
            (100 - learning_activity) * 0.08 +
            (25 - study_hours) * 0.07
        )
        
        # Add realistic boundary noise
        risk_index += np.random.normal(0, 3.5)
        
        if risk_index >= 46.0 or attendance < 58.0 or core_avg < 45.0:
            risk_level = "High Risk"
        elif risk_index >= 30.0 or attendance < 72.0 or core_avg < 62.0:
            risk_level = "Medium Risk"
        else:
            risk_level = "Low Risk"
            
        records.append({
            "student_id": student_id,
            "full_name": full_name,
            "roll_no": roll_no,
            "email": email_clean,
            "year": year_name,
            "branch": branch,
            "section": sec,
            "semester": sem,
            "attendance": round(float(attendance), 1),
            "mathematics_score": int(math_score),
            "physics_score": int(phys_score),
            "programming_score": int(prog_score),
            "data_structures_score": int(ds_score),
            "database_score": int(db_score),
            "communication_score": int(comm_score),
            "assignment_score": int(assignment_score),
            "quiz_score": int(quiz_score),
            "exam_score": int(exam_score),
            "study_hours": int(study_hours),
            "learning_activity": int(learning_activity),
            "previous_performance": int(previous_performance),
            "overall_progress": int(overall_progress),
            "risk_level": risk_level
        })
        
    df = pd.DataFrame(records)
    return df

def main():
    os.makedirs("data", exist_ok=True)
    df = generate_student_dataset(n_samples=5500, seed=42)
    csv_path = os.path.join("data", "student_learning_dataset.csv")
    df.to_csv(csv_path, index=False)
    print(f"Dataset generated successfully at: {csv_path}")
    print(f"Total rows: {len(df)}")
    print("\nRisk Level Distribution:")
    print(df["risk_level"].value_counts(normalize=True) * 100)
    print("\nBranch Distribution:")
    print(df["branch"].value_counts())
    print("\nFirst 3 rows:")
    print(df.head(3))

if __name__ == "__main__":
    main()
