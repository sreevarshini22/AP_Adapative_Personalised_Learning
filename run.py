"""
AP Adaptive Education Platform — Main Application Launcher
Coordinates dataset verification, ML model artifacts, database initialization,
and starts the Flask REST API & Web Dashboard.
"""

import os
import sys

# Ensure root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import init_db, seed_demo_data
from backend.app import create_app

def ensure_environment():
    print("=" * 75)
    print("  AP ADAPTIVE PERSONALISED LEARNING PLATFORM — INITIALIZING SYSTEM")
    print("=" * 75)
    
    # 1. Check ML & Quantum ML Engine Status
    from ml.quantum_model import get_qml_status
    qml_status = get_qml_status()
    print("[*] QUANTUM MACHINE LEARNING (QML) ENGINE STATUS:")
    print(f"    Quantum ML: {qml_status.get('quantum_ml_available', 'NOT AVAILABLE')}")
    print(f"    Framework:  {'PennyLane' if qml_status.get('pennylane') == 'installed' else 'Not Installed'}")
    print(f"    Device:     {qml_status.get('device', 'default.qubit')}")
    print(f"    Qubits:     {qml_status.get('qubits', 5)}")
    print(f"    Layers:     {qml_status.get('layers', 2)}")
    print(f"    Weights:    {'LOADED' if qml_status.get('weights_loaded') == 'YES' else 'NOT LOADED'}")
        
    # 2. Initialize Database & Seed Demo Data
    print("\n[*] Initializing SQLite database and verifying demo accounts...")
    init_db()
    seed_demo_data()
    print("[+] Database ready at database/students.db")
    print("=" * 75)

def main():
    ensure_environment()
    app = create_app()
    
    print("\n" + "*" * 75)
    print("  AP ADAPTIVE PERSONALISED LEARNING PLATFORM IS RUNNING!")
    print("  -----------------------------------------------------------------------")
    print("  - Main Portal / Landing Page:  http://127.0.0.1:5000/")
    print("  - Student Login:              http://127.0.0.1:5000/student-login")
    print("  - Faculty Dashboard:          http://127.0.0.1:5000/teacher-login")
    print("  - ML Benchmark & Metrics:     http://127.0.0.1:5000/ml-performance")
    print("  -----------------------------------------------------------------------")
    print("  DEMO CREDENTIALS:")
    print("  - Student: student@example.com / student123")
    print("  - Faculty: teacher@example.com / teacher123")
    print("*" * 75 + "\n")
    
    app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == "__main__":
    main()
