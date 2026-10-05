"""
Verification Test Suite for Interactive Quantum ML Circuit Visualizer & SHAP Explainability Engine.
"""

import os
import sys
import unittest
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import app


class TestQuantumVisualizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_01_circuit_state_endpoint(self):
        """Circuit state endpoint returns 5-qubit topology, gates, and parameters."""
        res = self.client.get("/api/ml/quantum/circuit-state")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["num_qubits"], 5)
        self.assertEqual(data["num_layers"], 2)
        self.assertEqual(len(data["qubit_mappings"]), 5)
        self.assertEqual(len(data["entanglement_topology"]), 5)
        self.assertIn("circuit_weights", data)

    def test_02_live_quantum_simulation_and_shap_drivers(self):
        """Live simulation endpoint computes angles, expectation values, and SHAP contributions."""
        payload = {
            "attendance": 88.0,
            "assessment_performance": 76.0,
            "topic_mastery": 70.0,
            "assignment_performance": 82.0,
            "learning_engagement": 65.0
        }
        res = self.client.post(
            "/api/ml/quantum/simulate-live",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["encoded_angles_rad"]), 5)
        self.assertEqual(len(data["pauli_z_expectations"]), 5)
        self.assertIn("risk_prediction", data)
        self.assertIn("shap_contributions", data)
        self.assertEqual(len(data["shap_contributions"]), 5)


if __name__ == "__main__":
    unittest.main()
