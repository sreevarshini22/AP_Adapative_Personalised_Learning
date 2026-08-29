"""
Comprehensive Academic Curriculum Seed Script for AP Adaptive Education Platform
Populates all engineering branches across ALL 4 Years and ALL 8 Semesters:
- CSE (Computer Science & Engineering)
- CSE (AI & ML)
- CSE (Data Science)
- ECE (Electronics & Communication Engineering)
- EEE (Electrical & Electronics Engineering)
- Mechanical Engineering
- Civil Engineering
- Information Technology (IT)

Each semester has its authentic B.Tech curriculum subjects, lessons, labs, quizzes, and faculty assignments.
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
    
    # 1. Faculty Accounts across departments
    teachers_data = [
        ("Dr. Ravi Kumar", "dr.ravi@apedu.ac.in", "CSE", "2nd Year", "A"),
        ("Dr. K. Srinivas Murthy", "teacher@example.com", "CSE", "3rd Year", "A"),
        ("Prof. Lakshmi Devi", "prof.lakshmi@apedu.ac.in", "CSE (AI & ML)", "2nd Year", "B"),
        ("Dr. P. Venkatesh", "dr.venkatesh@apedu.ac.in", "ECE", "4th Year", "C"),
        ("Prof. K. Ranga Rao", "prof.rangarao@apedu.ac.in", "EEE", "3rd Year", "A"),
        ("Dr. M. Suresh", "dr.suresh@apedu.ac.in", "Mechanical Engineering", "2nd Year", "A"),
        ("Dr. N. Satyanarayana", "dr.satya@apedu.ac.in", "Civil Engineering", "3rd Year", "A"),
        ("Prof. Geetha Reddy", "prof.geetha@apedu.ac.in", "Information Technology", "2nd Year", "A")
    ]
    
    default_teacher_pwd = generate_password_hash("teacher123")
    teacher_id_map = {}
    
    for full_name, email, branch, yr, sec in teachers_data:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email.lower(),))
        user_row = cursor.fetchone()
        if not user_row:
            cursor.execute("""
            INSERT INTO users (email, password_hash, role, full_name)
            VALUES (?, ?, 'teacher', ?)
            """, (email.lower(), default_teacher_pwd, full_name))
            u_id = cursor.lastrowid
        else:
            u_id = user_row["id"]
            
        cursor.execute("SELECT id FROM teachers WHERE LOWER(email) = ?", (email.lower(),))
        t_row = cursor.fetchone()
        if not t_row:
            cursor.execute("""
            INSERT INTO teachers (user_id, full_name, email, branch, year, section)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (u_id, full_name, email.lower(), branch, yr, sec))
            t_id = cursor.lastrowid
        else:
            t_id = t_row["id"]
            
        teacher_id_map[email.lower()] = t_id

    # 2. Comprehensive B.Tech Curriculum across all branches and all 8 semesters
    # Format: (subject_code, subject_name, branch, year, semester, credits, subject_type, description, assigned_teacher_email)
    all_subjects_catalog = [
        # =========================================================================
        # CSE (Computer Science & Engineering) - Semesters 1 to 8
        # =========================================================================
        # Sem 1 (1st Year)
        ("CS101", "Programming for Problem Solving using C", "CSE", "1st Year", 1, 3, "theory", "Algorithmic thinking, branching, loops, functions, arrays, pointers, and file operations in C.", "dr.ravi@apedu.ac.in"),
        ("CS101L", "C Programming & Problem Solving Lab", "CSE", "1st Year", 1, 2, "lab", "Hands-on implementation of C programs, pointer arithmetic, structures, and dynamic memory allocation.", "dr.ravi@apedu.ac.in"),
        ("MA101", "Engineering Mathematics - I (Calculus & ODE)", "CSE", "1st Year", 1, 4, "theory", "Single and multivariable calculus, Taylor series, and ordinary differential equations.", "prof.lakshmi@apedu.ac.in"),
        ("PH101", "Applied Physics & Semiconductor Devices", "CSE", "1st Year", 1, 3, "theory", "Wave optics, quantum mechanics, dielectric materials, and semiconductor band theory.", "dr.venkatesh@apedu.ac.in"),
        ("PH101L", "Applied Physics & Optics Lab", "CSE", "1st Year", 1, 2, "lab", "Optical bench experiments, semiconductor diode V-I characteristics, and Planck constant determination.", "dr.venkatesh@apedu.ac.in"),
        ("EE101", "Basic Electrical & Electronics Engineering", "CSE", "1st Year", 1, 3, "integrated", "DC/AC circuit analysis, transformers, diodes, BJT amplifiers, and logic gates.", "prof.rangarao@apedu.ac.in"),
        ("HS101", "Communicative English & Technical Writing", "CSE", "1st Year", 1, 2, "theory", "Vocabulary, reading comprehension, report generation, and formal technical communication.", "prof.lakshmi@apedu.ac.in"),

        # Sem 2 (1st Year)
        ("CS102", "Python Programming & Scripting", "CSE", "1st Year", 2, 3, "theory", "Control flow, OOP in Python, list comprehensions, file I/O, and NumPy vectorization.", "dr.ravi@apedu.ac.in"),
        ("CS102L", "Python Programming Virtual Lab", "CSE", "1st Year", 2, 2, "lab", "Hands-on Python scripts, data structures, object-oriented design, and algorithmic problem sets.", "dr.ravi@apedu.ac.in"),
        ("MA102", "Engineering Mathematics - II (Linear Algebra & Vector Calculus)", "CSE", "1st Year", 2, 4, "theory", "Eigenvalues, Cayley-Hamilton theorem, orthogonal transformations, and Stokes theorem.", "prof.lakshmi@apedu.ac.in"),
        ("CH102", "Engineering Chemistry & Material Science", "CSE", "1st Year", 2, 3, "theory", "Electrochemistry, polymers, phase rule, corrosion inhibitors, and nano-materials.", "dr.satya@apedu.ac.in"),
        ("ME102", "Engineering Graphics & Design Modeling", "CSE", "1st Year", 2, 3, "integrated", "Orthographic projections, isometric views, 3D modeling, and CAD drafting principles.", "dr.suresh@apedu.ac.in"),
        ("CS103", "Data Structures Fundamentals", "CSE", "1st Year", 2, 3, "integrated", "Dynamic memory management, linked lists, stacks, queues, and search trees.", "teacher@example.com"),

        # Sem 3 (2nd Year)
        ("CS201", "Data Structures & Algorithms", "CSE", "2nd Year", 3, 3, "theory", "Asymptotic analysis, advanced trees, heaps, graphs, hashing, and greedy traversal techniques.", "dr.ravi@apedu.ac.in"),
        ("CS201L", "Advanced Data Structures Lab", "CSE", "2nd Year", 3, 2, "lab", "Hands-on coding of AVL trees, red-black trees, Dijkstra shortest paths, and graph traversal.", "dr.ravi@apedu.ac.in"),
        ("CS202", "Database Management Systems", "CSE", "2nd Year", 3, 3, "theory", "ER modeling, relational algebra, SQL DDL/DML, normalization, and ACID transactions.", "teacher@example.com"),
        ("CS202L", "Database & SQL Systems Lab", "CSE", "2nd Year", 3, 2, "lab", "Schema design, complex SQL queries, stored procedures, triggers, and transaction isolation tests.", "teacher@example.com"),
        ("CS203", "Operating Systems & System Programming", "CSE", "2nd Year", 3, 3, "integrated", "Processes, CPU scheduling, synchronization primitives, virtual memory paging, and deadlocks.", "dr.ravi@apedu.ac.in"),
        ("MA201", "Discrete Mathematical Structures", "CSE", "2nd Year", 3, 3, "theory", "Set theory, propositional logic, relations, recurrence relations, and graph algorithms.", "prof.lakshmi@apedu.ac.in"),
        ("CS204", "Computer Organization & Architecture", "CSE", "2nd Year", 3, 3, "theory", "Instruction pipelining, cache memory hierarchies, ALU design, and I/O architectures.", "teacher@example.com"),

        # Sem 4 (2nd Year)
        ("CS205", "Object Oriented Programming through Java", "CSE", "2nd Year", 4, 3, "theory", "Classes, inheritance, polymorphism, interfaces, exception handling, multithreading, and Java Collections.", "dr.ravi@apedu.ac.in"),
        ("CS205L", "Java Programming & OOP Lab", "CSE", "2nd Year", 4, 2, "lab", "Java GUI programming, thread synchronization, socket programming, and collections framework.", "dr.ravi@apedu.ac.in"),
        ("CS206", "Design & Analysis of Algorithms", "CSE", "2nd Year", 4, 4, "integrated", "Divide & Conquer, Dynamic Programming, Greedy paradigm, Backtracking, and NP-completeness.", "teacher@example.com"),
        ("CS207", "Formal Languages & Automata Theory", "CSE", "2nd Year", 4, 3, "theory", "Finite automata, regular expressions, context-free grammars, pushdown automata, and Turing machines.", "dr.ravi@apedu.ac.in"),
        ("MA203", "Probability, Statistics & Queueing Theory", "CSE", "2nd Year", 4, 3, "theory", "Probability distributions, hypothesis testing, ANOVA, Markov chains, and M/M/1 queuing models.", "prof.lakshmi@apedu.ac.in"),
        ("CS208", "Software Engineering & Agile Methodologies", "CSE", "2nd Year", 4, 3, "theory", "SDLC models, Agile Scrum, requirements analysis, UML architectural design, and software QA.", "prof.lakshmi@apedu.ac.in"),

        # Sem 5 (3rd Year)
        ("CS301", "Machine Learning & Statistical Pattern Recognition", "CSE", "3rd Year", 5, 3, "theory", "Supervised classification, regression, SVMs, Decision Trees, Ensemble Random Forests, and Gradient Boosting.", "teacher@example.com"),
        ("CS301L", "Machine Learning & AI Practical Lab", "CSE", "3rd Year", 5, 2, "lab", "Scikit-Learn modeling, model evaluation metrics, feature engineering, and hyperparameter tuning.", "teacher@example.com"),
        ("CS302", "Web Technologies & Full Stack Development", "CSE", "3rd Year", 5, 3, "theory", "HTML5, CSS3, ES6 JavaScript, Node.js, Express, REST APIs, and database integration.", "dr.ravi@apedu.ac.in"),
        ("CS302L", "Web Technologies Lab", "CSE", "3rd Year", 5, 2, "lab", "Building dynamic responsive web applications, REST API development, and asynchronous client-server calls.", "dr.ravi@apedu.ac.in"),
        ("CS303", "Computer Networks & Protocols", "CSE", "3rd Year", 5, 3, "integrated", "Layered OSI/TCP-IP models, flow control, routing protocols (OSPF/BGP), and TCP congestion.", "teacher@example.com"),
        ("CS304", "Microprocessors & Microcontrollers Interfacing", "CSE", "3rd Year", 5, 3, "integrated", "8086/ARM architecture, assembly programming, interrupt handling, and peripheral interfacing.", "dr.venkatesh@apedu.ac.in"),
        ("CS305", "Artificial Intelligence Foundations", "CSE", "3rd Year", 5, 3, "theory", "Knowledge representation, heuristic search (A*), game playing, constraint satisfaction, and rule engines.", "prof.lakshmi@apedu.ac.in"),

        # Sem 6 (3rd Year)
        ("CS306", "Deep Learning & Neural Architectures", "CSE", "3rd Year", 6, 3, "theory", "Perceptrons, backpropagation, CNNs for computer vision, RNNs, and Transformer attention models.", "teacher@example.com"),
        ("CS306L", "Deep Learning & PyTorch Lab", "CSE", "3rd Year", 6, 2, "lab", "PyTorch model training, CNN image classification, transfer learning, and sequence modeling.", "teacher@example.com"),
        ("CS307", "Cryptography & Network Security", "CSE", "3rd Year", 6, 3, "theory", "Symmetric/Asymmetric encryption (AES, RSA), SHA-256 hashing, digital signatures, and firewalls.", "dr.ravi@apedu.ac.in"),
        ("CS308", "Cloud Computing & DevOps CI/CD", "CSE", "3rd Year", 6, 3, "integrated", "Virtualization, AWS/Azure architectures, Docker containers, Kubernetes orchestration, and CI/CD.", "teacher@example.com"),
        ("CS309", "Compiler Design & Code Generation", "CSE", "3rd Year", 6, 3, "theory", "Lexical analysis (Lex/Flex), syntax analysis (Yacc/Bison), intermediate code generation, and optimization.", "dr.ravi@apedu.ac.in"),
        ("CS310", "Big Data Analytics with Apache Spark", "CSE", "3rd Year", 6, 3, "integrated", "Hadoop HDFS, MapReduce, Apache Spark RDDs, PySpark dataframes, and stream processing.", "prof.geetha@apedu.ac.in"),

        # Sem 7 (4th Year)
        ("CS401", "Distributed Systems & Cloud Architecture", "CSE", "4th Year", 7, 4, "theory", "RPC, distributed consensus (Raft/Paxos), replication, clock synchronization, and microservices.", "teacher@example.com"),
        ("CS402", "Cyber Security, Penetration Testing & Forensics", "CSE", "4th Year", 7, 3, "theory", "Penetration testing, vulnerability scanning, malware analysis, and digital evidence handling.", "dr.ravi@apedu.ac.in"),
        ("CS402L", "Cyber Security & Ethical Hacking Lab", "CSE", "4th Year", 7, 2, "lab", "Packet sniffing (Wireshark), vulnerability assessment (Nessus), exploit payloads, and defense logging.", "dr.ravi@apedu.ac.in"),
        ("CS403", "Natural Language Processing & LLMs", "CSE", "4th Year", 7, 3, "integrated", "Word embeddings (Word2Vec), BERT, text classification, named entity recognition, and LLMs.", "prof.lakshmi@apedu.ac.in"),
        ("CS404", "Mobile Application Development", "CSE", "4th Year", 7, 3, "integrated", "Android SDK, Kotlin/Flutter UI widgets, background services, REST API consumers, and SQLite.", "prof.geetha@apedu.ac.in"),

        # Sem 8 (4th Year)
        ("CS405", "Major Capstone Engineering Project", "CSE", "4th Year", 8, 8, "lab", "End-to-end engineering capstone development, system deployment, research publication, and viva.", "teacher@example.com"),
        ("CS406", "High Performance Computing & GPU Acceleration", "CSE", "4th Year", 8, 3, "theory", "Parallel computing paradigms, OpenMP, MPI, and GPU CUDA accelerated scientific workloads.", "dr.ravi@apedu.ac.in"),
        ("CS407", "Enterprise Full Stack Application Engineering", "CSE", "4th Year", 8, 3, "integrated", "Microservices architecture, GraphQL, JWT authentication, caching strategies, and cloud deployment.", "prof.geetha@apedu.ac.in"),

        # =========================================================================
        # CSE (AI & ML) - Specialized Semesters 1 to 8
        # =========================================================================
        # Sem 1
        ("AIML101", "Introduction to Artificial Intelligence", "CSE (AI & ML)", "1st Year", 1, 3, "theory", "History of AI, problem formulations, state space search, and ethical considerations.", "prof.lakshmi@apedu.ac.in"),
        ("AIML101L", "Python for AI Foundations Lab", "CSE (AI & ML)", "1st Year", 1, 2, "lab", "Basic Python scripting, matrix manipulations with NumPy, and introductory search heuristics.", "prof.lakshmi@apedu.ac.in"),
        ("MA101A", "Mathematics for Machine Learning - I", "CSE (AI & ML)", "1st Year", 1, 4, "theory", "Multivariable calculus, partial derivatives, gradients, and optimization foundations.", "prof.lakshmi@apedu.ac.in"),
        ("PH101A", "Physics of Computation & Sensors", "CSE (AI & ML)", "1st Year", 1, 3, "theory", "Sensor physics, signal acquisition, noise characteristics, and transducer models.", "dr.venkatesh@apedu.ac.in"),
        ("EE101A", "Digital Principles for AI Accelerators", "CSE (AI & ML)", "1st Year", 1, 3, "integrated", "Logic gates, adders, multipliers, and systolic array compute architectures.", "prof.rangarao@apedu.ac.in"),
        
        # Sem 2
        ("AIML102", "Python for Scientific Computing & Data Wrangling", "CSE (AI & ML)", "1st Year", 2, 3, "theory", "NumPy, SciPy, Pandas data wrangling, and Matplotlib/Seaborn visualization.", "prof.lakshmi@apedu.ac.in"),
        ("AIML102L", "Scientific Python & Data Science Lab", "CSE (AI & ML)", "1st Year", 2, 2, "lab", "Data cleaning pipelines, exploratory data analysis, and multivariate visualizations.", "prof.lakshmi@apedu.ac.in"),
        ("MA102A", "Linear Algebra for AI & Optimization", "CSE (AI & ML)", "1st Year", 2, 4, "theory", "Vector spaces, matrix decompositions, eigenvalues, and convex optimization.", "prof.lakshmi@apedu.ac.in"),
        ("CS103A", "Data Structures for Intelligent Systems", "CSE (AI & ML)", "1st Year", 2, 4, "integrated", "Graphs, heaps, hash tables, and priority search structures.", "dr.ravi@apedu.ac.in"),

        # Sem 3
        ("AIML201", "Foundations of Artificial Intelligence", "CSE (AI & ML)", "2nd Year", 3, 3, "theory", "Search algorithms, heuristic evaluation, adversarial games, and probabilistic reasoning.", "prof.lakshmi@apedu.ac.in"),
        ("AIML201L", "AI Search & Heuristics Lab", "CSE (AI & ML)", "2nd Year", 3, 2, "lab", "Implementing A*, IDA*, Alpha-Beta pruning, and constraint satisfaction solvers.", "prof.lakshmi@apedu.ac.in"),
        ("AIML202", "Advanced Data Structures for AI", "CSE (AI & ML)", "2nd Year", 3, 3, "integrated", "Trie trees, KD-trees, priority queues, and graph representations for AI state spaces.", "dr.ravi@apedu.ac.in"),
        ("CS202A", "Databases & Data Warehousing for AI", "CSE (AI & ML)", "2nd Year", 3, 3, "integrated", "Relational SQL, vector embeddings stores, and data pipelines.", "teacher@example.com"),
        ("MA202", "Probability & Bayesian Inference", "CSE (AI & ML)", "2nd Year", 3, 3, "theory", "Probability distributions, maximum likelihood estimation, Bayesian networks.", "prof.lakshmi@apedu.ac.in"),

        # Sem 4
        ("AIML203", "Statistical Machine Learning", "CSE (AI & ML)", "2nd Year", 4, 3, "theory", "Regression models, decision tree ensembles, SVMs, and clustering techniques.", "prof.lakshmi@apedu.ac.in"),
        ("AIML203L", "Machine Learning Algorithms Lab", "CSE (AI & ML)", "2nd Year", 4, 2, "lab", "Hands-on implementations of gradient descent, random forests, and k-means clustering.", "prof.lakshmi@apedu.ac.in"),
        ("AIML204", "Knowledge Representation & Reasoning", "CSE (AI & ML)", "2nd Year", 4, 3, "theory", "Ontologies, first-order logic, description logics, and automated theorem provers.", "prof.lakshmi@apedu.ac.in"),
        ("CS206A", "Algorithmic Complexity in AI", "CSE (AI & ML)", "2nd Year", 4, 4, "integrated", "Dynamic programming, randomized algorithms, and approximation bounds.", "teacher@example.com"),

        # Sem 5
        ("AIML301", "Deep Learning & Neural Architectures", "CSE (AI & ML)", "3rd Year", 5, 3, "theory", "CNN architectures, ResNets, RNNs, LSTMs, Attention mechanisms, and PyTorch frameworks.", "prof.lakshmi@apedu.ac.in"),
        ("AIML301L", "Deep Learning & Neural Networks Lab", "CSE (AI & ML)", "3rd Year", 5, 2, "lab", "Building CNNs, autoencoders, and sequence models using PyTorch & TensorFlow.", "prof.lakshmi@apedu.ac.in"),
        ("AIML303", "Natural Language Understanding", "CSE (AI & ML)", "3rd Year", 5, 3, "integrated", "Syntactic parsing, word embeddings, sequence-to-sequence models, and sentiment analysis.", "prof.lakshmi@apedu.ac.in"),
        ("CS308A", "Cloud AI Infrastructure & MLOps", "CSE (AI & ML)", "3rd Year", 5, 3, "integrated", "MLflow, model versioning, automated deployment pipelines, and GPU clusters.", "teacher@example.com"),

        # Sem 6
        ("AIML302", "Computer Vision & Visual Perception", "CSE (AI & ML)", "3rd Year", 6, 3, "theory", "Object detection (YOLO), image segmentation, optical flow, and generative adversarial networks.", "prof.lakshmi@apedu.ac.in"),
        ("AIML302L", "Computer Vision & OpenCV Lab", "CSE (AI & ML)", "3rd Year", 6, 2, "lab", "Edge detection, feature matching, YOLO inference, and real-time video processing.", "prof.lakshmi@apedu.ac.in"),
        ("AIML304", "Reinforcement Learning & Decision Systems", "CSE (AI & ML)", "3rd Year", 6, 3, "integrated", "MDPs, Value Iteration, Q-learning, Deep Q-Networks (DQN), and Actor-Critic methods.", "prof.lakshmi@apedu.ac.in"),
        ("AIML305", "Big Data Analytics for AI", "CSE (AI & ML)", "3rd Year", 6, 3, "integrated", "PySpark MLlib, distributed feature stores, and stream analytics.", "prof.geetha@apedu.ac.in"),

        # Sem 7
        ("AIML401", "Generative AI & Large Language Models", "CSE (AI & ML)", "4th Year", 7, 3, "theory", "Transformer foundations, fine-tuning LLMs (LoRA), RAG architectures, and diffusion models.", "prof.lakshmi@apedu.ac.in"),
        ("AIML401L", "Generative AI & LLM Fine-Tuning Lab", "CSE (AI & ML)", "4th Year", 7, 2, "lab", "Building RAG pipelines with LangChain, vector databases (ChromaDB), and LoRA fine-tuning.", "prof.lakshmi@apedu.ac.in"),
        ("AIML403", "Autonomous Systems & Robotics AI", "CSE (AI & ML)", "4th Year", 7, 3, "integrated", "SLAM, sensor fusion, path planning algorithms, and ROS robotics middleware.", "dr.suresh@apedu.ac.in"),
        ("AIML404", "AI Ethics, Governance & Safety", "CSE (AI & ML)", "4th Year", 7, 3, "theory", "Explainability (SHAP/LIME), algorithmic fairness, model auditing, and AI alignment.", "prof.lakshmi@apedu.ac.in"),

        # Sem 8
        ("AIML405", "AI & ML Major Capstone Project", "CSE (AI & ML)", "4th Year", 8, 8, "lab", "Production AI deployment, end-to-end pipeline implementation, and technical viva.", "prof.lakshmi@apedu.ac.in"),
        ("AIML406", "Quantum Machine Learning", "CSE (AI & ML)", "4th Year", 8, 3, "theory", "Quantum variational circuits, PennyLane integration, and quantum support vector classifiers.", "teacher@example.com"),

        # =========================================================================
        # CSE (Data Science) - Semesters 1 to 8
        # =========================================================================
        ("DS101", "Foundations of Data Science", "CSE (Data Science)", "1st Year", 1, 3, "theory", "Data collection methodologies, exploratory analysis, hypothesis generation, and visualization.", "prof.geetha@apedu.ac.in"),
        ("DS101L", "Data Science Foundations Lab", "CSE (Data Science)", "1st Year", 1, 2, "lab", "Exploratory data analysis, statistical tests, and data cleaning using Python Pandas.", "prof.geetha@apedu.ac.in"),
        ("DS102", "Statistical Methods for Data Analysis", "CSE (Data Science)", "1st Year", 2, 4, "integrated", "Sampling distributions, hypothesis tests, regression modeling, and non-parametric statistics.", "prof.geetha@apedu.ac.in"),
        ("DS201", "Data Wrangling & Feature Engineering", "CSE (Data Science)", "2nd Year", 3, 3, "theory", "Data cleaning pipelines, feature engineering, missing data imputation, and outlier analysis.", "prof.geetha@apedu.ac.in"),
        ("DS201L", "Data Wrangling & ETL Lab", "CSE (Data Science)", "2nd Year", 3, 2, "lab", "Building automated ETL pipelines, data validation checks, and feature scaling.", "prof.geetha@apedu.ac.in"),
        ("DS202", "Applied Machine Learning for Data Science", "CSE (Data Science)", "2nd Year", 4, 4, "integrated", "Supervised/unsupervised algorithms, tree ensembles, and dimensionality reduction.", "prof.geetha@apedu.ac.in"),
        ("DS301", "Big Data Analytics & Cloud Warehousing", "CSE (Data Science)", "3rd Year", 5, 3, "theory", "Snowflake, BigQuery, Hadoop, Spark streaming, and data lake architectures.", "prof.geetha@apedu.ac.in"),
        ("DS301L", "Big Data & Cloud Warehousing Lab", "CSE (Data Science)", "3rd Year", 5, 2, "lab", "Spark SQL querying, data warehouse schema design, and cloud analytics dashboards.", "prof.geetha@apedu.ac.in"),
        ("DS302", "Data Visualization & Storytelling", "CSE (Data Science)", "3rd Year", 6, 4, "integrated", "Tableau, PowerBI, D3.js interactive graphs, and executive dashboard design.", "prof.geetha@apedu.ac.in"),
        ("DS401", "Predictive Modeling & Time Series Forecasting", "CSE (Data Science)", "4th Year", 7, 3, "theory", "ARIMA models, Prophet, survival analysis, and business analytics dashboards.", "prof.geetha@apedu.ac.in"),
        ("DS401L", "Time Series Analysis Lab", "CSE (Data Science)", "4th Year", 7, 2, "lab", "Stationarity testing, ARIMA forecasting, and anomaly detection in sequential data.", "prof.geetha@apedu.ac.in"),
        ("DS405", "Data Science Major Capstone Project", "CSE (Data Science)", "4th Year", 8, 8, "lab", "End-to-end data product development, predictive modeling, and executive presentation.", "prof.geetha@apedu.ac.in"),

        # =========================================================================
        # ECE (Electronics & Communication Engineering) - Semesters 1 to 8
        # =========================================================================
        ("EC101", "Electronic Devices & Circuit Theory", "ECE", "1st Year", 1, 3, "theory", "PN junction physics, Zener diodes, BJT characteristics, FET biasing, and small signal models.", "dr.venkatesh@apedu.ac.in"),
        ("EC101L", "Electronic Devices & Simulation Lab", "ECE", "1st Year", 1, 2, "lab", "V-I characteristics of diodes, transistor biasing circuits, and SPICE simulations.", "dr.venkatesh@apedu.ac.in"),
        ("EC102", "Signals & Linear Systems", "ECE", "1st Year", 2, 4, "theory", "Continuous/Discrete signals, Fourier Series, Fourier Transforms, and Z-Transforms.", "dr.venkatesh@apedu.ac.in"),
        ("EC201", "Digital Logic Design & Verilog HDL", "ECE", "2nd Year", 3, 3, "theory", "Boolean algebra, Karnaugh maps, combinational/sequential logic circuits, and FSM modeling.", "dr.venkatesh@apedu.ac.in"),
        ("EC201L", "Digital Electronics & HDL Lab", "ECE", "2nd Year", 3, 2, "lab", "FPGA programming, Verilog testbenches, and combinational logic hardware testing.", "dr.venkatesh@apedu.ac.in"),
        ("EC202", "Analog Communications & Modulation", "ECE", "2nd Year", 4, 3, "theory", "AM/FM modulation, superheterodyne receivers, noise analysis, and pulse modulation.", "dr.venkatesh@apedu.ac.in"),
        ("EC202L", "Analog & Digital Communication Lab", "ECE", "2nd Year", 4, 2, "lab", "Hardware modulation/demodulation kits, spectrum analysis, and signal constellation testing.", "dr.venkatesh@apedu.ac.in"),
        ("EC301", "Digital Communications & Information Theory", "ECE", "3rd Year", 5, 4, "integrated", "PCM, QPSK, QAM digital modulations, Shannon theorem, and error correcting codes.", "dr.venkatesh@apedu.ac.in"),
        ("EC302", "Antennas & Wave Propagation", "ECE", "3rd Year", 6, 4, "theory", "Dipole antennas, radiation patterns, phased arrays, and tropospheric wave propagation.", "dr.venkatesh@apedu.ac.in"),
        ("EC401", "VLSI Design & CMOS Circuitry", "ECE", "4th Year", 7, 3, "theory", "MOS transistor theory, CMOS layout rules, dynamic logic, and static timing analysis.", "dr.venkatesh@apedu.ac.in"),
        ("EC401L", "VLSI CAD & Chip Design Lab", "ECE", "4th Year", 7, 2, "lab", "Cadence/EDA tool simulation, CMOS inverter layout design, and DRC/LVS physical verification.", "dr.venkatesh@apedu.ac.in"),
        ("EC402", "Digital Signal Processing", "ECE", "4th Year", 7, 4, "integrated", "FFT architectures, FIR/IIR filter design, bilinear transformation, and DSP hardware.", "dr.venkatesh@apedu.ac.in"),
        ("EC403", "Embedded Systems & RTOS Design", "ECE", "4th Year", 8, 4, "integrated", "ARM Cortex-M architecture, RTOS task scheduling, inter-process sync, and IoT edge nodes.", "dr.venkatesh@apedu.ac.in"),
        ("EC405", "ECE Major Capstone Project", "ECE", "4th Year", 8, 8, "lab", "Hardware system prototype design, embedded firmware development, and technical evaluation.", "dr.venkatesh@apedu.ac.in"),

        # =========================================================================
        # EEE (Electrical & Electronics Engineering) - Semesters 1 to 8
        # =========================================================================
        ("EE101E", "Basic Electrical Engineering Fundamentals", "EEE", "1st Year", 1, 3, "theory", "Circuit theorems, single-phase AC analysis, resonance, and three-phase circuits.", "prof.rangarao@apedu.ac.in"),
        ("EE101EL", "Electrical Circuits & Measurements Lab", "EEE", "1st Year", 1, 2, "lab", "Verification of KCL/KVL, Thevenin theorem, wattmeter measurements, and RL/RC circuits.", "prof.rangarao@apedu.ac.in"),
        ("EE102E", "Electromagnetic Field Theory", "EEE", "1st Year", 2, 4, "theory", "Coulomb law, Gauss law, Maxwell equations, magnetic vector potential, and Poynting vector.", "prof.rangarao@apedu.ac.in"),
        ("EE201", "Electrical Circuit Analysis & Synthesis", "EEE", "2nd Year", 3, 4, "theory", "Mesh/Nodal analysis, network theorems (Thevenin/Norton), transient response, and two-port networks.", "prof.rangarao@apedu.ac.in"),
        ("EE202", "DC Machines & Transformers", "EEE", "2nd Year", 4, 3, "theory", "DC motor torque equations, generator characteristics, single/three-phase transformer testing.", "prof.rangarao@apedu.ac.in"),
        ("EE202L", "Electrical Machines Practical Lab", "EEE", "2nd Year", 4, 2, "lab", "Speed control of DC shunt motors, load test on transformer, and Hopkinson test.", "prof.rangarao@apedu.ac.in"),
        ("EE301", "Power System Generation & Transmission", "EEE", "3rd Year", 5, 4, "theory", "Thermal/Hydro generation, line parameters, corona loss, mechanical design of overhead lines.", "prof.rangarao@apedu.ac.in"),
        ("EE302", "Power Electronics & Motor Drives", "EEE", "3rd Year", 6, 3, "theory", "Thyristors, MOSFETs, IGBTs, buck/boost converters, inverters, and variable speed motor drives.", "prof.rangarao@apedu.ac.in"),
        ("EE302L", "Power Electronics & Simulation Lab", "EEE", "3rd Year", 6, 2, "lab", "SCR firing circuits, buck-boost converter waveforms, and PWM inverter testing using MATLAB/Simulink.", "prof.rangarao@apedu.ac.in"),
        ("EE401", "Smart Grids & Renewable Energy Integration", "EEE", "4th Year", 7, 4, "theory", "Solar PV arrays, wind energy conversion, microgrids, battery energy storage, and SCADA.", "prof.rangarao@apedu.ac.in"),
        ("EE405", "EEE Major Engineering Capstone Project", "EEE", "4th Year", 8, 8, "lab", "Power system simulation, hardware converter development, and faculty viva.", "prof.rangarao@apedu.ac.in"),

        # =========================================================================
        # Mechanical Engineering - Semesters 1 to 8
        # =========================================================================
        ("ME101", "Engineering Mechanics & Statics", "Mechanical Engineering", "1st Year", 1, 3, "theory", "Force systems, equilibrium, friction, trusses, centroid, and moment of inertia.", "dr.suresh@apedu.ac.in"),
        ("ME101L", "Workshop Practice & Manufacturing Lab", "Mechanical Engineering", "1st Year", 1, 2, "lab", "Carpentry, fitting, welding, sheet metal, and basic machine tool operations.", "dr.suresh@apedu.ac.in"),
        ("ME102M", "Engineering Materials & Metallurgy", "Mechanical Engineering", "1st Year", 2, 4, "theory", "Crystal structures, phase diagrams (Fe-C), heat treatment, and alloy steels.", "dr.suresh@apedu.ac.in"),
        ("ME201", "Engineering Thermodynamics", "Mechanical Engineering", "2nd Year", 3, 4, "theory", "First & Second laws of thermodynamics, Carnot cycle, entropy, Rankine and Brayton cycles.", "dr.suresh@apedu.ac.in"),
        ("ME202", "Strength of Materials & Solid Mechanics", "Mechanical Engineering", "2nd Year", 4, 3, "theory", "Stress-strain tensors, Mohr circle, shear force and bending moment diagrams, torsion in shafts.", "dr.suresh@apedu.ac.in"),
        ("ME202L", "Material Testing & Mechanics Lab", "Mechanical Engineering", "2nd Year", 4, 2, "lab", "Tensile test on UTM, Izod/Charpy impact test, Rockwell hardness test, and torsion testing.", "dr.suresh@apedu.ac.in"),
        ("ME301", "Fluid Mechanics & Hydraulic Machinery", "Mechanical Engineering", "3rd Year", 5, 3, "theory", "Bernoulli equation, Navier-Stokes, boundary layer theory, Pelton & Francis turbines, and pumps.", "dr.suresh@apedu.ac.in"),
        ("ME301L", "Fluid Mechanics & Hydraulics Lab", "Mechanical Engineering", "3rd Year", 5, 2, "lab", "Calibration of Venturimeter/Orifice meter, performance test on Pelton turbine and centrifugal pump.", "dr.suresh@apedu.ac.in"),
        ("ME302", "Heat Transfer & Thermal Engineering", "Mechanical Engineering", "3rd Year", 6, 3, "theory", "Conduction, convection, radiation, heat exchangers (LMTD/NTU), and boiling heat transfer.", "dr.suresh@apedu.ac.in"),
        ("ME302L", "Thermal Engineering & Heat Transfer Lab", "Mechanical Engineering", "3rd Year", 6, 2, "lab", "Thermal conductivity of metal rod, heat transfer in forced convection, and pin fin test.", "dr.suresh@apedu.ac.in"),
        ("ME401", "CAD/CAM & Industrial Robotics", "Mechanical Engineering", "4th Year", 7, 4, "integrated", "Geometric modeling, CNC part programming, robot kinematics (D-H parameters), and automation.", "dr.suresh@apedu.ac.in"),
        ("ME405", "Mechanical Engineering Capstone Project", "Mechanical Engineering", "4th Year", 8, 8, "lab", "Design and fabrication of mechanical prototype, thermal/structural analysis, and viva.", "dr.suresh@apedu.ac.in"),

        # =========================================================================
        # Civil Engineering - Semesters 1 to 8
        # =========================================================================
        ("CE101", "Engineering Geology & Mineralogy", "Civil Engineering", "1st Year", 1, 3, "theory", "Physical geology, mineral identification, rock weathering, faulting, and tunnel site geology.", "dr.satya@apedu.ac.in"),
        ("CE101L", "Geology & Building Drawing Lab", "Civil Engineering", "1st Year", 1, 2, "lab", "Mineral & rock specimen identification, geological map study, and plan drafting.", "dr.satya@apedu.ac.in"),
        ("CE102", "Fluid Mechanics for Civil Engineers", "Civil Engineering", "1st Year", 2, 4, "theory", "Hydrostatics, buoyancy, flow through pipes, open channel flow, and weir equations.", "dr.satya@apedu.ac.in"),
        ("CE201", "Surveying & Geomatics Engineering", "Civil Engineering", "2nd Year", 3, 3, "theory", "Chain, compass, theodolite leveling, total station surveying, and GPS/GIS mapping.", "dr.satya@apedu.ac.in"),
        ("CE201L", "Surveying Field Lab", "Civil Engineering", "2nd Year", 3, 2, "lab", "Theodolite traversing, differential leveling, contour mapping, and total station fieldwork.", "dr.satya@apedu.ac.in"),
        ("CE202", "Building Materials & Concrete Technology", "Civil Engineering", "2nd Year", 4, 3, "theory", "Cement properties, aggregate gradation, concrete mix design (IS 10262), and durability testing.", "dr.satya@apedu.ac.in"),
        ("CE202L", "Concrete Technology & Quality Testing Lab", "Civil Engineering", "2nd Year", 4, 2, "lab", "Compressive strength of concrete cubes, slump test, Vee-Bee consistometer, and cement fineness.", "dr.satya@apedu.ac.in"),
        ("CE301", "Structural Analysis & Determinate Systems", "Civil Engineering", "3rd Year", 5, 4, "theory", "Moment distribution method, slope deflection, influence lines, and matrix stiffness analysis.", "dr.satya@apedu.ac.in"),
        ("CE302", "Geotechnical & Soil Mechanics", "Civil Engineering", "3rd Year", 6, 3, "theory", "Soil classification, permeability, shear strength (Direct shear/Triaxial), and shallow foundation design.", "dr.satya@apedu.ac.in"),
        ("CE302L", "Geotechnical Soil Mechanics Lab", "Civil Engineering", "3rd Year", 6, 2, "lab", "Atterberg limits, direct shear test, standard proctor compaction test, and permeability determination.", "dr.satya@apedu.ac.in"),
        ("CE401", "Transportation & Environmental Engineering", "Civil Engineering", "4th Year", 7, 4, "integrated", "Highway geometric design, flexible/rigid pavement design, wastewater treatment, and air pollution control.", "dr.satya@apedu.ac.in"),
        ("CE405", "Civil Engineering Major Capstone Project", "Civil Engineering", "4th Year", 8, 8, "lab", "Structural building design (ETABS), geotechnical stability analysis, and technical report.", "dr.satya@apedu.ac.in"),

        # =========================================================================
        # Information Technology (IT) - Semesters 1 to 8
        # =========================================================================
        ("IT101", "Programming & Problem Solving using Java", "Information Technology", "1st Year", 1, 3, "theory", "Syntax, loops, arrays, OOP paradigms, inheritance, interfaces, and Java exceptions.", "prof.geetha@apedu.ac.in"),
        ("IT101L", "Java Programming Foundations Lab", "Information Technology", "1st Year", 1, 2, "lab", "Writing Java classes, exception handlers, string manipulation, and I/O streams.", "prof.geetha@apedu.ac.in"),
        ("IT102", "Computer Systems Architecture", "Information Technology", "1st Year", 2, 4, "theory", "Instruction sets, memory hierarchy, bus interfaces, and processor microarchitecture.", "prof.geetha@apedu.ac.in"),
        ("IT201", "Data Structures & Java Programming", "Information Technology", "2nd Year", 3, 3, "theory", "Core data structures, OOP Java fundamentals, collections framework, and algorithmic efficiency.", "prof.geetha@apedu.ac.in"),
        ("IT201L", "Data Structures with Java Lab", "Information Technology", "2nd Year", 3, 2, "lab", "Implementing trees, graphs, sorting algorithms, and hash tables in Java.", "prof.geetha@apedu.ac.in"),
        ("IT202", "Database Technologies & Web Backend", "Information Technology", "2nd Year", 4, 4, "integrated", "Relational database modeling, NoSQL systems (MongoDB), REST backend architectures.", "prof.geetha@apedu.ac.in"),
        ("IT301", "Cloud Infrastructure & Virtualization", "Information Technology", "3rd Year", 5, 3, "theory", "IaaS, PaaS, SaaS, hypervisors, serverless architectures, and cloud security compliance.", "prof.geetha@apedu.ac.in"),
        ("IT301L", "Cloud Infrastructure & Containerization Lab", "Information Technology", "3rd Year", 5, 2, "lab", "Docker containerization, AWS EC2/S3 provisioning, and Kubernetes microservice deployment.", "prof.geetha@apedu.ac.in"),
        ("IT302", "Enterprise Web Security & Cryptography", "Information Technology", "3rd Year", 6, 4, "integrated", "OWASP Top 10 defenses, OAuth2/JWT authentication, HTTPS encryption, and security testing.", "prof.geetha@apedu.ac.in"),
        ("IT401", "Full Stack Web & Mobile App Development", "Information Technology", "4th Year", 7, 4, "integrated", "Modern web frameworks, React/React Native, state management, and cloud database persistence.", "prof.geetha@apedu.ac.in"),
        ("IT405", "Information Technology Capstone Project", "Information Technology", "4th Year", 8, 8, "lab", "Full-scale enterprise application engineering, cloud deployment, and system evaluation.", "prof.geetha@apedu.ac.in")
    ]

    subject_id_map = {}
    
    for code, name, branch, yr, sem, credits, stype, desc, teacher_email in all_subjects_catalog:
        cursor.execute("SELECT id FROM subjects WHERE subject_code = ?", (code,))
        sub_row = cursor.fetchone()
        if not sub_row:
            cursor.execute("""
            INSERT INTO subjects (subject_code, subject_name, branch, year, semester, credits, subject_type, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, branch, yr, sem, credits, stype, desc))
            sub_id = cursor.lastrowid
        else:
            sub_id = sub_row["id"]
            cursor.execute("""
            UPDATE subjects SET subject_name = ?, branch = ?, year = ?, semester = ?, credits = ?, subject_type = ?, description = ?
            WHERE id = ?
            """, (name, branch, yr, sem, credits, stype, desc, sub_id))
            
        subject_id_map[code] = sub_id
        
        # Connect Teacher to Subject across sections
        t_id = teacher_id_map.get(teacher_email.lower()) or 1
        for sec in ["A", "B", "C", "D"]:
            cursor.execute("""
            INSERT OR IGNORE INTO teacher_subjects (teacher_id, subject_id, branch, year, semester, section)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (t_id, sub_id, branch, yr, sem, sec))

    # 3. Ensure every subject in the database has at least 3-4 structured syllabus lessons, 2-3 labs (for integrated/lab), and quizzes/assignments
    cursor.execute("SELECT id, subject_code, subject_name, subject_type, branch, semester FROM subjects")
    all_stored_subjects = cursor.fetchall()

    for sub in all_stored_subjects:
        s_id = sub["id"]
        s_code = sub["subject_code"]
        s_name = sub["subject_name"]
        s_type = sub["subject_type"]
        s_branch = sub["branch"]
        s_sem = sub["semester"]

        # 3.1 Lessons
        cursor.execute("SELECT count(*) FROM lessons WHERE subject_id = ?", (s_id,))
        if cursor.fetchone()[0] < 3:
            cursor.execute("DELETE FROM lessons WHERE subject_id = ?", (s_id,))
            cursor.execute("""
            INSERT INTO lessons (subject_id, title, description, topic, content, difficulty, estimated_minutes, order_number)
            VALUES 
            (?, 'Unit 1: Foundations & Architecture of ' || ?, 'Introduction, core terminology, theoretical paradigms, and historical context.', 'Foundations', '# Unit 1: Foundations of ' || ? || '\n\n### Overview\nWelcome to the foundational module for **' || ? || '**. This unit introduces core principles, architectural models, and analytical tools.\n\n### Key Learning Objectives\n- Understand fundamental mechanisms and definitions.\n- Master mathematical and logical models.\n- Formulate standard engineering problem sets.', 'Beginner', 45, 1),
            (?, 'Unit 2: Core Analytical Methodologies & Implementation', 'Formal algorithms, mathematical representations, design rules, and data structures.', 'Core Methodologies', '# Unit 2: Core Methodologies\n\n### Theoretical Formulations\nIn this unit, we explore standard transformations, system dynamics, and implementation pipelines.\n\n```python\n# Example algorithmic formulation for ' || ? || '\ndef compute_baseline_metric(inputs, parameters):\n    \"\"\"Calculates system equilibrium or operational response.\"\"\"\n    processed = [x * parameters.get(\"weight\", 1.0) for x in inputs]\n    return sum(processed) / max(len(processed), 1)\n```\n\n### Analysis\nReview step-by-step proofs and performance constraints.', 'Intermediate', 50, 2),
            (?, 'Unit 3: Advanced Optimization & Scaling Strategies', 'System optimization, latency/complexity reduction, bottleneck diagnosis, and performance tuning.', 'Advanced Optimization', '# Unit 3: Advanced Optimization\n\n### Scaling Principles\nFocuses on scaling algorithms, parallel execution, hardware acceleration, and fault-tolerant mechanisms.\n\n### Industry Best Practices\n1. Ensure strict parameter validation.\n2. Profile memory allocations and CPU overhead.\n3. Incorporate automated verification telemetry.', 'Advanced', 60, 3),
            (?, 'Unit 4: Case Studies, Practical Deployments & Future Frontiers', 'Industrial case studies, end-to-end integration, and future research directions.', 'Emerging Technologies', '# Unit 4: Case Studies & Frontiers\n\n### Real-World Case Studies\nExamines real-world production deployments, fault recovery benchmarks, and emerging quantum/AI enhancements in **' || ? || '**.\n\n### Summary & Review Checklist\n- Complete all diagnostic problem sets.\n- Review lab exercises and simulation results.', 'Advanced', 55, 4)
            """, (s_id, s_name, s_name, s_name, s_id, s_name, s_id, s_id, s_name))

        # 3.2 Labs
        if s_type in ['integrated', 'lab']:
            cursor.execute("SELECT count(*) FROM labs WHERE subject_id = ?", (s_id,))
            if cursor.fetchone()[0] < 2:
                cursor.execute("DELETE FROM labs WHERE subject_id = ?", (s_id,))
                cursor.execute("""
                INSERT INTO labs (subject_id, title, description, instructions, experiment_number, difficulty, estimated_minutes)
                VALUES 
                (?, 'Experiment 1: Baseline Hardware/Software Verification of ' || ?, 'Configure virtual runtime, verify parameters, and record baseline experimental outputs.', '# Experiment 1: Baseline Verification\n\n### Objectives\n- Initialize virtual laboratory workspace.\n- Set up input test vectors and calibrate measurement instruments.\n- Record and tabulate baseline operational data.\n\n### Procedure\n1. Launch simulation environment.\n2. Input calibration parameters.\n3. Record observed metrics and calculate percentage deviation.', 1, 'Beginner', 60),
                (?, 'Experiment 2: Parameter Variation & Performance Profiling', 'Execute dynamic parameter sweeps, evaluate efficiency curves, and identify operational bottlenecks.', '# Experiment 2: Performance Profiling\n\n### Objectives\n- Perform parameter sweep across operational ranges.\n- Plot response curves (throughput, latency, error rate, power).\n- Determine optimal operating equilibrium.\n\n### Deliverables\n- Tabulated measurement matrix.\n- Comparative response graphs.', 2, 'Intermediate', 75),
                (?, 'Experiment 3: Advanced Optimization & Fault Diagnosis', 'Simulate stress workloads, fault injection scenarios, and verify automated recovery mechanisms.', '# Experiment 3: Stress Testing & Optimization\n\n### Objectives\n- Subject system to edge-case stress conditions.\n- Measure recovery time and data integrity under failure.\n- Apply corrective tuning and verify performance restoration.', 3, 'Advanced', 90)
                """, (s_id, s_name, s_id, s_id))

        # 3.3 Quizzes
        cursor.execute("SELECT count(*) FROM quizzes WHERE subject_id = ?", (s_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO quizzes (subject_id, title, description, topic, difficulty, time_limit, total_questions)
            VALUES (?, ? || ' Diagnostic Quiz', 'Comprehensive assessment of key concepts, analytical thinking, and problem-solving skills.', 'Core Theory', 'Intermediate', 15, 3)
            """, (s_id, s_name))
            q_id = cursor.lastrowid

            cursor.execute("""
            INSERT INTO quiz_questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option, explanation, marks)
            VALUES 
            (?, 'What is the primary operational objective of ' || ? || '?', 'To optimize efficiency and systematic engineering execution', 'Random trial execution without validation', 'Manual non-standard operations', 'None of the above', 'A', 'Systematic modeling and algorithmic optimization are fundamental to the discipline.', 1.0),
            (?, 'Which parameter governs performance scaling in ' || ? || '?', 'Input size, complexity bounds, and resource allocation', 'Display refresh rate', 'Keyboard layout configuration', 'None of the above', 'A', 'Input complexity directly determines time and memory requirements.', 1.0),
            (?, 'Which of the following represents a recommended best engineering practice?', 'Rigorous modular design, boundary checks, and automated unit testing', 'Hardcoding variable states into source routines', 'Ignoring runtime edge cases and error bounds', 'Skipping validation benchmarks', 'A', 'Modular architectural design and automated testing ensure production resilience.', 1.0)
            """, (q_id, s_name, q_id, s_name, q_id))

        # 3.4 Assignments
        cursor.execute("SELECT count(*) FROM assignments WHERE subject_id = ?", (s_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO assignments (subject_id, title, description, instructions, total_marks, due_date)
            VALUES 
            (?, 'Assignment 1: Comprehensive Problem Set on ' || ?, 'Solve analytical problem formulations, theoretical proofs, and design trade-offs.', '# Assignment 1 Instructions\n\n1. Review Unit 1 & Unit 2 core lecture notes.\n2. Provide step-by-step derivation for all problem items.\n3. Include diagrams and algorithmic complexity calculations.', 100.0, '2026-10-15'),
            (?, 'Assignment 2: Case Study & Empirical Analysis', 'Real-world application analysis, runtime performance profiling, and optimization report.', '# Assignment 2 Instructions\n\n1. Benchmark runtime metrics against standard benchmarks.\n2. Identify system bottlenecks and efficiency limitations.\n3. Propose and document concrete optimization recommendations.', 100.0, '2026-11-01')
            """, (s_id, s_name, s_id))

    # 4. Auto-enroll existing seeded students into all matching subjects for their Branch + Year + Semester
    cursor.execute("SELECT id, branch, year, semester FROM students")
    all_students = cursor.fetchall()
    for st in all_students:
        st_id = st["id"]
        cursor.execute("""
        SELECT id FROM subjects 
        WHERE branch = ? AND year = ? AND semester = ?
        """, (st["branch"], st["year"], st["semester"]))
        matching_subs = cursor.fetchall()
        for msub in matching_subs:
            cursor.execute("""
            INSERT OR IGNORE INTO student_subjects (student_id, subject_id)
            VALUES (?, ?)
            """, (st_id, msub["id"]))

    conn.commit()
    conn.close()
    print("[+] Complete B.Tech curriculum, labs, lessons, assignments, and student subject enrollments seeded!")

if __name__ == "__main__":
    seed_academic_curriculum()
