import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.predict import predict_student_risk

SUBJECT_METRIC_MAP = {
    "Mathematics": "mathematics_score",
    "Physics": "physics_score",
    "Programming Fundamentals": "programming_score",
    "Data Structures & Algorithms": "data_structures_score",
    "Database Management Systems": "database_score",
    "Communication Skills": "communication_score"
}

# Comprehensive branch-aware curriculum repository
CURRICULUM_CATALOG = {
    "Programming Fundamentals": {
        "branch_relevance": ["CSE", "CSE (AI & ML)", "CSE (Data Science)", "IT", "ECE", "EEE"],
        "modules": [
            {
                "id": "PROG-101",
                "title": "Programming Logic & Flowcharts",
                "difficulty": "Beginner",
                "prerequisite": "None",
                "estimated_time": "3 Hours",
                "learning_objective": "Master algorithmic problem decomposition and pseudocode logic."
            },
            {
                "id": "PROG-102",
                "title": "Variables, Data Types & Operators",
                "difficulty": "Beginner",
                "prerequisite": "PROG-101",
                "estimated_time": "4 Hours",
                "learning_objective": "Understand memory allocation, data representation, and arithmetic expressions."
            },
            {
                "id": "PROG-103",
                "title": "Control Structures & Looping Mechanics",
                "difficulty": "Intermediate",
                "prerequisite": "PROG-102",
                "estimated_time": "5 Hours",
                "learning_objective": "Construct conditional branches, while/for loops, and nested logic."
            },
            {
                "id": "PROG-104",
                "title": "Functions, Modular Design & Scope",
                "difficulty": "Intermediate",
                "prerequisite": "PROG-103",
                "estimated_time": "4 Hours",
                "learning_objective": "Design reusable functions, parameter passing, and recursive calls."
            },
            {
                "id": "PROG-105",
                "title": "Pointers, Memory & Dynamic Allocation",
                "difficulty": "Advanced",
                "prerequisite": "PROG-104",
                "estimated_time": "6 Hours",
                "learning_objective": "Manage heap memory, pointer arithmetic, and reference types."
            },
            {
                "id": "PROG-106",
                "title": "Applied Coding Assessment & Mini-Project",
                "difficulty": "Advanced",
                "prerequisite": "PROG-105",
                "estimated_time": "5 Hours",
                "learning_objective": "Solve competitive programming problems under timed constraints."
            }
        ]
    },
    "Data Structures & Algorithms": {
        "branch_relevance": ["CSE", "CSE (AI & ML)", "CSE (Data Science)", "IT", "ECE"],
        "modules": [
            {
                "id": "DSA-101",
                "title": "Asymptotic Analysis & Big-O Notation",
                "difficulty": "Beginner",
                "prerequisite": "PROG-104",
                "estimated_time": "3 Hours",
                "learning_objective": "Evaluate time and space complexity of computational algorithms."
            },
            {
                "id": "DSA-102",
                "title": "Arrays, Strings & Linked Lists",
                "difficulty": "Beginner",
                "prerequisite": "DSA-101",
                "estimated_time": "5 Hours",
                "learning_objective": "Implement singly, doubly, and circular linked lists with pointer operations."
            },
            {
                "id": "DSA-103",
                "title": "Stacks, Queues & Priority Queues",
                "difficulty": "Intermediate",
                "prerequisite": "DSA-102",
                "estimated_time": "4 Hours",
                "learning_objective": "Build LIFO/FIFO structures for expression parsing and scheduling."
            },
            {
                "id": "DSA-104",
                "title": "Binary Trees, BST & AVL Trees",
                "difficulty": "Intermediate",
                "prerequisite": "DSA-103",
                "estimated_time": "6 Hours",
                "learning_objective": "Perform tree traversals, balancing operations, and binary search tree queries."
            },
            {
                "id": "DSA-105",
                "title": "Graph Algorithms: BFS, DFS, Dijkstra & Prim's",
                "difficulty": "Advanced",
                "prerequisite": "DSA-104",
                "estimated_time": "7 Hours",
                "learning_objective": "Traverse graphs and find shortest paths and minimum spanning trees."
            },
            {
                "id": "DSA-106",
                "title": "Dynamic Programming & Greedy Strategies",
                "difficulty": "Advanced",
                "prerequisite": "DSA-105",
                "estimated_time": "8 Hours",
                "learning_objective": "Solve complex optimization problems with memoization and tabulation."
            }
        ]
    },
    "Database Management Systems": {
        "branch_relevance": ["CSE", "CSE (AI & ML)", "CSE (Data Science)", "IT"],
        "modules": [
            {
                "id": "DBMS-101",
                "title": "Relational Model & ER Diagrams",
                "difficulty": "Beginner",
                "prerequisite": "None",
                "estimated_time": "4 Hours",
                "learning_objective": "Design conceptual entity-relationship models for enterprise data."
            },
            {
                "id": "DBMS-102",
                "title": "SQL Queries: DDL, DML & Subqueries",
                "difficulty": "Intermediate",
                "prerequisite": "DBMS-101",
                "estimated_time": "5 Hours",
                "learning_objective": "Write complex SQL joins, grouping aggregations, and nested subqueries."
            },
            {
                "id": "DBMS-103",
                "title": "Normalization (1NF to BCNF) & Integrity",
                "difficulty": "Intermediate",
                "prerequisite": "DBMS-102",
                "estimated_time": "5 Hours",
                "learning_objective": "Eliminate data anomalies and ensure database schema normal forms."
            },
            {
                "id": "DBMS-104",
                "title": "Transactions, ACID Properties & Concurrency",
                "difficulty": "Advanced",
                "prerequisite": "DBMS-103",
                "estimated_time": "6 Hours",
                "learning_objective": "Implement two-phase locking, serializability, and rollback protocols."
            },
            {
                "id": "DBMS-105",
                "title": "Indexing, Query Optimization & NoSQL",
                "difficulty": "Advanced",
                "prerequisite": "DBMS-104",
                "estimated_time": "5 Hours",
                "learning_objective": "Analyze B-Tree index efficiency, query execution plans, and document stores."
            }
        ]
    },
    "Mathematics": {
        "branch_relevance": ["All Branches"],
        "modules": [
            {
                "id": "MATH-101",
                "title": "Matrices, Eigenvalues & Eigenvectors",
                "difficulty": "Beginner",
                "prerequisite": "None",
                "estimated_time": "4 Hours",
                "learning_objective": "Solve systems of linear equations and diagonalize matrices."
            },
            {
                "id": "MATH-102",
                "title": "Differential Calculus & Mean Value Theorems",
                "difficulty": "Intermediate",
                "prerequisite": "MATH-101",
                "estimated_time": "5 Hours",
                "learning_objective": "Apply partial derivatives, maxima/minima, and Taylor series expansions."
            },
            {
                "id": "MATH-103",
                "title": "Multiple Integrals & Vector Calculus",
                "difficulty": "Intermediate",
                "prerequisite": "MATH-102",
                "estimated_time": "6 Hours",
                "learning_objective": "Compute surface and volume integrals using Gauss and Stokes theorems."
            },
            {
                "id": "MATH-104",
                "title": "Probability Distributions & Random Variables",
                "difficulty": "Advanced",
                "prerequisite": "MATH-102",
                "estimated_time": "6 Hours",
                "learning_objective": "Model engineering uncertainty via Binomial, Poisson, and Normal distributions."
            },
            {
                "id": "MATH-105",
                "title": "Numerical Methods & Differential Equations",
                "difficulty": "Advanced",
                "prerequisite": "MATH-103",
                "estimated_time": "6 Hours",
                "learning_objective": "Implement Runge-Kutta and Newton-Raphson approximation algorithms."
            }
        ]
    },
    "Physics": {
        "branch_relevance": ["All Branches"],
        "modules": [
            {
                "id": "PHYS-101",
                "title": "Wave Optics: Interference & Diffraction",
                "difficulty": "Beginner",
                "prerequisite": "None",
                "estimated_time": "4 Hours",
                "learning_objective": "Understand Young's double slit, Newton's rings, and grating diffraction."
            },
            {
                "id": "PHYS-102",
                "title": "Quantum Mechanics & Wave Function",
                "difficulty": "Intermediate",
                "prerequisite": "PHYS-101",
                "estimated_time": "5 Hours",
                "learning_objective": "Analyze de Broglie hypothesis and 1D Schrödinger wave equation."
            },
            {
                "id": "PHYS-103",
                "title": "Semiconductor Physics & Band Theory",
                "difficulty": "Intermediate",
                "prerequisite": "PHYS-102",
                "estimated_time": "5 Hours",
                "learning_objective": "Calculate carrier concentration, Fermi level, and Hall effect parameters."
            },
            {
                "id": "PHYS-104",
                "title": "Lasers, Fiber Optics & Nanomaterials",
                "difficulty": "Advanced",
                "prerequisite": "PHYS-103",
                "estimated_time": "5 Hours",
                "learning_objective": "Understand population inversion, optical attenuation, and nano-structures."
            }
        ]
    },
    "Communication Skills": {
        "branch_relevance": ["All Branches"],
        "modules": [
            {
                "id": "COMM-101",
                "title": "Technical Vocabulary & Grammar Mechanics",
                "difficulty": "Beginner",
                "prerequisite": "None",
                "estimated_time": "3 Hours",
                "learning_objective": "Enhance formal sentence construction and technical terminology."
            },
            {
                "id": "COMM-102",
                "title": "Professional Writing: Reports & Resumes",
                "difficulty": "Intermediate",
                "prerequisite": "COMM-101",
                "estimated_time": "4 Hours",
                "learning_objective": "Draft structured engineering project reports and industry-standard resumes."
            },
            {
                "id": "COMM-103",
                "title": "Oral Presentation & Interview Readiness",
                "difficulty": "Advanced",
                "prerequisite": "COMM-102",
                "estimated_time": "4 Hours",
                "learning_objective": "Master technical defense presentations and group discussion strategies."
            }
        ]
    }
}

def analyze_student_subjects(student_data):
    """
    Categorizes student subjects into Weak (<60), Moderate (60-79), Strong (>=80).
    """
    weak = []
    moderate = []
    strong = []
    
    for subject_name, metric_key in SUBJECT_METRIC_MAP.items():
        score = student_data.get(metric_key, 0)
        try:
            score = float(score) if score is not None else 0.0
        except (ValueError, TypeError):
            score = 0.0
            
        item = {
            "subject": subject_name,
            "metric_key": metric_key,
            "score": round(score, 1)
        }
        
        if score < 60.0:
            item["status"] = "Weak"
            item["badge_color"] = "danger"
            item["recommendation_priority"] = "Priority 1 (Remedial Action Required)"
            weak.append(item)
        elif score < 80.0:
            item["status"] = "Moderate"
            item["badge_color"] = "warning"
            item["recommendation_priority"] = "Priority 2 (Reinforcement & Practice)"
            moderate.append(item)
        else:
            item["status"] = "Strong"
            item["badge_color"] = "success"
            item["recommendation_priority"] = "Maintenance (Enrichment & Advanced)"
            strong.append(item)
            
    # Sort weak subjects ascending (lowest score first = highest urgency)
    weak.sort(key=lambda x: x["score"])
    # Sort moderate ascending
    moderate.sort(key=lambda x: x["score"])
    # Sort strong descending
    strong.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "weak_subjects": weak,
        "moderate_subjects": moderate,
        "strong_subjects": strong,
        "total_subjects": len(SUBJECT_METRIC_MAP),
        "weak_count": len(weak),
        "moderate_count": len(moderate),
        "strong_count": len(strong)
    }

def generate_personalized_learning_path(student_data, prediction_info=None):
    """
    Generates a personalized step-by-step learning sequence tailored to the student's
    ML risk level, subject weaknesses, and behavioral study capacity.
    """
    if prediction_info is None:
        prediction_info = predict_student_risk(student_data)
        
    subject_analysis = analyze_student_subjects(student_data)
    risk_level = prediction_info["risk_level"]
    study_hours = float(student_data.get("study_hours", 6.0) or 6.0)
    attendance = float(student_data.get("attendance", 75.0) or 75.0)
    
    learning_path = []
    step_number = 1
    
    # 1. Address WEAK subjects first with foundational and intermediate modules
    for subj in subject_analysis["weak_subjects"]:
        catalog_entry = CURRICULUM_CATALOG.get(subj["subject"])
        if catalog_entry:
            # If high risk or very low score (<45), assign beginner foundations first
            if risk_level == "High Risk" or subj["score"] < 45:
                selected_modules = [m for m in catalog_entry["modules"] if m["difficulty"] in ["Beginner", "Intermediate"]][:3]
            else:
                selected_modules = catalog_entry["modules"][:3]
                
            for mod in selected_modules:
                learning_path.append({
                    "step": step_number,
                    "subject": subj["subject"],
                    "module_id": mod["id"],
                    "title": mod["title"],
                    "module": mod["title"],
                    "difficulty": mod["difficulty"],
                    "estimated_time": mod["estimated_time"],
                    "learning_objective": mod["learning_objective"],
                    "phase": "Remedial & Foundation",
                    "reason": f"Targeted remediation for {subj['subject']} (Current score: {subj['score']}%)",
                    "status": "In Progress" if step_number == 1 else "Pending",
                    "badge": "Urgent",
                    "priority": "High"
                })
                step_number += 1
                
    # 2. Address MODERATE subjects for skill reinforcement
    for subj in subject_analysis["moderate_subjects"]:
        catalog_entry = CURRICULUM_CATALOG.get(subj["subject"])
        if catalog_entry:
            selected_modules = [m for m in catalog_entry["modules"] if m["difficulty"] in ["Intermediate", "Advanced"]][:2]
            for mod in selected_modules:
                learning_path.append({
                    "step": step_number,
                    "subject": subj["subject"],
                    "module_id": mod["id"],
                    "title": mod["title"],
                    "module": mod["title"],
                    "difficulty": mod["difficulty"],
                    "estimated_time": mod["estimated_time"],
                    "learning_objective": mod["learning_objective"],
                    "phase": "Skill Reinforcement",
                    "reason": f"Skill booster to elevate {subj['subject']} to mastery (>80%)",
                    "status": "Pending",
                    "badge": "Core",
                    "priority": "Medium"
                })
                step_number += 1
                
    # 3. If student has strong subjects or is low risk, add advanced capstones
    for subj in subject_analysis["strong_subjects"]:
        catalog_entry = CURRICULUM_CATALOG.get(subj["subject"])
        if catalog_entry:
            adv_modules = [m for m in catalog_entry["modules"] if m["difficulty"] == "Advanced"][:1]
            for mod in adv_modules:
                learning_path.append({
                    "step": step_number,
                    "subject": subj["subject"],
                    "module_id": mod["id"],
                    "title": mod["title"],
                    "module": mod["title"],
                    "difficulty": mod["difficulty"],
                    "estimated_time": mod["estimated_time"],
                    "learning_objective": mod["learning_objective"],
                    "phase": "Advanced Enrichment",
                    "reason": f"Excellence track for strong competency in {subj['subject']}",
                    "status": "Pending",
                    "badge": "Advanced",
                    "priority": "Low"
                })
                step_number += 1
                
    # If student is strong in all areas, provide advanced mastery sequence
    if not learning_path:
        for subj_name, catalog_entry in list(CURRICULUM_CATALOG.items())[:3]:
            for mod in catalog_entry["modules"][-2:]:
                learning_path.append({
                    "step": step_number,
                    "subject": subj_name,
                    "module_id": mod["id"],
                    "title": mod["title"],
                    "module": mod["title"],
                    "difficulty": mod["difficulty"],
                    "estimated_time": mod["estimated_time"],
                    "learning_objective": mod["learning_objective"],
                    "phase": "Honors & Capstone",
                    "reason": "Advanced honors path for top-tier student",
                    "status": "In Progress" if step_number == 1 else "Pending",
                    "badge": "Honors",
                    "priority": "Low"
                })
                step_number += 1
                
    # Study plan pace estimate based on study_hours
    total_hours_est = len(learning_path) * 4.5
    weeks_needed = max(1, round(total_hours_est / max(1.0, study_hours)))
    
    return {
        "learning_path": learning_path,
        "total_modules": len(learning_path),
        "estimated_total_hours": round(total_hours_est, 1),
        "recommended_weekly_hours": max(8.0, study_hours + (4.0 if risk_level == "High Risk" else 0.0)),
        "estimated_completion_weeks": weeks_needed,
        "subject_breakdown": subject_analysis,
        "path_focus": "Remedial & Recovery" if risk_level == "High Risk" else ("Performance Enhancement" if risk_level == "Medium Risk" else "Advanced Mastery")
    }
