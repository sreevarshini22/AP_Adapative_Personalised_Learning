"""
Quantum Machine Learning (QML) Architecture for AP Adaptive Education Platform
Powered by PennyLane (default.qubit simulator, 5 Qubits, Variational Quantum Circuit).

Features mapped to 5 Qubits:
- Qubit 0: Class Attendance (%)
- Qubit 1: Mathematics Score
- Qubit 2: Physics Score
- Qubit 3: Programming Score
- Qubit 4: Assignment Score
"""

import os
import sys
import json
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import pennylane as qml
    PENNYLANE_AVAILABLE = True
except ImportError:
    PENNYLANE_AVAILABLE = False

# Core configuration
NUM_QUBITS = 5
NUM_LAYERS = 2
DEVICE_NAME = "default.qubit"
CLASS_NAMES = ["Low Risk", "Medium Risk", "High Risk"]
QML_FEATURE_COLUMNS = [
    "attendance",
    "mathematics_score",
    "physics_score",
    "programming_score",
    "assignment_score"
]

FEATURE_DISPLAY_NAMES = {
    "attendance": "Class Attendance (%)",
    "mathematics_score": "Mathematics Score",
    "physics_score": "Physics Score",
    "programming_score": "Programming Score",
    "assignment_score": "Assignment Score"
}

FEATURE_BENCHMARKS = {
    "attendance": 75.0,
    "mathematics_score": 60.0,
    "physics_score": 60.0,
    "programming_score": 60.0,
    "assignment_score": 65.0
}

# Global singleton cache for loaded QML model artifacts
_QML_MODEL_CACHE: Optional[Dict[str, Any]] = None


def get_quantum_device():
    """Initializes the PennyLane quantum simulator device."""
    if not PENNYLANE_AVAILABLE:
        raise RuntimeError("PennyLane is not installed. Install via `pip install pennylane`.")
    return qml.device(DEVICE_NAME, wires=NUM_QUBITS)


# Create Quantum Device
if PENNYLANE_AVAILABLE:
    _dev = get_quantum_device()

    @qml.qnode(_dev, interface="autograd", diff_method="parameter-shift")
    def quantum_circuit_node(inputs, circuit_weights):
        """
        Variational Quantum Circuit (VQC) executing on 5 qubits.
        1. Feature Encoding: AngleEmbedding into Y-rotations.
        2. Variational Ansatz: Multi-layer Rotations (Rot) and CNOT Ring Entanglement.
        3. Quantum Measurements: Pauli-Z expectation values across all 5 qubits.
        """
        # Step 1: Quantum Feature Encoding
        qml.AngleEmbedding(inputs, wires=range(NUM_QUBITS), rotation="Y")
        
        # Step 2: Parameterized Variational Layers
        for l in range(NUM_LAYERS):
            # Single-qubit parameterized 3D Euler rotations (phi, theta, omega)
            for i in range(NUM_QUBITS):
                qml.Rot(
                    circuit_weights[l, i, 0],
                    circuit_weights[l, i, 1],
                    circuit_weights[l, i, 2],
                    wires=i
                )
            # Entangling CNOT gates in a closed circular topology
            for i in range(NUM_QUBITS):
                qml.CNOT(wires=[i, (i + 1) % NUM_QUBITS])
                
        # Step 3: Quantum Measurements (Pauli-Z expectation values)
        return [qml.expval(qml.PauliZ(i)) for i in range(NUM_QUBITS)]
else:
    quantum_circuit_node = None


def softmax(x: np.ndarray) -> np.ndarray:
    """Stable softmax computation."""
    e_x = np.exp(x - np.max(x))
    return e_x / np.sum(e_x, axis=-1, keepdims=True)


class QuantumRiskClassifier:
    """
    Quantum Machine Learning Classifier for student learning risk assessment.
    Executes a Parameterized Quantum Circuit with AngleEmbedding and Ring Entanglement.
    """

    def __init__(self, num_qubits: int = NUM_QUBITS, num_layers: int = NUM_LAYERS):
        self.num_qubits = num_qubits
        self.num_layers = num_layers
        self.classes = CLASS_NAMES
        self.feature_columns = QML_FEATURE_COLUMNS
        
        # Trainable parameters
        self.circuit_weights: Optional[np.ndarray] = None  # Shape: (NUM_LAYERS, NUM_QUBITS, 3)
        self.head_weights: Optional[np.ndarray] = None     # Shape: (3, NUM_QUBITS)
        self.head_bias: Optional[np.ndarray] = None        # Shape: (3,)
        
        # Feature Scaler Parameters
        self.scaler_min: np.ndarray = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
        self.scaler_max: np.ndarray = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
        self.is_trained: bool = False

    def init_weights(self, seed: int = 42):
        """Initializes quantum circuit and classical readout head weights."""
        rng = np.random.RandomState(seed)
        # Uniform initial angles between 0 and 2*pi
        self.circuit_weights = rng.uniform(0, 2 * np.pi, size=(self.num_layers, self.num_qubits, 3))
        # Xavier/He normal initialization for readout layer
        self.head_weights = rng.normal(0, 0.5, size=(len(self.classes), self.num_qubits))
        self.head_bias = np.zeros(len(self.classes))

    def fit_scaler(self, X: np.ndarray):
        """Computes min/max for mapping raw features into [0, pi]."""
        self.scaler_min = np.min(X, axis=0)
        self.scaler_max = np.max(X, axis=0)
        # Prevent division by zero
        for idx in range(len(self.scaler_min)):
            if self.scaler_max[idx] <= self.scaler_min[idx]:
                self.scaler_max[idx] = self.scaler_min[idx] + 100.0

    def transform_features(self, X: np.ndarray) -> np.ndarray:
        """Scales numeric features into [0, pi] for angle embedding."""
        X_clipped = np.clip(X, self.scaler_min, self.scaler_max)
        scaled = (X_clipped - self.scaler_min) / (self.scaler_max - self.scaler_min + 1e-8)
        return scaled * np.pi

    def forward_single(self, feature_vector_scaled: np.ndarray) -> np.ndarray:
        """
        Executes quantum circuit inference on a single normalized feature vector.
        Returns class probabilities: [P(Low Risk), P(Medium Risk), P(High Risk)].
        """
        if not PENNYLANE_AVAILABLE or quantum_circuit_node is None:
            raise RuntimeError("PennyLane quantum circuit is unavailable.")
            
        # Execute parameterized quantum circuit
        expvals = np.array(quantum_circuit_node(feature_vector_scaled, self.circuit_weights))
        
        # Readout head projection
        logits = np.dot(self.head_weights, expvals) + self.head_bias
        probs = softmax(logits)
        return probs

    def predict_single(self, student_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates risk for an authenticated student using the quantum model.
        Returns risk level, class probabilities, quantum risk score %, and explainability drivers.
        """
        # Extract 5 core features
        raw_vals = []
        for col in self.feature_columns:
            val = student_dict.get(col, 50.0)
            try:
                val = float(val) if val is not None else 50.0
            except (ValueError, TypeError):
                val = 50.0
            raw_vals.append(val)
            
        raw_array = np.array(raw_vals, dtype=float)
        scaled_input = self.transform_features(raw_array.reshape(1, -1))[0]
        
        # Run Quantum Circuit
        probs = self.forward_single(scaled_input)
        
        prob_dict = {
            self.classes[0]: round(float(probs[0]), 4),
            self.classes[1]: round(float(probs[1]), 4),
            self.classes[2]: round(float(probs[2]), 4)
        }
        
        pred_idx = int(np.argmax(probs))
        pred_class = self.classes[pred_idx]
        confidence = round(float(probs[pred_idx]) * 100.0, 1)
        
        # Composite quantum risk score on 0-100 scale
        p_low = probs[0]
        p_med = probs[1]
        p_high = probs[2]
        risk_score = round(float((p_high * 100.0) + (p_med * 45.0) + (p_low * 10.0)), 1)
        risk_score = max(0.0, min(100.0, risk_score))
        
        # Explainability & Diagnostic Drivers
        risk_drivers = []
        important_features = []
        for idx, col in enumerate(self.feature_columns):
            val = raw_vals[idx]
            benchmark = FEATURE_BENCHMARKS.get(col, 60.0)
            disp_name = FEATURE_DISPLAY_NAMES.get(col, col)
            diff = val - benchmark
            
            if diff < 0:
                detail = f"{disp_name} ({val:g}) is below benchmark ({benchmark:g})"
                risk_drivers.append(detail)
                impact_type = "Risk Factor"
            else:
                detail = f"{disp_name} ({val:g}) meets/exceeds standard ({benchmark:g})"
                impact_type = "Strength Buffer"
                
            important_features.append({
                "feature_key": col,
                "feature_name": disp_name,
                "value": val,
                "benchmark": benchmark,
                "difference": round(diff, 1),
                "impact_type": impact_type,
                "detail": detail
            })
            
        if not risk_drivers:
            risk_drivers.append(f"Student maintains consistent academic indicators across all {self.num_qubits} quantum-evaluated metrics.")
            
        risk_factors = [f for f in important_features if f["impact_type"] == "Risk Factor"]
        strength_factors = [f for f in important_features if f["impact_type"] == "Strength Buffer"]

        return {
            "risk_level": pred_class,
            "risk_score": risk_score,
            "probabilities": prob_dict,
            "confidence": confidence,
            "confidence_percentage": confidence,
            "top_risk_drivers": risk_drivers[:4],
            "risk_drivers": risk_drivers[:4],
            "top_risk_factors": risk_factors[:4],
            "top_strengths": strength_factors[:4],
            "important_features": important_features,
            "explanations": risk_drivers,
            "model_name": "Quantum Machine Learning (PennyLane default.qubit)",
            "model": "Quantum ML",
            "device": DEVICE_NAME,
            "qubits": self.num_qubits,
            "layers": self.num_layers
        }

    def save(self, base_dir: str = "models"):
        """Saves trained quantum weights, scalers, and metadata to JSON files."""
        os.makedirs(base_dir, exist_ok=True)
        
        weights_data = {
            "circuit_weights": self.circuit_weights.tolist() if self.circuit_weights is not None else [],
            "head_weights": self.head_weights.tolist() if self.head_weights is not None else [],
            "head_bias": self.head_bias.tolist() if self.head_bias is not None else [],
            "num_qubits": self.num_qubits,
            "num_layers": self.num_layers,
            "device": DEVICE_NAME
        }
        
        scaler_data = {
            "scaler_min": self.scaler_min.tolist(),
            "scaler_max": self.scaler_max.tolist(),
            "feature_columns": self.feature_columns,
            "normalization_range": [0, "pi"]
        }
        
        weights_path = os.path.join(base_dir, "quantum_weights.json")
        scaler_path = os.path.join(base_dir, "quantum_scaler.json")
        
        with open(weights_path, "w") as f:
            json.dump(weights_data, f, indent=2)
            
        with open(scaler_path, "w") as f:
            json.dump(scaler_data, f, indent=2)
            
        # Also mirror into ml/ directory for immediate package accessibility
        ml_dir = os.path.join(PROJECT_ROOT, "ml")
        os.makedirs(ml_dir, exist_ok=True)
        with open(os.path.join(ml_dir, "quantum_weights.json"), "w") as f:
            json.dump(weights_data, f, indent=2)
        with open(os.path.join(ml_dir, "quantum_scaler.json"), "w") as f:
            json.dump(scaler_data, f, indent=2)

    @classmethod
    def load(cls, base_dir: str = "models") -> "QuantumRiskClassifier":
        """Loads trained quantum weights and scaler from JSON files."""
        weights_path = os.path.join(base_dir, "quantum_weights.json")
        scaler_path = os.path.join(base_dir, "quantum_scaler.json")
        
        if not os.path.exists(weights_path):
            # Fallback to ml/ directory if needed
            alt_weights = os.path.join(PROJECT_ROOT, "ml", "quantum_weights.json")
            alt_scaler = os.path.join(PROJECT_ROOT, "ml", "quantum_scaler.json")
            if os.path.exists(alt_weights):
                weights_path = alt_weights
                scaler_path = alt_scaler
            else:
                raise FileNotFoundError(f"Quantum weights not found at {weights_path} or {alt_weights}")
                
        with open(weights_path, "r") as f:
            weights_data = json.load(f)
            
        with open(scaler_path, "r") as f:
            scaler_data = json.load(f)
            
        instance = cls(
            num_qubits=weights_data.get("num_qubits", NUM_QUBITS),
            num_layers=weights_data.get("num_layers", NUM_LAYERS)
        )
        instance.circuit_weights = np.array(weights_data["circuit_weights"])
        instance.head_weights = np.array(weights_data["head_weights"])
        instance.head_bias = np.array(weights_data["head_bias"])
        
        instance.scaler_min = np.array(scaler_data["scaler_min"])
        instance.scaler_max = np.array(scaler_data["scaler_max"])
        instance.feature_columns = scaler_data.get("feature_columns", QML_FEATURE_COLUMNS)
        instance.is_trained = True
        
        return instance


def load_quantum_model(models_dir: str = "models") -> QuantumRiskClassifier:
    """Loads and caches the Quantum Machine Learning classifier."""
    global _QML_MODEL_CACHE
    if _QML_MODEL_CACHE is None:
        try:
            model = QuantumRiskClassifier.load(base_dir=models_dir)
            _QML_MODEL_CACHE = {"model": model, "status": "Ready"}
        except Exception as e:
            # If not trained yet, attempt auto-training
            from ml.train_qml_model import train_qml_model
            train_qml_model()
            model = QuantumRiskClassifier.load(base_dir=models_dir)
            _QML_MODEL_CACHE = {"model": model, "status": "Ready"}
            
    return _QML_MODEL_CACHE["model"]


def predict_learning_risk(student_data: Dict[str, Any]) -> Dict[str, Any]:
    """Primary entrypoint: Evaluates student data using Quantum ML."""
    model = load_quantum_model()
    return model.predict_single(student_data)


def get_qml_status() -> Dict[str, Any]:
    """Returns technical readiness and status parameters of the QML system."""
    weights_path = os.path.join(PROJECT_ROOT, "models", "quantum_weights.json")
    weights_exist = os.path.exists(weights_path) or os.path.exists(os.path.join(PROJECT_ROOT, "ml", "quantum_weights.json"))
    
    return {
        "quantum_ml_available": "YES" if PENNYLANE_AVAILABLE and weights_exist else "NO",
        "pennylane": "installed" if PENNYLANE_AVAILABLE else "not installed",
        "device": DEVICE_NAME,
        "qubits": NUM_QUBITS,
        "layers": NUM_LAYERS,
        "weights_loaded": "YES" if weights_exist else "NO",
        "training_completed": "YES" if weights_exist else "NO",
        "feature_count": len(QML_FEATURE_COLUMNS),
        "features": QML_FEATURE_COLUMNS
    }
