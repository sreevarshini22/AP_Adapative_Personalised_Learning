"""
Interactive Practice Coding Sandbox & Gamification Service
AP Adaptive Education Platform

Features:
1. Secure in-browser code execution sandbox (Python / SQL) with test case evaluation.
2. Gamification engine (XP points, Dynamic Leveling, Streaks, and Achievement Badges).
3. Grounded curriculum coding challenges (Machine Learning, Quantum Circuits, DBMS SQL, DSA).
"""

import os
import sys
import io
import time
import json
import traceback
from typing import Dict, Any, List, Optional
import sqlite3

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import get_db_connection, log_audit_event


# All platform achievement badges
ALL_BADGES = [
    {
        "key": "first_code",
        "name": "First Code Run",
        "icon": "fa-code",
        "color": "#38bdf8",
        "description": "Successfully ran your first interactive code challenge."
    },
    {
        "key": "quantum_pioneer",
        "name": "Quantum Pioneer",
        "icon": "fa-atom",
        "color": "#c084fc",
        "description": "Completed a Variational Quantum Circuit simulation challenge."
    },
    {
        "key": "algorithm_master",
        "name": "Algorithm Ace",
        "icon": "fa-brain",
        "color": "#34d399",
        "description": "Passed all test cases for an Advanced Tree or Graph algorithm."
    },
    {
        "key": "streak_warrior",
        "name": "Streak Champion",
        "icon": "fa-fire",
        "color": "#f97316",
        "description": "Maintained an active 5+ day continuous learning streak."
    },
    {
        "key": "mastery_scholar",
        "name": "Mastery Scholar",
        "icon": "fa-graduation-cap",
        "color": "#fbbf24",
        "description": "Achieved 90%+ Topic Mastery on 3 consecutive adaptive quizzes."
    }
]

# Baseline Practice Coding Challenges
DEFAULT_CHALLENGES = [
    {
        "title": "Decision Tree Entropy & Information Gain",
        "language": "python",
        "difficulty": "Intermediate",
        "category": "Machine Learning",
        "description": "Write a Python function `calculate_entropy(p)` that returns the Shannon entropy in bits for a binary classification split where `p` is the probability of positive class (0.0 < p < 1.0). Return 0.0 if p == 0 or p == 1.",
        "starter_code": "import math\n\ndef calculate_entropy(p: float) -> float:\n    # Return Shannon entropy in bits: -p*log2(p) - (1-p)*log2(1-p)\n    if p <= 0 or p >= 1:\n        return 0.0\n    return round(-p * math.log2(p) - (1 - p) * math.log2(1 - p), 4)\n",
        "solution_code": "import math\ndef calculate_entropy(p):\n    if p <= 0 or p >= 1: return 0.0\n    return round(-p * math.log2(p) - (1 - p) * math.log2(1 - p), 4)",
        "test_cases": [
            {"input": "0.5", "expected": "1.0", "hidden": False},
            {"input": "0.0", "expected": "0.0", "hidden": False},
            {"input": "0.8", "expected": "0.7219", "hidden": True}
        ],
        "xp_reward": 150
    },
    {
        "title": "Quantum Rotation & Pauli-Z Expectation",
        "language": "python",
        "difficulty": "Beginner",
        "category": "Quantum Computing",
        "description": "Calculate the theoretical Pauli-Z expectation value $\\langle Z \\rangle = \\cos(\\theta)$ for a single qubit state $|\\psi\\rangle = R_y(\\theta)|0\\rangle$. Implement `pauli_z_expectation(theta_rad)`.",
        "starter_code": "import math\n\ndef pauli_z_expectation(theta: float) -> float:\n    # Theoretical Pauli-Z expectation value is cos(theta)\n    return round(math.cos(theta), 4)\n",
        "solution_code": "import math\ndef pauli_z_expectation(theta):\n    return round(math.cos(theta), 4)",
        "test_cases": [
            {"input": "0.0", "expected": "1.0", "hidden": False},
            {"input": "3.1415926535", "expected": "-1.0", "hidden": False},
            {"input": "1.5707963267", "expected": "0.0", "hidden": True}
        ],
        "xp_reward": 120
    },
    {
        "title": "SQL Relational Grouping & Risk Aggregation",
        "language": "sql",
        "difficulty": "Intermediate",
        "category": "Database Systems",
        "description": "Write a SQL query that selects the `branch` and calculates the average attendance as `avg_att` and count of students as `student_count` grouped by `branch`, having at least 1 student, ordered by `avg_att` DESC.",
        "starter_code": "SELECT branch, AVG(attendance) AS avg_att, COUNT(*) AS student_count\nFROM students\nGROUP BY branch\nHAVING COUNT(*) >= 1\nORDER BY avg_att DESC;\n",
        "solution_code": "SELECT branch, AVG(attendance) AS avg_att, COUNT(*) AS student_count FROM students GROUP BY branch HAVING COUNT(*) >= 1 ORDER BY avg_att DESC;",
        "test_cases": [
            {"input": "EXECUTE", "expected": "RESULTS_PRESENT", "hidden": False}
        ],
        "xp_reward": 140
    }
]


def seed_coding_challenges_if_empty():
    """Seeds default curriculum practice challenges if table is empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM coding_challenges")
    count = cursor.fetchone()[0]
    
    if count == 0:
        for ch in DEFAULT_CHALLENGES:
            cursor.execute("""
            INSERT INTO coding_challenges (title, language, difficulty, category, description, starter_code, solution_code, test_cases_json, xp_reward)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ch["title"], ch["language"], ch["difficulty"], ch["category"], ch["description"],
                ch["starter_code"], ch["solution_code"], json.dumps(ch["test_cases"]), ch["xp_reward"]
            ))
        conn.commit()
    conn.close()


def get_student_gamification_profile(student_id: int) -> Dict[str, Any]:
    """Returns XP points, level, unlocked badges, streak status, and rank."""
    seed_coding_challenges_if_empty()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, full_name, roll_no, attendance, learning_streak, xp_points, current_level FROM students WHERE id = ?", (student_id,))
    s_row = cursor.fetchone()

    if not s_row:
        conn.close()
        return {}

    xp = int(s_row["xp_points"] or 450)
    streak = int(s_row["learning_streak"] or 3)
    
    # Calculate Level based on XP
    # Level 1: 0 - 500
    # Level 2: 501 - 1200
    # Level 3: 1201 - 2500
    # Level 4: 2501 - 5000
    # Level 5: 5000+
    if xp >= 5000:
        lvl_num = 5
        lvl_name = "Level 5: Quantum Grandmaster"
        next_threshold = 10000
    elif xp >= 2500:
        lvl_num = 4
        lvl_name = "Level 4: Quantum Explorer"
        next_threshold = 5000
    elif xp >= 1200:
        lvl_num = 3
        lvl_name = "Level 3: Algorithm Specialist"
        next_threshold = 2500
    elif xp >= 500:
        lvl_num = 2
        lvl_name = "Level 2: Apprentice Scholar"
        next_threshold = 1200
    else:
        lvl_num = 1
        lvl_name = "Level 1: Novice Learner"
        next_threshold = 500

    # Fetch unlocked badges
    cursor.execute("SELECT badge_key, badge_name, badge_icon, badge_color, description, unlocked_at FROM student_badges WHERE student_id = ?", (student_id,))
    unlocked_rows = cursor.fetchall()
    unlocked_keys = {r["badge_key"]: dict(r) for r in unlocked_rows}

    # Auto-unlock streak badge if streak >= 5
    if streak >= 5 and "streak_warrior" not in unlocked_keys:
        b_info = next(b for b in ALL_BADGES if b["key"] == "streak_warrior")
        cursor.execute("""
        INSERT OR IGNORE INTO student_badges (student_id, badge_key, badge_name, badge_icon, badge_color, description)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (student_id, b_info["key"], b_info["name"], b_info["icon"], b_info["color"], b_info["description"]))
        conn.commit()
        unlocked_keys["streak_warrior"] = b_info

    # Structure full badge list with locked/unlocked state
    badges_response = []
    for b in ALL_BADGES:
        is_unlocked = b["key"] in unlocked_keys
        b_dict = dict(b)
        b_dict["is_unlocked"] = is_unlocked
        b_dict["unlocked_at"] = unlocked_keys[b["key"]].get("unlocked_at") if is_unlocked else None
        badges_response.append(b_dict)

    conn.close()

    return {
        "student_id": student_id,
        "full_name": s_row["full_name"],
        "roll_no": s_row["roll_no"],
        "xp_points": xp,
        "current_level": lvl_name,
        "level_number": lvl_num,
        "next_level_xp": next_threshold,
        "xp_progress_percentage": round(min(100.0, (xp / next_threshold) * 100.0), 1),
        "learning_streak": streak,
        "total_badges": len(ALL_BADGES),
        "unlocked_badges_count": len(unlocked_keys),
        "badges": badges_response
    }


import ast
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

ALLOWED_SANDBOX_MODULES = {"math", "random", "json", "collections", "itertools", "heapq", "functools", "re", "statistics", "numpy"}

class ASTSandboxValidator(ast.NodeVisitor):
    """Inspects Python AST to reject dangerous constructs and forbidden system access."""
    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        for alias in node.names:
            base_mod = alias.name.split(".")[0]
            if base_mod not in ALLOWED_SANDBOX_MODULES:
                self.errors.append(f"Importing module '{alias.name}' is prohibited in the academic sandbox.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_mod = node.module.split(".")[0]
            if base_mod not in ALLOWED_SANDBOX_MODULES:
                self.errors.append(f"Importing from module '{node.module}' is prohibited in the academic sandbox.")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # Disallow access to dangerous private attributes like __subclasses__, __globals__, __code__
        if node.attr.startswith("__") and node.attr.endswith("__"):
            if node.attr not in {"__name__", "__doc__", "__init__"}:
                self.errors.append(f"Access to internal attribute '{node.attr}' is restricted for security.")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "compile", "open", "input", "breakpoint", "getattr", "setattr", "delattr"}:
                self.errors.append(f"Function call '{node.func.id}()' is disabled in the practice sandbox.")
        self.generic_visit(node)


def execute_python_sandbox_code(code_str: str, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executes student Python code inside a hardened execution namespace with AST validation and strict timeout.
    """
    start_time = time.time()
    
    # 1. AST Validation
    try:
        parsed_ast = ast.parse(code_str)
        validator = ASTSandboxValidator()
        validator.visit(parsed_ast)
        if validator.errors:
            return {
                "success": False,
                "status": "SecurityViolation",
                "error": validator.errors[0],
                "passed_tests": 0,
                "total_tests": len(test_cases),
                "output": "",
                "execution_time_ms": 0.0
            }
    except SyntaxError as syn_err:
        return {
            "success": False,
            "status": "SyntaxError",
            "error": f"SyntaxError on line {syn_err.lineno}: {syn_err.msg}",
            "passed_tests": 0,
            "total_tests": len(test_cases),
            "output": "",
            "execution_time_ms": 0.0
        }

    # Safe built-in namespace
    def safe_import(name, *args, **kwargs):
        base_mod = name.split(".")[0]
        if base_mod in ALLOWED_SANDBOX_MODULES:
            return __import__(name, *args, **kwargs)
        raise ImportError(f"Module '{name}' is restricted in the practice sandbox.")

    safe_globals = {
        "__builtins__": {
            "range": range, "len": len, "int": int, "float": float, "str": str, "bool": bool,
            "list": list, "dict": dict, "set": set, "tuple": tuple, "min": min, "max": max,
            "sum": sum, "abs": abs, "round": round, "print": print, "enumerate": enumerate,
            "zip": zip, "sorted": sorted, "reversed": reversed, "__import__": safe_import,
            "True": True, "False": False, "None": None, "Exception": Exception, "ValueError": ValueError,
            "TypeError": TypeError, "KeyError": KeyError, "IndexError": IndexError
        }
    }
    
    import math
    import random
    safe_globals["math"] = math
    safe_globals["random"] = random

    # 2. Worker runner with 2.0-second timeout
    def _run_student_code():
        local_ns = {}
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            compiled_code = compile(parsed_ast, filename="<student_sandbox>", mode="exec")
            exec(compiled_code, safe_globals, local_ns)
            sys.stdout = old_stdout
            out = stdout_capture.getvalue()
            return True, local_ns, out, None
        except Exception as e:
            sys.stdout = old_stdout
            return False, {}, stdout_capture.getvalue(), e

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_student_code)
        try:
            success, local_ns, exec_output, err = future.result(timeout=2.0)
        except FutureTimeoutError:
            return {
                "success": False,
                "status": "TimeoutError",
                "error": "Execution Timed Out (> 2.0s). Please check your code for infinite loops or heavy operations.",
                "passed_tests": 0,
                "total_tests": len(test_cases),
                "output": "",
                "execution_time_ms": 2000.0
            }

    if not success:
        return {
            "success": False,
            "status": "RuntimeError",
            "error": f"{type(err).__name__}: {str(err)}",
            "traceback": traceback.format_exc(),
            "passed_tests": 0,
            "total_tests": len(test_cases),
            "output": exec_output,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2)
        }

    # Find the main user function in local_ns
    user_func = None
    for k, v in local_ns.items():
        if callable(v):
            user_func = v
            break

    passed_count = 0
    test_results = []

    for t in test_cases:
        in_val = t["input"]
        exp_val = str(t["expected"]).strip()
        
        try:
            if user_func:
                if "," in in_val:
                    args = [eval(arg.strip(), safe_globals) for arg in in_val.split(",")]
                    res = user_func(*args)
                else:
                    arg = eval(in_val, safe_globals) if in_val != "EXECUTE" else None
                    res = user_func(arg) if arg is not None else user_func()
            else:
                res = "executed"

            res_str = str(res).strip()
            try:
                is_pass = abs(float(res_str) - float(exp_val)) < 0.001
            except Exception:
                is_pass = (res_str.lower() == exp_val.lower())

            if is_pass:
                passed_count += 1

            test_results.append({
                "input": in_val,
                "expected": exp_val if not t.get("hidden") else "[Hidden Test Case]",
                "actual": res_str if not t.get("hidden") else ("[Passed]" if is_pass else "[Failed]"),
                "passed": is_pass,
                "hidden": t.get("hidden", False)
            })
        except Exception as te:
            test_results.append({
                "input": in_val,
                "expected": exp_val,
                "actual": f"Error: {te}",
                "passed": False,
                "hidden": t.get("hidden", False)
            })

    total_tests = len(test_cases)
    is_all_passed = (passed_count == total_tests)

    return {
        "success": is_all_passed,
        "status": "Passed" if is_all_passed else "Failed",
        "passed_tests": passed_count,
        "total_tests": total_tests,
        "test_results": test_results,
        "output": exec_output,
        "execution_time_ms": round((time.time() - start_time) * 1000, 2)
    }


def execute_sql_sandbox_query(query_str: str) -> Dict[str, Any]:
    """
    Executes a read-only SQL query against the SQLite database with safe limits.
    """
    start_time = time.time()
    
    # Read-only guard
    upper_q = query_str.strip().upper()
    if any(k in upper_q for k in ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "TRUNCATE"]):
        return {
            "success": False,
            "status": "SecurityError",
            "error": "Only read-only SELECT queries are permitted in the Practice Sandbox.",
            "passed_tests": 0,
            "total_tests": 1,
            "execution_time_ms": 0.0
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query_str)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
        conn.close()

        formatted_rows = [list(r) for r in rows[:20]]
        return {
            "success": True,
            "status": "Passed",
            "passed_tests": 1,
            "total_tests": 1,
            "columns": cols,
            "rows": formatted_rows,
            "row_count": len(rows),
            "output": f"Query returned {len(rows)} records successfully.",
            "execution_time_ms": round((time.time() - start_time) * 1000, 2)
        }
    except Exception as e:
        return {
            "success": False,
            "status": "SQLError",
            "error": str(e),
            "passed_tests": 0,
            "total_tests": 1,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2)
        }
