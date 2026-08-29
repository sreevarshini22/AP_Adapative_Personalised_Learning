"""
Independent Verification and Test Script for Quantum Machine Learning (QML) Model
Executes PennyLane quantum circuit inference on test student feature vectors.
"""

import os
import sys
import json

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.quantum_model import (
    load_quantum_model,
    predict_learning_risk,
    get_qml_status,
    NUM_QUBITS,
    NUM_LAYERS,
    DEVICE_NAME
)


def run_qml_verification():
    print("=" * 70)
    print("      QUANTUM MACHINE LEARNING (QML) INDEPENDENT VERIFICATION")
    print("=" * 70)

    # 1. Check QML System Status
    status = get_qml_status()
    print("SYSTEM STATUS CHECK:")
    for k, v in status.items():
        print(f"  - {k:<24}: {v}")
    print("-" * 70)

    # 2. Test Sample Feature Vector (as requested in spec)
    test_student_sample = {
        "attendance": 80.0,
        "mathematics_score": 75.0,
        "physics_score": 70.0,
        "programming_score": 65.0,
        "assignment_score": 85.0
    }

    print("\nSAMPLE STUDENT INPUT FEATURES:")
    for k, v in test_student_sample.items():
        print(f"  - {k:<24}: {v}")

    # 3. Execute Quantum Inference
    result = predict_learning_risk(test_student_sample)

    print("\n" + "=" * 70)
    print("             QUANTUM ML PREDICTION RESULT")
    print("=" * 70)
    print(f"Risk Level:         {result['risk_level']}")
    print(f"Risk Score:         {result['risk_score']}%")
    print(f"Model:              {result['model']}")
    print(f"Confidence:         {result['confidence']}%")
    print(f"Qubits:             {result['qubits']}")
    print(f"Layers:             {result['layers']}")
    print(f"Device:             {result['device']}")
    print(f"Class Probabilities:{result['probabilities']}")
    print("-" * 70)
    print("Top Risk Drivers / Strengths Identified:")
    for d in result["top_risk_drivers"]:
        print(f"  * {d}")
    print("=" * 70 + "\n")

    # 4. Test At-Risk Student Feature Vector
    weak_student_sample = {
        "attendance": 48.0,
        "mathematics_score": 38.0,
        "physics_score": 42.0,
        "programming_score": 35.0,
        "assignment_score": 50.0
    }
    weak_result = predict_learning_risk(weak_student_sample)

    print("=" * 70)
    print("         AT-RISK STUDENT QUANTUM PREDICTION RESULT")
    print("=" * 70)
    print(f"Risk Level:         {weak_result['risk_level']}")
    print(f"Risk Score:         {weak_result['risk_score']}%")
    print(f"Confidence:         {weak_result['confidence']}%")
    print(f"Probabilities:      {weak_result['probabilities']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_qml_verification()
