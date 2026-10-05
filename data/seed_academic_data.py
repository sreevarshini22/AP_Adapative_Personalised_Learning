"""
Comprehensive Multi-Institution Academic Curriculum Seed Script
AP Adaptive & Personalised Learning Platform

Seeds:
1. Multi-Institution Entities:
   - Andhra University College of Engineering (Autonomous) [AU_ENG]
   - JNTUK College of Engineering [JNTUK_ENG]
   - Sri Venkateswara University College of Engineering [SVU_ENG]
   - AP State Higher Education Council [AP_SCHE]
2. Role-Based User Accounts:
   - Super Admin / State Admin: state.admin@sche.ap.gov.in (admin123)
   - Institution Admin AU: admin@au.edu.in (admin123)
   - Institution Admin JNTUK: admin@jntuk.edu.in (admin123)
   - Faculty AU: prof.murthy@au.edu.in / teacher@example.com (teacher123)
   - Faculty JNTUK: dr.venkatesh@jntuk.edu.in (teacher123)
   - Student AU (College A, AIML): student.au@au.edu.in (student123)
   - Student JNTUK (College B, ECE): student.jntuk@jntuk.edu.in (student123)
   - Default Demo Student (CSE): student@example.com (student123)
3. Dynamic Curriculum Hierarchy for Critical Test Cases:
   - College A: AIML -> Year 3 -> Sem 1 -> Machine Learning, DBMS, Computer Networks
   - College B: ECE -> Year 3 -> Sem 1 -> Signals and Systems, VLSI Design, Digital Communication
4. Modules, Topics, Learning Objectives, Authorized Resources, Document Chunks, Grounded Questions,
   Student Relational Performances, and Topic Masteries.
"""

import os
import sys
import sqlite3
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import get_db_connection, init_db


def seed_academic_curriculum():
    init_db()
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if institutions already populated
    cursor.execute("SELECT COUNT(*) FROM institutions")
    inst_count = cursor.fetchone()[0]

    if inst_count == 0:
        conn.close()
        # Import master real universities and colleges dataset
        from backend.institution_service import import_institution_dataset
        csv_dataset_path = os.path.join(PROJECT_ROOT, "data", "master_institutions_dataset.csv")
        if os.path.exists(csv_dataset_path):
            import_institution_dataset(
                file_bytes_or_path=csv_dataset_path,
                filename="master_institutions_dataset.csv",
                imported_by=1,
                source="AISHE_PORTAL",
                version_tag="v1.0.0"
            )
        conn = get_db_connection()
        cursor = conn.cursor()

    # Shared default passwords
    admin_pwd = generate_password_hash("admin123")
    teacher_pwd = generate_password_hash("teacher123")
    student_pwd = generate_password_hash("student123")

    # =========================================================================
    # 1. INSTITUTIONS
    # =========================================================================
    institutions_data = [
        ("AU_ENG", "Andhra University College of Engineering (Autonomous)", "Autonomous University", "Andhra Pradesh", "Visakhapatnam", "https://andhrauniversity.edu.in", "contact@au.edu.in", "U-0003"),
        ("JNTUK_ENG", "JNTUK University College of Engineering", "State University", "Andhra Pradesh", "Kakinada", "https://jntuk.edu.in", "contact@jntuk.edu.in", "U-0017"),
        ("SVU_ENG", "Sri Venkateswara University College of Engineering", "State University", "Andhra Pradesh", "Tirupati", "https://svuniversity.edu.in", "contact@svu.edu.in", "U-0036"),
        ("AP_SCHE", "Andhra Pradesh State Higher Education Council Portal", "State Directorate", "Andhra Pradesh", "Amaravati", "https://apsche.ap.gov.in", "state.admin@sche.ap.gov.in", "AP-SCHE-01")
    ]

    inst_map = {}
    for code, name, itype, state, dist, web, email, aishe in institutions_data:
        cursor.execute("SELECT id FROM institutions WHERE code = ? OR aishe_code = ?", (code, aishe))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO institutions (code, name, institution_name, aishe_code, institution_type, state, district, city, website, contact_email, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (code, name, name, aishe, itype, state, dist, dist, web, email))
            inst_id = cursor.lastrowid
        else:
            inst_id = row["id"]
            cursor.execute("""
            UPDATE institutions SET
                aishe_code = COALESCE(aishe_code, ?),
                institution_name = COALESCE(institution_name, ?),
                code = COALESCE(code, ?),
                name = COALESCE(name, ?)
            WHERE id = ?
            """, (aishe, name, code, name, inst_id))
        inst_map[code] = inst_id

    au_id = inst_map["AU_ENG"]
    jntuk_id = inst_map["JNTUK_ENG"]
    sche_id = inst_map["AP_SCHE"]

    # =========================================================================
    # 2. PROGRAMS
    # =========================================================================
    programs_data = [
        (au_id, "AIML", "B.Tech in Artificial Intelligence & Machine Learning", "B.Tech", 4, 8),
        (au_id, "CSE", "B.Tech in Computer Science & Engineering", "B.Tech", 4, 8),
        (jntuk_id, "ECE", "B.Tech in Electronics & Communication Engineering", "B.Tech", 4, 8),
        (jntuk_id, "CSE", "B.Tech in Computer Science & Engineering", "B.Tech", 4, 8),
        (inst_map["SVU_ENG"], "EEE", "B.Tech in Electrical & Electronics Engineering", "B.Tech", 4, 8)
    ]

    prog_map = {}
    for i_id, p_code, p_name, deg, yrs, sems in programs_data:
        cursor.execute("SELECT id FROM programs WHERE institution_id = ? AND program_code = ?", (i_id, p_code))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO programs (institution_id, program_code, program_name, degree_type, total_years, total_semesters, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (i_id, p_code, p_name, deg, yrs, sems))
            p_id = cursor.lastrowid
        else:
            p_id = row["id"]
        prog_map[(i_id, p_code)] = p_id

    au_aiml_prog = prog_map[(au_id, "AIML")]
    jntuk_ece_prog = prog_map[(jntuk_id, "ECE")]

    # =========================================================================
    # 3. CURRICULUM VERSIONS
    # =========================================================================
    versions_data = [
        (au_id, au_aiml_prog, "R24", "AU Autonomous AIML Regulation 2024", "2024-2028", "published"),
        (jntuk_id, jntuk_ece_prog, "R23", "JNTUK Regulation 2023 (ECE)", "2023-2027", "published")
    ]
    version_map = {}
    for i_id, p_id, v_code, v_name, eff_yr, status in versions_data:
        cursor.execute("SELECT id FROM curriculum_versions WHERE institution_id = ? AND program_id = ? AND version_code = ?", (i_id, p_id, v_code))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO curriculum_versions (institution_id, program_id, version_code, version_name, effective_year, approval_status, is_active, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            """, (i_id, p_id, v_code, v_name, eff_yr, status))
            v_id = cursor.lastrowid
        else:
            v_id = row["id"]
        version_map[(i_id, p_id, v_code)] = v_id

    au_v_id = version_map[(au_id, au_aiml_prog, "R24")]
    jntuk_v_id = version_map[(jntuk_id, jntuk_ece_prog, "R23")]

    # =========================================================================
    # User Accounts
    users_to_create = [
        # Super / State Admin
        ("state.admin@sche.ap.gov.in", generate_password_hash("StateAdmin@2024"), "state_admin", "Dr. AP State Higher Education Secretary", sche_id),
        # Institution Admins
        ("admin@au.edu.in", generate_password_hash("AdminAU@2024"), "institution_admin", "AU Academic Dean", au_id),
        ("admin@jntuk.edu.in", generate_password_hash("AdminJNTUK@2024"), "institution_admin", "JNTUK Academic Registrar", jntuk_id),
        # Faculty
        ("prof.murthy@au.edu.in", generate_password_hash("ProfMurthy@2024"), "teacher", "Dr. K. Srinivas Murthy", au_id),
        ("dr.venkatesh@jntuk.edu.in", generate_password_hash("DrVenkatesh@2024"), "teacher", "Dr. P. Venkatesh", jntuk_id),
        ("teacher@example.com", generate_password_hash("teacher123"), "teacher", "Dr. Faculty Advisor", au_id),
        # Students
        ("student.au@au.edu.in", generate_password_hash("StudentAU@2024"), "student", "Aarav Sharma", au_id),
        ("student.jntuk@jntuk.edu.in", generate_password_hash("StudentJNTUK@2024"), "student", "Bhavya Reddy", jntuk_id),
        ("student@example.com", generate_password_hash("student123"), "student", "Student Demo", au_id)
    ]

    user_id_map = {}
    for email, pwd, role, name, inst_id in users_to_create:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email.lower(),))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO users (email, password_hash, role, full_name, institution_id)
            VALUES (?, ?, ?, ?, ?)
            """, (email.lower(), pwd, role, name, inst_id))
            u_id = cursor.lastrowid
        else:
            u_id = row["id"]
            cursor.execute("UPDATE users SET password_hash = ?, institution_id = COALESCE(?, institution_id), role = ?, full_name = ? WHERE id = ?", (pwd, inst_id, role, name, u_id))
        user_id_map[email.lower()] = u_id

    # Seed Teachers records
    teachers_records = [
        (user_id_map["prof.murthy@au.edu.in"], "Dr. K. Srinivas Murthy", "prof.murthy@au.edu.in", "AIML", "Artificial Intelligence", "Professor & Head", "3rd Year", "A", au_id, au_aiml_prog),
        (user_id_map["dr.venkatesh@jntuk.edu.in"], "Dr. P. Venkatesh", "dr.venkatesh@jntuk.edu.in", "ECE", "Electronics & Communication", "Professor", "3rd Year", "A", jntuk_id, jntuk_ece_prog),
        (user_id_map["teacher@example.com"], "Dr. Faculty Advisor", "teacher@example.com", "CSE", "Computer Science", "Associate Professor", "3rd Year", "A", au_id, None)
    ]
    teacher_id_map = {}
    for uid, name, email, branch, dept, desig, yr, sec, inst_id, prog_id in teachers_records:
        cursor.execute("SELECT id FROM teachers WHERE LOWER(email) = ?", (email.lower(),))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO teachers (user_id, full_name, email, branch, department, designation, year, section, institution_id, program_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (uid, name, email.lower(), branch, dept, desig, yr, sec, inst_id, prog_id))
            t_id = cursor.lastrowid
        else:
            t_id = row["id"]
            cursor.execute("""
            UPDATE teachers SET institution_id = ?, program_id = ?, department = ?, designation = ? WHERE id = ?
            """, (inst_id, prog_id, dept, desig, t_id))
        teacher_id_map[email.lower()] = t_id

    # Seed Classes (Institution -> Class -> Student & Teacher -> Class -> Students hierarchy)
    classes_data = [
        (teacher_id_map["prof.murthy@au.edu.in"], au_id, "R24", "AIML", "3rd Year", 1, "A", "2024-2025"),
        (teacher_id_map["dr.venkatesh@jntuk.edu.in"], jntuk_id, "R23", "ECE", "3rd Year", 1, "A", "2024-2025"),
        (teacher_id_map["teacher@example.com"], au_id, "R23", "CSE", "3rd Year", 5, "A", "2024-2025")
    ]
    class_id_map = {}
    for t_id, i_id, reg, br, yr, sem, sec, ac_yr in classes_data:
        cursor.execute("""
        SELECT id FROM classes 
        WHERE institution_id = ? AND regulation = ? AND branch = ? AND year = ? AND semester = ? AND section = ? AND academic_year = ?
        """, (i_id, reg, br, yr, sem, sec, ac_yr))
        c_row = cursor.fetchone()
        if not c_row:
            cursor.execute("""
            INSERT INTO classes (teacher_id, institution_id, regulation, branch, year, semester, section, academic_year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (t_id, i_id, reg, br, yr, sem, sec, ac_yr))
            class_id = cursor.lastrowid
        else:
            class_id = c_row["id"]
            cursor.execute("UPDATE classes SET teacher_id = ? WHERE id = ?", (t_id, class_id))
        class_id_map[(i_id, br, yr, sec)] = class_id

    # Seed Teacher Class Assignments (Explicit teacher_assignments mapping)
    teacher_assignments_data = [
        (teacher_id_map["prof.murthy@au.edu.in"], "AIML", "3rd Year", "A", "2024-2025", 1),
        (teacher_id_map["dr.venkatesh@jntuk.edu.in"], "ECE", "3rd Year", "A", "2024-2025", 1),
        (teacher_id_map["teacher@example.com"], "CSE", "3rd Year", "A", "2024-2025", 1)
    ]
    for t_id, br, yr, sec, ac_yr, is_ct in teacher_assignments_data:
        cursor.execute("""
        INSERT OR REPLACE INTO teacher_assignments (teacher_id, branch, year, section, academic_year, is_class_teacher)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (t_id, br, yr, sec, ac_yr, is_ct))

    # Seed Students records
    students_records = [
        # Student A: College A (AU - AIML - 3rd Year - Sem 1) -> Assigned to Prof. Murthy
        (user_id_map["student.au@au.edu.in"], "Aarav Sharma", "21AUAIML001", "student.au@au.edu.in", "3rd Year", "AIML", "A", 1, 78.5, 62.0, 58.0, 70.0, 68.0, 65.0, 72.0, 68.0, 64.0, 62.0, 8.5, 68.0, 72.0, 58.0, 4, au_id, au_aiml_prog, au_v_id, class_id_map.get((au_id, "AIML", "3rd Year", "A")), "R24", "2024-2025", teacher_id_map["prof.murthy@au.edu.in"]),
        # Student B: College B (JNTUK - ECE - 3rd Year - Sem 1) -> Assigned to Dr. Venkatesh
        (user_id_map["student.jntuk@jntuk.edu.in"], "Bhavya Reddy", "21JNTUKECE042", "student.jntuk@jntuk.edu.in", "3rd Year", "ECE", "A", 1, 84.0, 70.0, 74.0, 65.0, 68.0, 70.0, 75.0, 72.0, 70.0, 72.0, 9.0, 75.0, 76.0, 65.0, 5, jntuk_id, jntuk_ece_prog, jntuk_v_id, class_id_map.get((jntuk_id, "ECE", "3rd Year", "A")), "R23", "2024-2025", teacher_id_map["dr.venkatesh@jntuk.edu.in"]),
        # Demo Student: CSE - 3rd Year - Sem 5 -> Assigned to Default Faculty (teacher@example.com)
        (user_id_map["student@example.com"], "Student Demo", "21AP001", "student@example.com", "3rd Year", "CSE", "A", 5, 82.0, 68.0, 70.0, 72.0, 68.0, 70.0, 75.0, 74.0, 68.0, 70.0, 7.5, 65.0, 70.0, 62.0, 3, au_id, None, None, class_id_map.get((au_id, "CSE", "3rd Year", "A")), "R23", "2024-2025", teacher_id_map["teacher@example.com"])
    ]

    student_id_map = {}
    for uid, name, roll, email, yr, branch, sec, sem, att, m_sc, p_sc, pr_sc, ds_sc, db_sc, cm_sc, as_sc, qz_sc, ex_sc, sh, la, pp, op, ls, inst_id, prog_id, v_id, cls_id, reg, ac_yr, t_id in students_records:
        cursor.execute("SELECT id FROM students WHERE roll_no = ? OR LOWER(email) = ?", (roll, email.lower()))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO students (
                user_id, full_name, roll_no, email, year, branch, section, semester,
                attendance, mathematics_score, physics_score, programming_score,
                data_structures_score, database_score, communication_score,
                assignment_score, quiz_score, exam_score, study_hours,
                learning_activity, previous_performance, overall_progress,
                learning_streak, institution_id, program_id, curriculum_version_id,
                class_id, regulation, academic_year, teacher_id, is_demo
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, 1
            )
            """, (
                uid, name, roll, email.lower(), yr, branch, sec, sem,
                att, m_sc, p_sc, pr_sc, ds_sc, db_sc, cm_sc, as_sc, qz_sc, ex_sc, sh, la, pp, op, ls, inst_id, prog_id, v_id,
                cls_id, reg, ac_yr, t_id
            ))
            s_id = cursor.lastrowid
        else:
            s_id = row["id"]
            cursor.execute("""
            UPDATE students SET
                user_id = ?, full_name = ?, roll_no = ?, year = ?, branch = ?, section = ?, semester = ?,
                institution_id = ?, program_id = ?, curriculum_version_id = ?,
                class_id = ?, regulation = ?, academic_year = ?, teacher_id = ?
            WHERE id = ?
            """, (uid, name, roll, yr, branch, sec, sem, inst_id, prog_id, v_id, cls_id, reg, ac_yr, t_id, s_id))
        student_id_map[roll] = s_id


    # =========================================================================
    # 5. DYNAMIC SUBJECTS, MODULES & TOPICS (CRITICAL TEST CASE: Requirement 43)
    # =========================================================================

    # --- COLLEGE A (AU AIML 3rd Year Sem 1) ---
    college_a_subjects = [
        ("CS301-AU", "Machine Learning", "AIML", "3rd Year", 1, 4, "theory", "Supervised, unsupervised, ensemble algorithms, and quantum learning foundations.", au_id, au_aiml_prog, au_v_id, [
            (1, "Supervised Learning & Decision Trees", "Tree-based induction, information gain, and ensemble architectures.", [
                ("Decision Trees", "ID3 and CART recursive partitioning algorithms.", "Beginner", "Textbook of Machine Learning by Tom Mitchell, Pages 112-114", "Explain the recursive splitting mechanism in decision tree induction."),
                ("Entropy and Information Gain", "Information theoretic reduction of impurity.", "Intermediate", "Textbook of Machine Learning by Tom Mitchell, Pages 115-118", "Compute entropy given sample class distributions."),
                ("Random Forests Ensemble", "Bagging, bootstrap aggregation, and out-of-bag error estimation.", "Intermediate", "Applied Machine Learning by Hastie et al., Pages 85-92", "Explain variance reduction in random forest ensembles.")
            ]),
            (2, "Probabilistic & Quantum Foundations", "Bayes classification, gradient descent, and variational quantum circuits.", [
                ("Bayesian Classification", "Naive Bayes, posterior estimation, and Laplace smoothing.", "Intermediate", "Pattern Recognition & ML by Bishop, Pages 140-146", "Derive Maximum A Posteriori (MAP) classification rule."),
                ("Variational Quantum Circuits", "AngleEmbedding, Parameterized Quantum Circuits (PQC), and VQC optimization.", "Advanced", "Quantum Machine Learning with PennyLane by Schuld, Pages 45-52", "Formulate parameterized Pauli-Z expectation measurements in 5-qubit VQC.")
            ])
        ]),
        ("CS302-AU", "Database Management Systems", "AIML", "3rd Year", 1, 3, "theory", "Relational schema design, normalization, ACID transactions, and query optimization.", au_id, au_aiml_prog, au_v_id, [
            (1, "Relational Modeling & Schema Design", "ER modeling, relational algebra, and schema normalization.", [
                ("Entity-Relationship Modeling", "Entities, attributes, cardinality ratios, and ER diagrams.", "Beginner", "Database System Concepts by Silberschatz, Pages 55-64", "Design conceptual schema for enterprise domain."),
                ("3NF and BCNF Normalization", "Functional dependencies, lossless joins, and dependency preservation.", "Intermediate", "Database System Concepts by Silberschatz, Pages 80-92", "Decompose relational schemas into Boyce-Codd Normal Form.")
            ]),
            (2, "Transaction & Concurrency Protocols", "ACID guarantees, two-phase locking, and write-ahead logging.", [
                ("ACID Properties", "Atomicity, Consistency, Isolation, and Durability.", "Beginner", "Database System Concepts by Silberschatz, Pages 180-188", "Explain how write-ahead logging ensures durability."),
                ("Two-Phase Locking Protocol", "Strict 2PL, shared/exclusive locks, and deadlock prevention.", "Advanced", "Database System Concepts by Silberschatz, Pages 210-220", "Analyze conflict serializability under two-phase locking.")
            ])
        ]),
        ("CS303-AU", "Computer Networks", "AIML", "3rd Year", 1, 3, "theory", "OSI/TCP-IP layering, routing protocols, flow control, and network security.", au_id, au_aiml_prog, au_v_id, [
            (1, "Network Layer & Routing", "IP addressing, subnets, and routing protocols.", [
                ("IP Addressing and CIDR", "IPv4/IPv6 headers, subnet masks, and longest prefix match.", "Beginner", "Computer Networking: Top Down Approach by Kurose, Pages 95-104", "Calculate subnet broadcast and network addresses."),
                ("OSPF Routing Protocol", "Link-state advertisements and Dijkstra shortest path routing.", "Intermediate", "Computer Networking: Top Down Approach by Kurose, Pages 120-130", "Construct link-state databases and routing tables.")
            ]),
            (2, "Transport Layer Protocols", "TCP flow control, congestion window, and UDP mechanics.", [
                ("TCP Congestion Control", "Slow start, congestion avoidance, fast retransmit, and fast recovery.", "Intermediate", "Computer Networking: Top Down Approach by Kurose, Pages 230-245", "Trace congestion window dynamics during packet loss.")
            ])
        ])
    ]

    # --- COLLEGE B (JNTUK ECE 3rd Year Sem 1) ---
    college_b_subjects = [
        ("EC301-JNTUK", "Signals and Systems", "ECE", "3rd Year", 1, 4, "theory", "Continuous & discrete signal representations, Fourier, Laplace, and Z-transforms.", jntuk_id, jntuk_ece_prog, jntuk_v_id, [
            (1, "Continuous & Discrete Transforms", "Spectral analysis and transform domain representations.", [
                ("Continuous-Time Fourier Transform", "CTFT properties, duality, convolution, and frequency spectra.", "Intermediate", "Signals and Systems by Alan V. Oppenheim, Pages 204-212", "Evaluate frequency response of linear time-invariant systems."),
                ("Laplace Transform Analysis", "Bilateral Laplace transform, region of convergence (ROC), and stability.", "Intermediate", "Signals and Systems by Alan V. Oppenheim, Pages 230-240", "Determine system pole-zero stability in s-plane."),
                ("Z-Transform and ROC", "Discrete transform, inversion methods, and digital filter response.", "Advanced", "Signals and Systems by Alan V. Oppenheim, Pages 280-295", "Apply Z-transform to solve discrete linear difference equations.")
            ])
        ]),
        ("EC302-JNTUK", "VLSI Design", "ECE", "3rd Year", 1, 3, "theory", "MOS transistor theory, CMOS inverter layout, stick diagrams, and timing analysis.", jntuk_id, jntuk_ece_prog, jntuk_v_id, [
            (1, "CMOS Technology & Circuit Layout", "MOS physics, inverter transfer characteristics, and layout rules.", [
                ("MOS Transistor Operation", "Linear and saturation regimes, threshold voltage, and body effect.", "Beginner", "CMOS VLSI Design by Weste & Harris, Pages 42-50", "Derive drain current equation in saturation mode."),
                ("CMOS Inverter DC Characteristics", "Noise margins, switching threshold, and dynamic power dissipation.", "Intermediate", "CMOS VLSI Design by Weste & Harris, Pages 65-74", "Calculate symmetric CMOS inverter switching threshold."),
                ("Layout Design Rules & Stick Diagrams", "Lambda rules, Euler path logic layout, and DRC physical verification.", "Advanced", "CMOS VLSI Design by Weste & Harris, Pages 98-110", "Construct Euler path for optimal CMOS diffusion layout.")
            ])
        ]),
        ("EC303-JNTUK", "Digital Communication", "ECE", "3rd Year", 1, 3, "theory", "Pulse modulation, passband digital signaling, QPSK, QAM, and error rates.", jntuk_id, jntuk_ece_prog, jntuk_v_id, [
            (1, "Baseband & Passband Modulation", "PCM, QPSK, QAM, and noise analysis in AWGN channels.", [
                ("Pulse Code Modulation (PCM)", "Sampling theorem, uniform/non-uniform quantization, and companding.", "Beginner", "Digital Communications by Simon Haykin, Pages 110-122", "Determine signal-to-quantization noise ratio in PCM systems."),
                ("QPSK & QAM Constellations", "Phase shift keying, constellation diagrams, and bit error probability.", "Intermediate", "Digital Communications by Simon Haykin, Pages 160-175", "Calculate bit error rate (BER) over additive white Gaussian noise."),
                ("Information Theory & Shannon Limit", "Entropy, mutual information, and channel coding theorem.", "Advanced", "Digital Communications by Simon Haykin, Pages 210-225", "Compute channel capacity for AWGN bandwidth-constrained channel.")
            ])
        ])
    ]

    all_custom_subjects = college_a_subjects + college_b_subjects

    for s_code, s_name, branch, yr, sem, credits, stype, desc, i_id, p_id, v_id, modules_list in all_custom_subjects:
        cursor.execute("SELECT id FROM subjects WHERE subject_code = ?", (s_code,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO subjects (
                institution_id, program_id, curriculum_version_id, subject_code,
                subject_name, branch, year, semester, credits, subject_type, description, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published')
            """, (i_id, p_id, v_id, s_code, s_name, branch, yr, sem, credits, stype, desc))
            s_id = cursor.lastrowid
        else:
            s_id = row["id"]
            cursor.execute("""
            UPDATE subjects SET
                institution_id = ?, program_id = ?, curriculum_version_id = ?, status = 'published'
            WHERE id = ?
            """, (i_id, p_id, v_id, s_id))

        # Create authorized resource for the subject
        cursor.execute("SELECT id FROM learning_resources WHERE subject_id = ?", (s_id,))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO learning_resources (
                institution_id, subject_id, title, file_name, resource_type, source,
                authorization_status, copyright_acknowledged, version, is_demo
            ) VALUES (?, ?, ?, ?, 'textbook', 'Official Institution Syllabus Committee', 'authorized', 1, '1.0', 1)
            """, (i_id, s_id, f"Official Reference Text: {s_name}", f"{s_code}_Textbook.pdf"))
            res_id = cursor.lastrowid
        else:
            res_id = cursor.fetchone()

        # Modules & Topics
        for m_num, m_name, m_desc, topics_list in modules_list:
            cursor.execute("SELECT id FROM modules WHERE subject_id = ? AND module_number = ?", (s_id, m_num))
            m_row = cursor.fetchone()
            if not m_row:
                cursor.execute("""
                INSERT INTO modules (subject_id, module_number, module_name, description)
                VALUES (?, ?, ?, ?)
                """, (s_id, m_num, m_name, m_desc))
                mod_id = cursor.lastrowid
            else:
                mod_id = m_row["id"]

            for t_idx, (t_name, t_desc, t_diff, t_source, t_obj) in enumerate(topics_list, start=1):
                cursor.execute("SELECT id FROM topics WHERE module_id = ? AND topic_name = ?", (mod_id, t_name))
                t_row = cursor.fetchone()
                if not t_row:
                    cursor.execute("""
                    INSERT INTO topics (module_id, subject_id, topic_name, description, difficulty, order_number)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (mod_id, s_id, t_name, t_desc, t_diff, t_idx))
                    top_id = cursor.lastrowid
                else:
                    top_id = t_row["id"]

                # Add Lesson for backward compatibility and lessons portal
                cursor.execute("SELECT id FROM lessons WHERE subject_id = ? AND topic = ?", (s_id, t_name))
                if not cursor.fetchone():
                    cursor.execute("""
                    INSERT INTO lessons (subject_id, title, description, topic, content, difficulty, estimated_minutes, order_number)
                    VALUES (?, ?, ?, ?, ?, ?, 45, ?)
                    """, (s_id, f"Core Lesson: {t_name}", t_desc, t_name, f"# {t_name}\n\n{t_desc}\n\n**Source Reference:** {t_source}\n\n## Core Principles\n- Operational foundations and mathematical formulation.\n- Practical implementation guidelines.", t_diff, t_idx))

                # Add Document Chunk for retrieval grounding
                cursor.execute("SELECT id FROM document_chunks WHERE topic_id = ?", (top_id,))
                if not cursor.fetchone() and res_id:
                    cursor.execute("""
                    INSERT INTO document_chunks (
                        resource_id, subject_id, module_id, topic_id, page_number,
                        section_heading, chunk_text, token_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 60)
                    """, (res_id, s_id, mod_id, top_id, t_idx * 15, t_name, f"Approved curriculum content for {t_name}. Core theoretical derivation, operational trade-offs, and design principles according to {t_source}."))

                # Add Grounded Question
                cursor.execute("SELECT id FROM grounded_questions WHERE topic_id = ?", (top_id,))
                if not cursor.fetchone():
                    cursor.execute("""
                    INSERT INTO grounded_questions (
                        subject_id, module_id, topic_id, question_text, question_type,
                        option_a, option_b, option_c, option_d, correct_answer, explanation,
                        difficulty, source_reference, source_page, generation_method, approval_status
                    ) VALUES (?, ?, ?, ?, 'MCQ', ?, ?, ?, ?, 'A', ?, ?, ?, ?, 'grounded_rag', 'approved')
                    """, (
                        s_id, mod_id, top_id,
                        f"According to {s_name} standards, what is the core engineering purpose of {t_name}?",
                        f"Systematic algorithmic optimization and bounded error control for {t_name}.",
                        "Manual non-standard trial and error without metrics.",
                        "Bypassing runtime validation checks.",
                        "None of the above.",
                        f"Approved source {t_source} establishes exact analytical bounds for {t_name}.",
                        t_diff, t_source, t_idx * 15
                    ))

    # =========================================================================
    # 6. AUTO-ENROLL STUDENTS & SEED PERFORMANCE / TOPIC MASTERY
    # =========================================================================
    student_a_id = student_id_map["21AUAIML001"]
    student_b_id = student_id_map["21JNTUKECE042"]

    # Student A (College A - AU AIML)
    cursor.execute("SELECT id FROM subjects WHERE institution_id = ? AND program_id = ?", (au_id, au_aiml_prog))
    for s_row in cursor.fetchall():
        s_id = s_row["id"]
        cursor.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)", (student_a_id, s_id))
        cursor.execute("""
        INSERT OR IGNORE INTO student_subject_performance (student_id, subject_id, attendance, assessment_score, assignment_score, quiz_score, lab_score, overall_score, mastery_score)
        VALUES (?, ?, 78.5, 62.0, 70.0, 58.0, 72.0, 65.0, 56.0)
        """, (student_a_id, s_id))

    # Seed topic mastery for Student A on Decision Trees (weak = 42%)
    cursor.execute("SELECT id, subject_id FROM topics WHERE topic_name = 'Decision Trees'")
    dt_row = cursor.fetchone()
    if dt_row:
        cursor.execute("""
        INSERT OR REPLACE INTO student_topic_mastery (student_id, topic_id, subject_id, mastery_score, quiz_score, attempts, time_spent_minutes, status)
        VALUES (?, ?, ?, 42.0, 40.0, 3, 45.0, 'needs_revision')
        """, (student_a_id, dt_row["id"], dt_row["subject_id"]))

    cursor.execute("SELECT id, subject_id FROM topics WHERE topic_name = 'Entropy and Information Gain'")
    ent_row = cursor.fetchone()
    if ent_row:
        cursor.execute("""
        INSERT OR REPLACE INTO student_topic_mastery (student_id, topic_id, subject_id, mastery_score, quiz_score, attempts, time_spent_minutes, status)
        VALUES (?, ?, ?, 38.0, 35.0, 2, 30.0, 'needs_revision')
        """, (student_a_id, ent_row["id"], ent_row["subject_id"]))

    # Student B (College B - JNTUK ECE)
    cursor.execute("SELECT id FROM subjects WHERE institution_id = ? AND program_id = ?", (jntuk_id, jntuk_ece_prog))
    for s_row in cursor.fetchall():
        s_id = s_row["id"]
        cursor.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)", (student_b_id, s_id))
        cursor.execute("""
        INSERT OR IGNORE INTO student_subject_performance (student_id, subject_id, attendance, assessment_score, assignment_score, quiz_score, lab_score, overall_score, mastery_score)
        VALUES (?, ?, 84.0, 72.0, 75.0, 70.0, 78.0, 74.0, 72.0)
        """, (student_b_id, s_id))

    # Seed topic mastery for Student B
    cursor.execute("SELECT id, subject_id FROM topics WHERE topic_name = 'Continuous-Time Fourier Transform'")
    ctft_row = cursor.fetchone()
    if ctft_row:
        cursor.execute("""
        INSERT OR REPLACE INTO student_topic_mastery (student_id, topic_id, subject_id, mastery_score, quiz_score, attempts, time_spent_minutes, status)
        VALUES (?, ?, ?, 48.0, 50.0, 2, 35.0, 'needs_revision')
        """, (student_b_id, ctft_row["id"], ctft_row["subject_id"]))

    cursor.execute("SELECT id, subject_id FROM topics WHERE topic_name = 'CMOS Inverter DC Characteristics'")
    cmos_row = cursor.fetchone()
    if cmos_row:
        cursor.execute("""
        INSERT OR REPLACE INTO student_topic_mastery (student_id, topic_id, subject_id, mastery_score, quiz_score, attempts, time_spent_minutes, status)
        VALUES (?, ?, ?, 78.0, 80.0, 1, 20.0, 'in_progress')
        """, (student_b_id, cmos_row["id"], cmos_row["subject_id"]))

    # Assign faculty to subjects
    prof_murthy_id = cursor.execute("SELECT id FROM teachers WHERE email = 'prof.murthy@au.edu.in'").fetchone()[0]
    dr_venk_id = cursor.execute("SELECT id FROM teachers WHERE email = 'dr.venkatesh@jntuk.edu.in'").fetchone()[0]

    cursor.execute("SELECT id FROM subjects WHERE subject_code = 'CS301-AU'")
    ml_sub_row = cursor.fetchone()
    if ml_sub_row:
        cursor.execute("INSERT OR IGNORE INTO teacher_subjects (teacher_id, subject_id, branch, year, semester, section) VALUES (?, ?, 'AIML', '3rd Year', 1, 'A')", (prof_murthy_id, ml_sub_row["id"]))

    cursor.execute("SELECT id FROM subjects WHERE subject_code = 'EC301-JNTUK'")
    sig_sub_row = cursor.fetchone()
    if sig_sub_row:
        cursor.execute("INSERT OR IGNORE INTO teacher_subjects (teacher_id, subject_id, branch, year, semester, section) VALUES (?, ?, 'ECE', '3rd Year', 1, 'A')", (dr_venk_id, sig_sub_row["id"]))

    conn.commit()
    conn.close()
    print("[+] State-scale multi-institution curriculum, roles, grounded resources, and test cases seeded successfully!")


if __name__ == "__main__":
    seed_academic_curriculum()
