"""
Database layer for AP Adaptive Education Platform
Manages SQLite schema, tables for dynamic academics (subjects, lessons, labs, assessments, quizzes, messages, notifications, goals), and migrations.
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_DIR = os.path.join(PROJECT_ROOT, "database")
DB_PATH = os.path.join(DB_DIR, "students.db")

def get_db_connection():
    """Returns a SQLite database connection with row factory enabled."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Creates all database tables and ensures required schema is present."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users table (Central authentication entity)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL, -- 'student' or 'teacher'
        full_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. Teachers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        branch TEXT,
        year TEXT,
        section TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    
    # 3. Students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        full_name TEXT NOT NULL,
        roll_no TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        year TEXT NOT NULL,
        branch TEXT NOT NULL,
        section TEXT NOT NULL,
        semester INTEGER NOT NULL,
        attendance REAL NOT NULL DEFAULT 75.0,
        mathematics_score REAL NOT NULL DEFAULT 65.0,
        physics_score REAL NOT NULL DEFAULT 65.0,
        programming_score REAL NOT NULL DEFAULT 65.0,
        data_structures_score REAL NOT NULL DEFAULT 65.0,
        database_score REAL NOT NULL DEFAULT 65.0,
        communication_score REAL NOT NULL DEFAULT 70.0,
        assignment_score REAL NOT NULL DEFAULT 70.0,
        quiz_score REAL NOT NULL DEFAULT 65.0,
        exam_score REAL NOT NULL DEFAULT 65.0,
        study_hours REAL NOT NULL DEFAULT 8.0,
        learning_activity REAL NOT NULL DEFAULT 60.0,
        previous_performance REAL NOT NULL DEFAULT 65.0,
        overall_progress REAL NOT NULL DEFAULT 50.0,
        learning_streak INTEGER NOT NULL DEFAULT 3,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
    );
    """)
    
    # 4. Subjects table (Dynamic branch, year, semester curriculum)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_code TEXT UNIQUE NOT NULL,
        subject_name TEXT NOT NULL,
        branch TEXT NOT NULL,
        year TEXT NOT NULL,
        semester INTEGER NOT NULL,
        credits INTEGER DEFAULT 3,
        subject_type TEXT DEFAULT 'theory', -- 'theory', 'lab', 'integrated'
        description TEXT
    );
    """)
    
    # 5. Teacher-Subject Assignments table (Connects teacher to subject/section)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teacher_subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        branch TEXT NOT NULL,
        year TEXT NOT NULL,
        semester INTEGER NOT NULL,
        section TEXT NOT NULL,
        FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
        UNIQUE(teacher_id, subject_id, branch, year, semester, section)
    );
    """)
    
    # Migrate legacy lessons table if it lacks subject_id
    cursor.execute("PRAGMA table_info(lessons)")
    cols = [col["name"] for col in cursor.fetchall()]
    if cols and "subject_id" not in cols:
        cursor.execute("DROP TABLE IF EXISTS student_lesson_progress")
        cursor.execute("DROP TABLE IF EXISTS lesson_progress")
        cursor.execute("DROP TABLE IF EXISTS lessons")

    # 6. Lessons table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        topic TEXT,
        content TEXT NOT NULL,
        difficulty TEXT DEFAULT 'Beginner', -- 'Beginner', 'Intermediate', 'Advanced'
        estimated_minutes INTEGER DEFAULT 45,
        order_number INTEGER DEFAULT 1,
        prerequisite_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)
    
    # 7. Student Lesson Progress table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lesson_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        lesson_id INTEGER NOT NULL,
        status TEXT DEFAULT 'Not Started', -- 'Not Started', 'In Progress', 'Completed'
        progress_percentage REAL DEFAULT 0.0,
        completed_at TIMESTAMP,
        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (lesson_id) REFERENCES lessons (id) ON DELETE CASCADE,
        UNIQUE(student_id, lesson_id)
    );
    """)
    
    # 8. Labs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS labs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        instructions TEXT NOT NULL,
        experiment_number INTEGER NOT NULL,
        difficulty TEXT DEFAULT 'Intermediate',
        estimated_minutes INTEGER DEFAULT 60,
        resources TEXT,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)
    
    # 9. Student Lab Progress table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lab_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        lab_id INTEGER NOT NULL,
        status TEXT DEFAULT 'Not Started', -- 'Not Started', 'In Progress', 'Completed'
        score REAL DEFAULT 0.0,
        completed_at TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (lab_id) REFERENCES labs (id) ON DELETE CASCADE,
        UNIQUE(student_id, lab_id)
    );
    """)
    
    # 10. Assessments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        total_marks REAL DEFAULT 50.0,
        duration_minutes INTEGER DEFAULT 60,
        due_date TEXT,
        assessment_type TEXT DEFAULT 'Mid Examination',
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)
    
    # 11. Student Assessment Results table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assessment_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        assessment_id INTEGER NOT NULL,
        score REAL NOT NULL,
        total_marks REAL NOT NULL,
        percentage REAL NOT NULL,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Graded',
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (assessment_id) REFERENCES assessments (id) ON DELETE CASCADE,
        UNIQUE(student_id, assessment_id)
    );
    """)
    
    # 12. Quizzes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        topic TEXT,
        difficulty TEXT DEFAULT 'Intermediate',
        time_limit INTEGER DEFAULT 15,
        total_questions INTEGER DEFAULT 5,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)
    
    # 13. Quiz Questions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quiz_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_option TEXT NOT NULL, -- 'A', 'B', 'C', 'D'
        explanation TEXT,
        marks REAL DEFAULT 1.0,
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
    );
    """)
    
    # 14. Student Quiz Results table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        quiz_id INTEGER NOT NULL,
        score REAL NOT NULL,
        total_marks REAL NOT NULL,
        percentage REAL NOT NULL,
        weak_topic TEXT,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
    );
    """)
    
    # 15. Messages table (Student <-> Teacher conversation threads)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        sender_id INTEGER NOT NULL,
        sender_role TEXT NOT NULL, -- 'student' or 'teacher'
        receiver_id INTEGER NOT NULL,
        receiver_role TEXT NOT NULL, -- 'student' or 'teacher'
        subject_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)
    
    # 16. Notifications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info', -- 'lesson', 'quiz', 'assessment', 'message', 'recommendation', 'risk'
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    
    # 17. Learning Goals table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS learning_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        target_percentage REAL NOT NULL,
        current_percentage REAL NOT NULL DEFAULT 0.0,
        status TEXT DEFAULT 'In Progress', -- 'In Progress', 'Achieved'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
    );
    """)
    
    # 18. Teacher Interventions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interventions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        teacher_id INTEGER,
        risk_level TEXT NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        priority TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Active',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE SET NULL
    );
    """)
    
    # 19. Student CSV Bulk Import History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_import_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        file_name TEXT NOT NULL,
        total_rows INTEGER NOT NULL,
        imported_rows INTEGER NOT NULL,
        skipped_rows INTEGER NOT NULL,
        error_rows INTEGER NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    
    # 20. Student Selected Subjects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, subject_id),
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)
    
    # 21. Subject Assignments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        instructions TEXT,
        total_marks REAL DEFAULT 100.0,
        due_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)
    
    # 22. Student Assignment Submissions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignment_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        submission_text TEXT NOT NULL,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        score REAL,
        feedback TEXT,
        status TEXT DEFAULT 'Submitted', -- 'Submitted', 'Graded', 'Under Review'
        UNIQUE(assignment_id, student_id),
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
    );
    """)
    
    # Safe column migration for students table
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN learning_streak INTEGER DEFAULT 3")
    except sqlite3.OperationalError:
        pass # column already exists
        
    conn.commit()
    conn.close()

def seed_demo_data():
    """Initializes schema and seeds baseline demo data if necessary."""
    init_db()
    from data.seed_academic_data import seed_academic_curriculum
    seed_academic_curriculum()

if __name__ == "__main__":
    init_db()
    seed_demo_data()
