# AP Adaptive Personalised Learning Platform

> "AP Adaptive Personalised Learning Platform is a Quantum Machine Learning based personalized learning system designed to analyze learner patterns, predict academic risk, identify learning gaps, and recommend individualized learning paths and interventions for diverse student populations."

---

## 1. Problem Statement
Large and diverse student populations across engineering colleges in Andhra Pradesh require personalized learning pathways. Traditional one-size-fits-all curricula fail to capture subtle variations in student attendance, study pace, subject weaknesses, and LMS engagement. Without early diagnostic indicators, struggling students often remain undetected until end-of-semester examinations, leading to backlogs and elevated dropout rates.

## 2. Proposed Solution
The **AP Adaptive Education Platform** leverages **Classical Machine Learning (ML)** to continuously analyze multidimensional learner performance, classify academic risk into **Low Risk**, **Medium Risk**, and **High Risk** tiers with high statistical confidence, explain underlying risk drivers through feature attribution, and generate individualized prerequisite-aware learning pathways and teacher intervention workflows.

---

## 3. System Architecture

```
Student / Teacher Client (Browser)
             │
             ▼
     Frontend (HTML5 / CSS3 / Vanilla JS / Chart.js)
             │
             ▼
     Flask REST API Layer & Session-Based RBAC
       ├── Auth Blueprint (/api/login/*, /api/auth/me)
       ├── Student Blueprint (/api/student/*)
       ├── Teacher Blueprint (/api/teacher/*)
       └── ML Blueprint (/api/ml/*)
             │
             ├──────────────────────────────────────┐
             ▼                                      ▼
  SQLite DB (students.db)              Classical ML Engine (Scikit-Learn)
  ├── users                            ├── StandardScaler & Imputer Pipeline
  ├── students                         ├── Best Classifier (Gradient Boosting)
  ├── lessons                          ├── Feature Attribution & Explainability
  ├── student_lesson_progress          ├── Personalized Learning Path Generator
  └── interventions                    └── Teacher Intervention Synthesis Engine
```

---

## 4. Classical Machine Learning Approach

### 4.1 Input Features (14 Dimensions)
The Classical ML model evaluates the following core academic and behavioral attributes:
1. `attendance`: Class attendance percentage (35%–100%)
2. `mathematics_score`: Linear algebra, calculus, probability (0–100)
3. `physics_score`: Applied physics, wave optics, semiconductors (0–100)
4. `programming_score`: C / C++ / Python coding proficiency (0–100)
5. `data_structures_score`: Stacks, queues, trees, graphs, dynamic programming (0–100)
6. `database_score`: Relational models, SQL, transactions, indexing (0–100)
7. `communication_score`: Technical presentation and writing (0–100)
8. `assignment_score`: Continuous evaluation assignment score (0–100)
9. `quiz_score`: Periodic formative quiz performance (0–100)
10. `exam_score`: Mid-term and end-term exam score (0–100)
11. `study_hours`: Self-study and laboratory practice hours per week (1–25 hrs)
12. `learning_activity`: LMS engagement and interaction index (10–100)
13. `previous_performance`: Historical GPA / percentage (30–100)
14. `overall_progress`: Completed syllabus curriculum percentage (0–100)

### 4.2 Target Classification
- **Low Risk**: Consistently high academic performance, strong attendance, and high study engagement.
- **Medium Risk**: Moderate performance with isolated subject vulnerabilities requiring targeted monitoring.
- **High Risk**: Severe attendance deficit, failing core subjects, or low LMS interaction requiring immediate faculty intervention.

---

## 5. Model Evaluation & Benchmark Results

The training pipeline evaluated 4 Classical ML classifiers on **5,500 synthetic B.Tech student records** using a stratified 80/20 train-test split (4,400 training samples, 1,100 test samples):

| Model Architecture | Validation Accuracy | Weighted Precision | Weighted Recall | Weighted F1-Score | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gradient Boosting** | **92.64%** | **92.68%** | **92.64%** | **0.9262** | **★ Selected Champion** |
| **Random Forest** | 91.91% | 92.08% | 91.91% | 0.9186 | Benchmark Candidate |
| **Decision Tree** | 87.09% | 87.05% | 87.09% | 0.8702 | Benchmark Candidate |
| **Logistic Regression** | 83.91% | 83.89% | 83.91% | 0.8384 | Baseline Candidate |

**Artifacts Generated**:
- `models/learning_risk_model.pkl` (Fitted model artifact and feature importance weights)
- `models/preprocessing_pipeline.pkl` (Median imputer and standard scaler)
- `models/model_metrics.json` (Full benchmark comparison, class reports, and confusion matrix)

---

## 6. Personalized Learning & Recommendation Engine

The recommendation engine (`ml/personalized_learning.py`) categorizes student subjects into:
- **Weak Areas** (`score < 60%`): Prioritized with remedial foundational modules.
- **Moderate Areas** (`60% <= score < 80%`): Guided problem solving and practice modules.
- **Strong Areas** (`score >= 80%`): Advanced honors modules and capstone projects.

### Dynamic Learning Path Construction
1. Identifies weak subjects and extracts prerequisite modules from the curriculum catalog.
2. Adjusts pacing based on weekly study hours and risk severity.
3. Allows interactive module completion in the Student Dashboard, dynamically updating the database and triggering real-time risk re-evaluation.

---

## 7. Faculty Intervention Engine

The intervention synthesizer (`ml/intervention_engine.py`) translates model outputs into structured faculty workflows:
- **High Risk**: Urgent 1-on-1 mentor consultations within 48 hours, parent notifications for low attendance, and remedial tutorial enrollment.
- **Medium Risk**: Bi-weekly assignment check-ins and interactive LMS engagement boosters.
- **Low Risk**: Invitations to inter-college hackathons, research reading, and peer-mentoring leadership roles.

---

## 8. Installation & Setup

### Prerequisites
- Python 3.10+
- Modern Web Browser (Chrome, Edge, Firefox, Safari)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate Dataset & Train Models (Automated)
```bash
python ml/train_model.py
```

### 3. Launch the Platform
```bash
python run.py
```
Open your browser at `http://127.0.0.1:5000/`.

---

## 9. Demo Credentials

| Role | Email | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Faculty / Teacher** | `teacher@example.com` | `teacher123` | Class roster, ML diagnostics, class-wide analytics, intervention logging |
| **Student** | `student@example.com` | `student123` | Personal dashboard, radar charts, dynamic learning path, interactive completion |

---

## 10. Verification & Test Suite

Run the automated ML and REST API unit test suites:

```bash
# Run Classical ML & Personalization Tests
python -m unittest tests/test_ml.py

# Run REST API & Auth Tests
python -m unittest tests/test_api.py
```

---

## 11. Project Directory Structure

```
AP_Adaptive_Personalised_Learning/
├── backend/
│   ├── app.py                     # Flask application factory
│   ├── auth.py                    # Session auth & RBAC decorators
│   ├── database.py                # SQLite schema and seeding
│   ├── models.py                  # Serializers
│   └── routes/
│       ├── __init__.py
│       ├── auth_routes.py         # Login, logout, session routes
│       ├── ml_routes.py           # ML metrics, explainability API
│       ├── student_routes.py      # Student profile & progress routes
│       └── teacher_routes.py      # Faculty roster & analytics routes
├── data/
│   ├── generate_dataset.py        # 5,500 student dataset generator
│   └── student_learning_dataset.csv
├── database/
│   └── students.db                # SQLite database
├── frontend/
│   ├── index.html                 # Main landing page
│   ├── ml-performance.html        # ML benchmarks & live playground
│   ├── student-dashboard.html     # Student adaptive learning portal
│   ├── student-details.html       # Teacher diagnostic deep-dive
│   ├── student-login.html         # Student authentication
│   ├── styles.css                 # Modern CSS design system
│   ├── teacher-dashboard.html     # Faculty analytics & roster
│   └── teacher-login.html         # Faculty authentication
├── ml/
│   ├── __init__.py
│   ├── evaluation.py              # Precision, Recall, F1, Confusion Matrix
│   ├── intervention_engine.py     # Teacher action synthesis
│   ├── personalized_learning.py   # Adaptive learning path generator
│   ├── predict.py                 # Risk inference & explainability
│   ├── preprocessing.py           # Feature transformations
│   └── train_model.py             # 4-model trainer & champion selector
├── models/
│   ├── learning_risk_model.pkl    # Trained champion classifier
│   ├── model_metrics.json         # Benchmark metrics JSON
│   └── preprocessing_pipeline.pkl # Preprocessing pipeline
├── tests/
│   ├── test_api.py                # REST API test suite
│   └── test_ml.py                 # ML prediction test suite
├── README.md                      # Comprehensive documentation
├── requirements.txt               # Python package dependencies
└── run.py                         # Single-command launcher
```
