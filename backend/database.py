"""
Database layer for AP Adaptive Education Platform
Manages SQLite schema, tables for dynamic academics (subjects, lessons, labs, assessments, quizzes, messages, notifications, goals), and migrations.
"""

import os
import shutil
import sqlite3
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Handle read-only serverless environments (e.g. Vercel / AWS Lambda)
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or not os.access(PROJECT_ROOT, os.W_OK):
    DB_DIR = "/tmp"
    DB_PATH = os.path.join(DB_DIR, "students.db")
    orig_db = os.path.join(PROJECT_ROOT, "database", "students.db")
    if os.path.exists(orig_db) and not os.path.exists(DB_PATH):
        try:
            shutil.copy2(orig_db, DB_PATH)
        except Exception:
            pass
else:
    DB_DIR = os.path.join(PROJECT_ROOT, "database")
    DB_PATH = os.path.join(DB_DIR, "students.db")

def get_db_connection():
    """Returns a SQLite database connection with row factory, WAL mode, and high-concurrency pragmas enabled."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")
        conn.execute("PRAGMA temp_store = MEMORY")
    except Exception:
        pass
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
        department TEXT,
        designation TEXT DEFAULT 'Faculty',
        year TEXT,
        section TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    
    # Auto-migrate teachers table for department and designation columns
    cursor.execute("PRAGMA table_info(teachers)")
    teacher_cols = [col["name"] for col in cursor.fetchall()]
    if "department" not in teacher_cols:
        try:
            cursor.execute("ALTER TABLE teachers ADD COLUMN department TEXT")
            cursor.execute("UPDATE teachers SET department = branch WHERE department IS NULL")
        except Exception:
            pass
    if "designation" not in teacher_cols:
        try:
            cursor.execute("ALTER TABLE teachers ADD COLUMN designation TEXT DEFAULT 'Faculty'")
        except Exception:
            pass
    
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
    
    # 5b. Teacher Class Assignments table (Connects teacher to specific branch/year/section cohort)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teacher_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        branch TEXT NOT NULL,
        year TEXT NOT NULL,
        section TEXT NOT NULL,
        academic_year TEXT DEFAULT '2024-2025',
        is_class_teacher INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE CASCADE,
        UNIQUE(teacher_id, branch, year, section)
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
        subject_id INTEGER,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0,
        read_at TIMESTAMP,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE SET NULL
    );
    """)
    
    # Check if subject_id is NOT NULL in legacy table or read_at is missing
    cursor.execute("PRAGMA table_info(messages)")
    msg_cols_info = cursor.fetchall()
    msg_cols = [col["name"] for col in msg_cols_info]
    subject_id_col = next((col for col in msg_cols_info if col["name"] == "subject_id"), None)
    
    if subject_id_col and subject_id_col["notnull"] == 1:
        try:
            cursor.execute("""
            CREATE TABLE messages_temp_migration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_role TEXT NOT NULL,
                receiver_id INTEGER NOT NULL,
                receiver_role TEXT NOT NULL,
                subject_id INTEGER,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0,
                read_at TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE SET NULL
            );
            """)
            cursor.execute(f"INSERT INTO messages_temp_migration (id, conversation_id, sender_id, sender_role, receiver_id, receiver_role, subject_id, message, created_at, is_read, read_at) SELECT id, conversation_id, sender_id, sender_role, receiver_id, receiver_role, subject_id, message, created_at, is_read, {'read_at' if 'read_at' in msg_cols else 'NULL'} FROM messages")
            cursor.execute("DROP TABLE messages")
            cursor.execute("ALTER TABLE messages_temp_migration RENAME TO messages")
        except Exception:
            pass
    elif "read_at" not in msg_cols:
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN read_at TIMESTAMP")
        except Exception:
            pass
            
    # Indexes for high-performance message queries and polling
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages (conversation_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages (sender_role, sender_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages (receiver_role, receiver_id, is_read);")

    
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
        institution_id INTEGER,
        subject_id INTEGER,
        risk_level TEXT DEFAULT 'Medium Risk',
        action_type TEXT DEFAULT 'Remedial Quiz',
        title TEXT NOT NULL,
        category TEXT DEFAULT 'Academic Support',
        priority TEXT DEFAULT 'High',
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Assigned',
        notes TEXT,
        due_date TEXT,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE SET NULL,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE SET NULL,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE
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

    # =========================================================================
    # MULTI-INSTITUTION & DYNAMIC CURRICULUM SCHEMA EXTENSIONS
    # =========================================================================

    # 23. Institutions table (Multi-tenancy & Institution Master)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS institutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aishe_code TEXT UNIQUE,
        institution_name TEXT NOT NULL,
        institution_type TEXT DEFAULT 'University', -- 'University', 'Autonomous College', 'Affiliated College', 'Institute of National Importance', 'Polytechnic', 'Medical', 'Management'
        university_name TEXT,
        state TEXT NOT NULL DEFAULT 'Andhra Pradesh',
        district TEXT DEFAULT 'Visakhapatnam',
        city TEXT DEFAULT 'Visakhapatnam',
        website TEXT,
        status TEXT DEFAULT 'active', -- 'active', 'inactive', 'archived'
        source TEXT DEFAULT 'AISHE_MASTER',
        source_version TEXT DEFAULT 'v1.0.0',
        code TEXT,
        name TEXT,
        contact_email TEXT,
        is_demo INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 24. Programs / Branches table (Institution-specific degrees & branches)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS programs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institution_id INTEGER NOT NULL,
        program_code TEXT NOT NULL, -- e.g. 'AIML', 'CSE', 'ECE', 'DS'
        program_name TEXT NOT NULL,
        degree_type TEXT DEFAULT 'B.Tech',
        total_years INTEGER DEFAULT 4,
        total_semesters INTEGER DEFAULT 8,
        is_demo INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE,
        UNIQUE(institution_id, program_code)
    );
    """)

    # 25. Academic Years table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS academic_years (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institution_id INTEGER NOT NULL,
        year_label TEXT NOT NULL, -- e.g. '2024-2025', '2025-2026'
        is_current INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE,
        UNIQUE(institution_id, year_label)
    );
    """)

    # 26. Curriculum Regulations / Versions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS curriculum_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institution_id INTEGER NOT NULL,
        program_id INTEGER NOT NULL,
        version_code TEXT NOT NULL, -- e.g. 'R20', 'R23', 'R24', 'Regulation 2025'
        version_name TEXT NOT NULL,
        effective_year TEXT,
        approval_status TEXT DEFAULT 'approved', -- 'draft', 'parsed', 'pending_review', 'approved', 'published'
        approved_by INTEGER,
        approved_at TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        is_demo INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE,
        FOREIGN KEY (program_id) REFERENCES programs (id) ON DELETE CASCADE,
        UNIQUE(institution_id, program_id, version_code)
    );
    """)

    # 27. Curriculum Modules / Units table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        module_number INTEGER NOT NULL,
        module_name TEXT NOT NULL,
        description TEXT,
        estimated_hours REAL DEFAULT 8.0,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
        UNIQUE(subject_id, module_number)
    );
    """)

    # 28. Curriculum Topics table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        topic_name TEXT NOT NULL,
        description TEXT,
        difficulty TEXT DEFAULT 'Intermediate', -- 'Beginner', 'Intermediate', 'Advanced'
        order_number INTEGER DEFAULT 1,
        prerequisites TEXT,
        FOREIGN KEY (module_id) REFERENCES modules (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)

    # 29. Learning Objectives table (Grounded Bloom Taxonomy)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS learning_objectives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER NOT NULL,
        objective_text TEXT NOT NULL,
        bloom_level TEXT DEFAULT 'Understand', -- 'Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'
        FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE
    );
    """)

    # 30. Authorized Learning Resources table (Private storage + copyright check)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS learning_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institution_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        module_id INTEGER,
        topic_id INTEGER,
        title TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT,
        resource_type TEXT DEFAULT 'textbook', -- 'textbook', 'pdf', 'lecture_notes', 'lab_manual', 'reference_doc', 'oer'
        source TEXT,
        authorization_status TEXT DEFAULT 'authorized', -- 'authorized', 'pending_verification', 'rejected'
        copyright_acknowledged INTEGER DEFAULT 1,
        uploaded_by INTEGER,
        version TEXT DEFAULT '1.0',
        is_demo INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)

    # 31. Document Chunks table (Grounded Retrieval Store with page/section provenance)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS document_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        module_id INTEGER,
        topic_id INTEGER,
        page_number INTEGER,
        section_heading TEXT,
        chunk_text TEXT NOT NULL,
        token_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (resource_id) REFERENCES learning_resources (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)

    # 32. Grounded AI Questions / Assessments (Strict syllabus & resource provenance)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS grounded_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL,
        module_id INTEGER,
        topic_id INTEGER,
        quiz_id INTEGER,
        question_text TEXT NOT NULL,
        question_type TEXT DEFAULT 'MCQ', -- 'MCQ', 'TrueFalse', 'ShortAnswer', 'Scenario', 'Numerical'
        option_a TEXT,
        option_b TEXT,
        option_c TEXT,
        option_d TEXT,
        correct_answer TEXT NOT NULL,
        explanation TEXT,
        difficulty TEXT DEFAULT 'Intermediate',
        source_reference TEXT,
        source_resource_id INTEGER,
        source_page INTEGER,
        generation_method TEXT DEFAULT 'grounded_rag',
        approval_status TEXT DEFAULT 'approved', -- 'draft', 'pending_faculty_review', 'approved', 'rejected'
        reviewed_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE
    );
    """)

    # 33. Student Subject Relational Performance (Curriculum-agnostic)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_subject_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        attendance REAL DEFAULT 75.0,
        assessment_score REAL DEFAULT 65.0,
        assignment_score REAL DEFAULT 70.0,
        quiz_score REAL DEFAULT 65.0,
        lab_score REAL DEFAULT 70.0,
        overall_score REAL DEFAULT 67.0,
        mastery_score REAL DEFAULT 65.0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
        UNIQUE(student_id, subject_id)
    );
    """)

    # 34. Student Topic Mastery (Dynamic adaptive tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_topic_mastery (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        mastery_score REAL DEFAULT 50.0,
        quiz_score REAL DEFAULT 0.0,
        attempts INTEGER DEFAULT 0,
        time_spent_minutes REAL DEFAULT 0.0,
        status TEXT DEFAULT 'in_progress', -- 'not_started', 'in_progress', 'mastered', 'needs_revision'
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
        UNIQUE(student_id, topic_id)
    );
    """)

    # 35. Student Activity Logs (Granular telemetry)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        activity_type TEXT NOT NULL, -- 'lesson_opened', 'lesson_completed', 'resource_viewed', 'quiz_started', 'quiz_completed', 'recommendation_accepted', 'recommendation_completed'
        subject_id INTEGER,
        module_id INTEGER,
        topic_id INTEGER,
        resource_id INTEGER,
        quiz_id INTEGER,
        score REAL,
        duration_seconds INTEGER DEFAULT 0,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
    );
    """)

    # 36. Curriculum Import Batches (Admin preview and approval state machine)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS curriculum_import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        institution_id INTEGER NOT NULL,
        program_id INTEGER NOT NULL,
        version_code TEXT NOT NULL,
        file_name TEXT NOT NULL,
        status TEXT DEFAULT 'approved', -- 'uploaded', 'parsed', 'validation_error', 'pending_review', 'approved', 'published'
        total_records INTEGER DEFAULT 0,
        valid_records INTEGER DEFAULT 0,
        error_records INTEGER DEFAULT 0,
        error_log TEXT,
        uploaded_by INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE
    );
    """)

    # 37. Audit Logs (Enterprise security and trace provenance)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_email TEXT,
        role TEXT,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id TEXT,
        institution_id INTEGER,
        details TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 38. Model Predictions History & Audit
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS model_predictions_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        model_type TEXT NOT NULL, -- 'QML_5Qubit_VQC', 'QML_8Qubit_VQC', 'Classical_GradientBoosting', 'Classical_RandomForest'
        model_version TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        risk_score REAL NOT NULL,
        confidence REAL NOT NULL,
        features_json TEXT NOT NULL,
        probabilities_json TEXT NOT NULL,
        risk_drivers_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
    );
    """)

    # 39. Remedial Interventions table (Teacher 1-Click Action & Lifecycle Tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interventions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        teacher_id INTEGER,
        institution_id INTEGER,
        subject_id INTEGER,
        risk_level TEXT DEFAULT 'Medium Risk', -- 'Low Risk', 'Medium Risk', 'High Risk'
        action_type TEXT DEFAULT 'Remedial Quiz', -- 'Remedial Quiz', 'Targeted Drill', 'Mentorship Session', 'Attendance Warning', 'Study Material'
        title TEXT NOT NULL,
        category TEXT DEFAULT 'Academic Support',
        priority TEXT DEFAULT 'High', -- 'Low', 'Medium', 'High', 'Urgent'
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Assigned', -- 'Assigned', 'In Progress', 'Completed', 'Resolved'
        notes TEXT,
        due_date TEXT,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE SET NULL,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE SET NULL,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE
    );
    """)

    # Safe Column Migrations for Users, Teachers, Students, Subjects
    cursor.execute("PRAGMA table_info(users)")
    u_cols = [c["name"] for c in cursor.fetchall()]
    if "institution_id" not in u_cols:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN institution_id INTEGER")
        except Exception:
            pass

    cursor.execute("PRAGMA table_info(teachers)")
    t_cols = [c["name"] for c in cursor.fetchall()]
    if "institution_id" not in t_cols:
        try:
            cursor.execute("ALTER TABLE teachers ADD COLUMN institution_id INTEGER")
        except Exception:
            pass
    if "program_id" not in t_cols:
        try:
            cursor.execute("ALTER TABLE teachers ADD COLUMN program_id INTEGER")
        except Exception:
            pass

    cursor.execute("PRAGMA table_info(students)")
    s_cols = [c["name"] for c in cursor.fetchall()]
    if "institution_id" not in s_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN institution_id INTEGER")
        except Exception:
            pass
    if "program_id" not in s_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN program_id INTEGER")
        except Exception:
            pass
    if "curriculum_version_id" not in s_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN curriculum_version_id INTEGER")
        except Exception:
            pass
    if "is_demo" not in s_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN is_demo INTEGER DEFAULT 0")
        except Exception:
            pass
    if "learning_streak" not in s_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN learning_streak INTEGER DEFAULT 3")
        except Exception:
            pass
    if "xp_points" not in s_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN xp_points INTEGER DEFAULT 450")
        except Exception:
            pass
    if "teacher_id" not in s_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN teacher_id INTEGER REFERENCES teachers (id)")
        except Exception:
            pass

    # Ensure teacher_assignments table is populated from teachers table if empty
    try:
        cursor.execute("SELECT COUNT(*) FROM teacher_assignments")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT OR IGNORE INTO teacher_assignments (teacher_id, branch, year, section, academic_year, is_class_teacher)
            SELECT id, branch, year, section, '2024-2025', 1
            FROM teachers
            WHERE branch IS NOT NULL AND year IS NOT NULL AND section IS NOT NULL
            """)
    except Exception:
        pass

    # Auto-link students.teacher_id to their assigned class teacher
    try:
        cursor.execute("""
        UPDATE students
        SET teacher_id = (
            SELECT ta.teacher_id
            FROM teacher_assignments ta
            WHERE UPPER(ta.branch) = UPPER(students.branch)
              AND UPPER(ta.year) = UPPER(students.year)
              AND UPPER(ta.section) = UPPER(students.section)
            LIMIT 1
        )
        WHERE teacher_id IS NULL
        """)
    except Exception:
        pass

    # Ensure interventions table has all required columns
    cursor.execute("PRAGMA table_info(interventions)")
    it_cols = [c["name"] for c in cursor.fetchall()]
    if it_cols:
        for missing_col, col_type in [
            ("institution_id", "INTEGER"),
            ("subject_id", "INTEGER"),
            ("action_type", "TEXT DEFAULT 'Remedial Quiz'"),
            ("risk_level", "TEXT DEFAULT 'Medium Risk'"),
            ("due_date", "TEXT"),
            ("completed_at", "TIMESTAMP"),
            ("notes", "TEXT")
        ]:
            if missing_col not in it_cols:
                try:
                    cursor.execute(f"ALTER TABLE interventions ADD COLUMN {missing_col} {col_type}")
                except Exception:
                    pass

    # 39. Badges & Gamification Achievements table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        badge_key TEXT NOT NULL,
        badge_name TEXT NOT NULL,
        badge_icon TEXT NOT NULL,
        badge_color TEXT DEFAULT '#818cf8',
        description TEXT NOT NULL,
        unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        UNIQUE(student_id, badge_key)
    );
    """)

    # 40. Interactive Practice Coding Challenges table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coding_challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER,
        title TEXT NOT NULL,
        language TEXT DEFAULT 'python', -- 'python', 'sql', 'javascript'
        difficulty TEXT DEFAULT 'Beginner', -- 'Beginner', 'Intermediate', 'Advanced'
        category TEXT DEFAULT 'Algorithms',
        description TEXT NOT NULL,
        starter_code TEXT NOT NULL,
        solution_code TEXT,
        test_cases_json TEXT NOT NULL, -- [{"input": "...", "expected": "...", "hidden": false}]
        xp_reward INTEGER DEFAULT 100,
        FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE SET NULL
    );
    """)

    # 41. Coding Submissions & Test Runs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coding_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        challenge_id INTEGER NOT NULL,
        code_submitted TEXT NOT NULL,
        passed_tests INTEGER DEFAULT 0,
        total_tests INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Passed', -- 'Passed', 'Failed', 'SyntaxError', 'RuntimeError'
        execution_time_ms REAL DEFAULT 0.0,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
        FOREIGN KEY (challenge_id) REFERENCES coding_challenges (id) ON DELETE CASCADE
    );
    """)

    # 42. Dataset Versions table (Master Dataset Provenance & Failover)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dataset_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        source TEXT DEFAULT 'AISHE_PORTAL',
        version TEXT NOT NULL,
        row_count INTEGER DEFAULT 0,
        valid_count INTEGER DEFAULT 0,
        invalid_count INTEGER DEFAULT 0,
        duplicate_count INTEGER DEFAULT 0,
        imported_by INTEGER,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active' -- 'active', 'archived', 'failed'
    );
    """)

    # 43. Classes table (Institution -> Class -> Student & Teacher -> Class -> Students hierarchy)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER,
        institution_id INTEGER NOT NULL,
        regulation TEXT DEFAULT 'R23',
        branch TEXT NOT NULL,
        year TEXT NOT NULL,
        semester INTEGER DEFAULT 1,
        section TEXT NOT NULL,
        academic_year TEXT DEFAULT '2024-2025',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE SET NULL,
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE,
        UNIQUE(institution_id, regulation, branch, year, semester, section, academic_year)
    );
    """)

    cursor.execute("PRAGMA table_info(subjects)")
    subj_cols = [c["name"] for c in cursor.fetchall()]
    if "institution_id" not in subj_cols:
        try:
            cursor.execute("ALTER TABLE subjects ADD COLUMN institution_id INTEGER")
        except Exception:
            pass
    if "program_id" not in subj_cols:
        try:
            cursor.execute("ALTER TABLE subjects ADD COLUMN program_id INTEGER")
        except Exception:
            pass
    if "curriculum_version_id" not in subj_cols:
        try:
            cursor.execute("ALTER TABLE subjects ADD COLUMN curriculum_version_id INTEGER")
        except Exception:
            pass
    if "status" not in subj_cols:
        try:
            cursor.execute("ALTER TABLE subjects ADD COLUMN status TEXT DEFAULT 'published'")
        except Exception:
            pass

    # Ensure students table has class_id, regulation, and academic_year
    cursor.execute("PRAGMA table_info(students)")
    st_cols = [c["name"] for c in cursor.fetchall()]
    if "class_id" not in st_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN class_id INTEGER")
        except Exception:
            pass
    if "regulation" not in st_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN regulation TEXT DEFAULT 'R23'")
        except Exception:
            pass
    if "academic_year" not in st_cols:
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN academic_year TEXT DEFAULT '2024-2025'")
        except Exception:
            pass

    # Ensure institutions table has all master fields
    cursor.execute("PRAGMA table_info(institutions)")
    inst_cols = [c["name"] for c in cursor.fetchall()]
    for field_name, field_def in [
        ("aishe_code", "TEXT"),
        ("institution_name", "TEXT"),
        ("institution_type", "TEXT DEFAULT 'University'"),
        ("university_name", "TEXT"),
        ("state", "TEXT DEFAULT 'Andhra Pradesh'"),
        ("district", "TEXT DEFAULT 'Visakhapatnam'"),
        ("city", "TEXT DEFAULT 'Visakhapatnam'"),
        ("website", "TEXT"),
        ("status", "TEXT DEFAULT 'active'"),
        ("source", "TEXT DEFAULT 'AISHE_MASTER'"),
        ("source_version", "TEXT DEFAULT 'v1.0.0'"),
        ("updated_at", "TIMESTAMP")
    ]:
        if field_name not in inst_cols:
            try:
                cursor.execute(f"ALTER TABLE institutions ADD COLUMN {field_name} {field_def}")
            except Exception as e:
                print(f"[Migration Warning]: {e}")

    # Auto-synchronize legacy name/code with institution_name/aishe_code
    try:
        cursor.execute("UPDATE institutions SET institution_name = name WHERE institution_name IS NULL AND name IS NOT NULL")
        cursor.execute("UPDATE institutions SET aishe_code = code WHERE aishe_code IS NULL AND code IS NOT NULL")
        cursor.execute("UPDATE institutions SET name = institution_name WHERE name IS NULL AND institution_name IS NOT NULL")
        cursor.execute("UPDATE institutions SET code = aishe_code WHERE code IS NULL AND aishe_code IS NOT NULL")
    except Exception:
        pass

    # High-Performance Indexes for Institution Master & Hierarchy
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_inst_aishe_unique ON institutions (aishe_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_name ON institutions (institution_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_univ ON institutions (university_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_state_dist ON institutions (state, district);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_type ON institutions (institution_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_status ON institutions (status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dataset_ver_status ON dataset_versions (status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_inst_sec ON classes (institution_id, branch, year, section);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_teacher ON classes (teacher_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_class ON students (class_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_inst ON students (institution_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_teacher_assignments_lookup ON teacher_assignments (teacher_id, branch, year, section);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_teacher ON students (teacher_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_cohort ON students (branch, year, section);")

    # High-Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subj_inst_prog ON subjects (institution_id, program_id, year, semester);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_modules_subj ON modules (subject_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_mod ON topics (module_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_subj ON topics (subject_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_res_subj ON learning_resources (subject_id, authorization_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_subj_top ON document_chunks (subject_id, topic_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stud_subj_perf ON student_subject_performance (student_id, subject_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stud_top_mast ON student_topic_mastery (student_id, topic_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_act_logs_stud ON student_activity_logs (student_id, activity_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_inst ON audit_logs (institution_id, action);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_student_badges ON student_badges (student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_code_challenges ON coding_challenges (subject_id, difficulty);")

    conn.commit()
    conn.close()


def log_audit_event(user_id=None, user_email=None, role=None, action="", entity_type=None, entity_id=None, institution_id=None, details=""):
    """Records an immutable audit trail entry."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO audit_logs (user_id, user_email, role, action, entity_type, entity_id, institution_id, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, user_email, role, action, entity_type, str(entity_id) if entity_id else None, institution_id, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Audit Log Error]: {e}")


def seed_demo_data():
    """Initializes schema and seeds baseline demo data if necessary."""
    init_db()
    from data.seed_academic_data import seed_academic_curriculum
    seed_academic_curriculum()

if __name__ == "__main__":
    init_db()
    seed_demo_data()
