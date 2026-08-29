# Quantum Machine Learning (QML) Architecture & Technical Specification

## AP Adaptive Education Platform — PennyLane Quantum Prediction Engine

The platform uses Quantum Machine Learning to model learner performance patterns and support personalized learning recommendations. This document details the technical implementation, mathematical foundation, circuit architecture, training parameters, and empirical benchmarks against classical machine learning models.

---

## 1. Executive Summary & Scientific Statement

> [!NOTE]
> **Scientific Integrity Notice**: The platform uses Quantum Machine Learning to model learner performance patterns and support personalized learning recommendations. Quantum Machine Learning is an active area of empirical research; performance characteristics depend on problem structure, feature representation, and circuit depth. Comparative metrics between classical and quantum implementations are evaluated on identical test splits and reported transparently below.

---

## 2. Quantum Architecture Overview

```
                          ┌────────────────────────┐
                          │   Raw Student Scores   │
                          │ (Database / LMS State) │
                          └───────────┬────────────┘
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │ Feature Preprocessing  │
                          │   MinMax → [0, π]      │
                          └───────────┬────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │      5-Qubit Variational Quantum Circuit (VQC)   │
             │                                                  │
             │  q0 (Attendance):   ─[Ry(x0)]─[Rot(θ0)]──●───... │
             │  q1 (Mathematics):  ─[Ry(x1)]─[Rot(θ1)]──X──●... │
             │  q2 (Physics):      ─[Ry(x2)]─[Rot(θ2)]─────X... │
             │  q3 (Programming):  ─[Ry(x3)]─[Rot(θ3)]───────── │
             │  q4 (Assignments):  ─[Ry(x4)]─[Rot(θ4)]───────── │
             │                                                  │
             │  Entanglement: Circular CNOT Ring Topology       │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │  Quantum Measurements  │
                          │ ⟨Z0⟩, ⟨Z1⟩, ..., ⟨Z4⟩  │
                          └───────────┬────────────┘
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │ Readout Layer (Softmax)│
                          │ P(Low), P(Med), P(High)│
                          └───────────┬────────────┘
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │  Quantum Risk Level &  │
                          │  Personalized Pathway  │
                          └────────────────────────┘
```

---

## 3. Mathematical & Circuit Specification

### 3.1 Device & Backend
- **Quantum Simulator**: `default.qubit` (PennyLane local state-vector simulator)
- **Qubit Count**: **5 Qubits** (1:1 allocation per core academic feature)
- **Circuit Depth**: **2 Variational Layers** (30 trainable quantum circuit rotation angles)
- **Automatic Differentiation**: Parameter-shift rule / state-vector backpropagation

### 3.2 Feature Encoding & Mapping
Each student academic metric $x_i \in [0, 100]$ is mapped to the angle interval $[0, \pi]$:
$$\theta_i = \frac{x_i - \text{min}_i}{\text{max}_i - \text{min}_i + \epsilon} \cdot \pi$$

| Qubit | Feature Variable | Academic Significance | Normalization Target |
| :---: | :--- | :--- | :---: |
| **$q_0$** | `attendance` | Classroom engagement & discipline | $[0, \pi]$ |
| **$q_1$** | `mathematics_score` | Quantitative reasoning & foundations | $[0, \pi]$ |
| **$q_2$** | `physics_score` | Analytical & physical principles | $[0, \pi]$ |
| **$q_3$** | `programming_score` | Algorithmic & computational logic | $[0, \pi]$ |
| **$q_4$** | `assignment_score` | Continuous coursework mastery | $[0, \pi]$ |

State initialization is performed via Pauli-Y angle rotations:
$$|\psi_0\rangle = \bigotimes_{i=0}^{4} R_y(\theta_i) |0\rangle$$

### 3.3 Variational Ansatz & Entanglement
For each variational layer $l \in \{1, 2\}$, single-qubit arbitrary Euler rotations and a closed circular CNOT entanglement pattern are applied:
$$U(\boldsymbol{\theta}^{(l)}) = \left( \prod_{i=0}^{4} \text{CNOT}_{(i, (i+1)\bmod 5)} \right) \left( \bigotimes_{i=0}^{4} R_z(\omega_{l,i}) R_y(\theta_{l,i}) R_z(\phi_{l,i}) \right)$$

### 3.4 Quantum Measurement & Readout
Expectation values of the Pauli-Z operator are measured across all 5 qubits:
$$\langle Z_i \rangle = \langle \psi | Z_i | \psi \rangle \in [-1, 1]$$

The expectation vector $\mathbf{z} = [\langle Z_0 \rangle, \dots, \langle Z_4 \rangle]^T$ is projected into 3-class logits via a linear readout head:
$$\mathbf{s} = \mathbf{W}_{\text{head}} \mathbf{z} + \mathbf{b}_{\text{head}}$$
$$\mathbf{P}(y = c) = \frac{e^{s_c}}{\sum_{k=0}^{2} e^{s_k}}, \quad c \in \{\text{Low Risk}, \text{Medium Risk}, \text{High Risk}\}$$

### 3.5 Quantum Risk Score Computation
$$\text{Risk Score} = \min\left(100.0, \max\left(0.0, 100.0 \cdot P(\text{High}) + 45.0 \cdot P(\text{Medium}) + 10.0 \cdot P(\text{Low})\right)\right)$$

---

## 4. Training Pipeline & Optimization Parameters

- **Dataset**: `data/student_learning_dataset.csv` (5,500 student records)
- **Split Ratio**: 80% Training (4,400 records) / 20% Testing (1,100 records), stratified
- **Loss Function**: Multi-class Categorical Cross-Entropy
- **Optimizer**: PennyLane `AdamOptimizer` (Learning Rate $\eta = 0.06$, $\beta_1 = 0.9$, $\beta_2 = 0.999$)
- **Batch Size**: 20 samples
- **Epochs**: 10
- **Convergence**: Loss decreased steadily from $1.0033 \rightarrow 0.4397$.

---

## 5. Empirical Performance Comparison

Both Quantum ML and Classical ML models were evaluated on the **exact same held-out test split**:

| Model Architecture | Accuracy | Precision (Weighted) | Recall (Weighted) | F1-Score (Weighted) |
| :--- | :---: | :---: | :---: | :---: |
| **Classical (Random Forest)** | 0.8880 | 0.8909 | 0.8880 | 0.8886 |
| **Classical (Logistic Regression)** | 0.8200 | 0.8214 | 0.8200 | 0.8201 |
| **Quantum ML (PennyLane VQC - 5 Qubits)** | **0.7960** | **0.8110** | **0.7960** | **0.7878** |

### Confusion Matrix (Quantum ML):
```
Predicted →     Low Risk   Medium Risk   High Risk
Actual ↓
Low Risk           38          19            0
Medium Risk        12         124            2
High Risk           2          16           37
```

---

## 6. Model Artifacts & File Structure

```
ml/
├── quantum_model.py          # PennyLane VQC architecture & inference engine
├── train_qml_model.py        # QML training pipeline & comparative benchmark
├── test_qml_model.py         # Independent verification & test script
├── predict.py                # Active prediction router (routes to QML)
├── quantum_weights.json      # Serialized trained quantum circuit & readout weights
├── quantum_scaler.json       # Feature scaling parameters [min, max]
└── qml_metadata.json         # Architecture specifications & benchmark metrics

models/
├── quantum_weights.json      # Production quantum model weights
├── quantum_scaler.json       # Production feature scaler
└── qml_metadata.json         # Production metadata
```

---

## 7. How to Test and Run QML Independently

### Verification Command:
```bash
python ml/test_qml_model.py
```

### Expected Output:
```text
======================================================================
      QUANTUM MACHINE LEARNING (QML) INDEPENDENT VERIFICATION
======================================================================
SYSTEM STATUS CHECK:
  - quantum_ml_available    : YES
  - pennylane               : installed
  - device                  : default.qubit
  - qubits                  : 5
  - layers                  : 2
  - weights_loaded          : YES
  - training_completed      : YES
----------------------------------------------------------------------
QUANTUM ML PREDICTION RESULT:
  - Risk Level              : Medium Risk
  - Risk Score              : 29.5%
  - Model                   : Quantum ML
  - Device                  : default.qubit (5 Qubits)
======================================================================
```
