"""
Quantum Machine Learning Training Pipeline for AP Adaptive Education Platform
Trains a 5-qubit Variational Quantum Circuit (VQC) with PennyLane on student academic data.
Also computes an honest, empirical comparison against Classical ML on identical test splits.
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

# Ensure project root is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pennylane as qml
from pennylane import numpy as pnp

from ml.quantum_model import (
    QuantumRiskClassifier,
    NUM_QUBITS,
    NUM_LAYERS,
    DEVICE_NAME,
    CLASS_NAMES,
    QML_FEATURE_COLUMNS,
    softmax
)

LABEL_MAP = {"Low Risk": 0, "Medium Risk": 1, "High Risk": 2}
INV_LABEL_MAP = {0: "Low Risk", 1: "Medium Risk", 2: "High Risk"}

# Initialize dedicated PennyLane autograd device for training
dev_train = qml.device(DEVICE_NAME, wires=NUM_QUBITS)

@qml.qnode(dev_train, interface="autograd", diff_method="backprop")
def qnode_train(features, weights):
    qml.AngleEmbedding(features, wires=range(NUM_QUBITS), rotation="Y")
    for l in range(NUM_LAYERS):
        for i in range(NUM_QUBITS):
            qml.Rot(weights[l, i, 0], weights[l, i, 1], weights[l, i, 2], wires=i)
        for i in range(NUM_QUBITS):
            qml.CNOT(wires=[i, (i + 1) % NUM_QUBITS])
    return [qml.expval(qml.PauliZ(i)) for i in range(NUM_QUBITS)]


def cost_fn(c_weights, h_weights, h_bias, X_batch=None, y_batch=None):
    """Categorical Cross-Entropy loss over quantum batch."""
    loss = 0.0
    for x_i, y_i in zip(X_batch, y_batch):
        expvals = pnp.stack(qnode_train(x_i, c_weights))
        logits = pnp.dot(h_weights, expvals) + h_bias
        # Numerical log_softmax
        max_l = pnp.max(logits)
        log_sum_exp = max_l + pnp.log(pnp.sum(pnp.exp(logits - max_l)))
        loss = loss - logits[y_i] + log_sum_exp
    return loss / len(X_batch)


def load_and_inspect_dataset(csv_path="data/student_learning_dataset.csv"):
    """Loads and inspects the existing project dataset."""
    if not os.path.exists(csv_path):
        from data.generate_dataset import generate_student_dataset
        print("Dataset not found. Generating dataset (5,500 records)...", flush=True)
        df = generate_student_dataset(n_samples=5500, seed=42)
        df.to_csv(csv_path, index=False)
    else:
        df = pd.read_csv(csv_path)

    print("\n" + "=" * 75, flush=True)
    print("      DATASET INSPECTION & ACADEMIC AUDIT", flush=True)
    print("=" * 75, flush=True)
    print(f"Total samples:        {len(df):,}", flush=True)
    print(f"Total features in DF: {len(df.columns)}", flush=True)
    print(f"QML Input features:   {QML_FEATURE_COLUMNS}", flush=True)
    print(f"Target classes:       {CLASS_NAMES}", flush=True)
    print("Class distribution:", flush=True)
    for k, v in df["risk_level"].value_counts().items():
        pct = (v / len(df)) * 100
        print(f"  - {k:<12}: {v:,} ({pct:.1f}%)", flush=True)
    print("=" * 75 + "\n", flush=True)

    return df


def train_qml_model(
    epochs: int = 10,
    batch_size: int = 20,
    lr: float = 0.06,
    train_samples: int = 150,
    test_eval_samples: int = 250,
    seed: int = 42
):
    """
    Main training workflow for PennyLane Quantum Machine Learning model.
    """
    print("=" * 75, flush=True)
    print("      PENNYLANE QUANTUM MACHINE LEARNING (QML) TRAINING PIPELINE", flush=True)
    print("=" * 75, flush=True)
    print(f"Device:           {DEVICE_NAME} (Local Quantum Simulator)", flush=True)
    print(f"Qubits:           {NUM_QUBITS} (1 Qubit per Academic Feature)", flush=True)
    print(f"Variational Depth:{NUM_LAYERS} Layers (Rotations + Circular Entanglement)", flush=True)
    print(f"Encoding Method:  AngleEmbedding (Y-Rotations mapped to [0, pi])", flush=True)
    print(f"Target Dimension: 3 Classes (Low Risk, Medium Risk, High Risk)", flush=True)
    print("=" * 75 + "\n", flush=True)

    # 1. Load dataset
    df = load_and_inspect_dataset()

    X_raw = df[QML_FEATURE_COLUMNS].values
    y_raw = df["risk_level"].map(LABEL_MAP).values

    # Stratified 80/20 train/test split
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y_raw, test_size=0.20, random_state=seed, stratify=y_raw
    )

    print(f"Training samples: {len(X_train_raw):,} | Testing samples: {len(X_test_raw):,}", flush=True)

    # 2. Instantiate Quantum Model and fit scaler
    qml_model = QuantumRiskClassifier(num_qubits=NUM_QUBITS, num_layers=NUM_LAYERS)
    qml_model.fit_scaler(X_train_raw)

    # 3. Transform inputs into angle space [0, pi]
    X_train_scaled = qml_model.transform_features(X_train_raw)
    X_test_scaled = qml_model.transform_features(X_test_raw)

    # Convert to PennyLane autograd arrays
    pnp.random.seed(seed)
    c_weights = pnp.random.uniform(0, 2 * np.pi, size=(NUM_LAYERS, NUM_QUBITS, 3), requires_grad=True)
    h_weights = pnp.random.normal(0, 0.5, size=(3, NUM_QUBITS), requires_grad=True)
    h_bias = pnp.zeros(3, requires_grad=True)

    # Select representative training subset
    sub_idx = np.random.RandomState(seed).choice(len(X_train_scaled), min(train_samples, len(X_train_scaled)), replace=False)
    X_train_sub = pnp.array(X_train_scaled[sub_idx], requires_grad=False)
    y_train_sub = pnp.array(y_train[sub_idx], requires_grad=False)

    opt = qml.AdamOptimizer(stepsize=lr)

    print(f"\nTraining Quantum Circuit on {len(X_train_sub)} samples across {epochs} epochs...", flush=True)
    start_time = time.time()

    n_samples = len(X_train_sub)
    n_batches = int(np.ceil(n_samples / batch_size))

    for epoch in range(1, epochs + 1):
        perm = np.random.permutation(n_samples)
        epoch_loss = 0.0

        for b in range(n_batches):
            b_idx = perm[b * batch_size : (b + 1) * batch_size]
            X_b = X_train_sub[b_idx]
            y_b = y_train_sub[b_idx]

            (c_weights, h_weights, h_bias), loss_val = opt.step_and_cost(
                cost_fn, c_weights, h_weights, h_bias, X_batch=X_b, y_batch=y_b
            )
            epoch_loss += float(loss_val) * len(b_idx)

        avg_epoch_loss = epoch_loss / n_samples
        print(f" Epoch {epoch:02d}/{epochs:02d} | Quantum Cross-Entropy Loss: {avg_epoch_loss:.4f}", flush=True)

    train_duration = time.time() - start_time
    print(f"\n[+] Quantum training completed in {train_duration:.2f} seconds.", flush=True)

    # Update model weights with trained parameters
    qml_model.circuit_weights = np.array(c_weights)
    qml_model.head_weights = np.array(h_weights)
    qml_model.head_bias = np.array(h_bias)
    qml_model.is_trained = True

    # 4. Evaluate Quantum ML on test split
    print(f"\nEvaluating Quantum ML on {min(test_eval_samples, len(X_test_scaled))} held-out test samples...", flush=True)
    eval_n = min(test_eval_samples, len(X_test_scaled))
    eval_X_scaled = X_test_scaled[:eval_n]
    eval_X_raw = X_test_raw[:eval_n]
    eval_y = y_test[:eval_n]

    qml_preds = []
    for i in range(eval_n):
        probs = qml_model.forward_single(eval_X_scaled[i])
        qml_preds.append(np.argmax(probs))

    qml_preds = np.array(qml_preds)

    qml_acc = float(accuracy_score(eval_y, qml_preds))
    qml_prec = float(precision_score(eval_y, qml_preds, average="weighted", zero_division=0))
    qml_rec = float(recall_score(eval_y, qml_preds, average="weighted", zero_division=0))
    qml_f1 = float(f1_score(eval_y, qml_preds, average="weighted", zero_division=0))
    qml_cm = confusion_matrix(eval_y, qml_preds).tolist()
    qml_clf_report = classification_report(eval_y, qml_preds, target_names=CLASS_NAMES, output_dict=True, zero_division=0)

    # 5. Train & Evaluate Classical ML on the EXACT SAME 5 features and test split
    print("Evaluating Classical ML Benchmark (Random Forest & Logistic Regression)...", flush=True)
    clf_rf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=seed)
    clf_rf.fit(X_train_raw, y_train)
    rf_preds = clf_rf.predict(eval_X_raw)

    rf_acc = float(accuracy_score(eval_y, rf_preds))
    rf_prec = float(precision_score(eval_y, rf_preds, average="weighted", zero_division=0))
    rf_rec = float(recall_score(eval_y, rf_preds, average="weighted", zero_division=0))
    rf_f1 = float(f1_score(eval_y, rf_preds, average="weighted", zero_division=0))

    clf_lr = LogisticRegression(max_iter=1000, random_state=seed)
    clf_lr.fit(X_train_raw, y_train)
    lr_preds = clf_lr.predict(eval_X_raw)

    lr_acc = float(accuracy_score(eval_y, lr_preds))
    lr_prec = float(precision_score(eval_y, lr_preds, average="weighted", zero_division=0))
    lr_rec = float(recall_score(eval_y, lr_preds, average="weighted", zero_division=0))
    lr_f1 = float(f1_score(eval_y, lr_preds, average="weighted", zero_division=0))

    # 6. Save Quantum Weights, Scaler, and Metadata
    qml_model.save("models")

    metadata = {
        "framework": "PennyLane",
        "device": DEVICE_NAME,
        "qubits": NUM_QUBITS,
        "layers": NUM_LAYERS,
        "encoding": "AngleEmbedding (Y-axis rotation mapped to [0, pi])",
        "optimizer": "Adam",
        "epochs": epochs,
        "training_time_seconds": round(train_duration, 2),
        "dataset_summary": {
            "total_samples": len(df),
            "train_samples": len(X_train_raw),
            "test_samples": len(X_test_raw),
            "features": QML_FEATURE_COLUMNS,
            "classes": CLASS_NAMES
        },
        "quantum_metrics": {
            "accuracy": round(qml_acc, 4),
            "precision_weighted": round(qml_prec, 4),
            "recall_weighted": round(qml_rec, 4),
            "f1_weighted": round(qml_f1, 4),
            "confusion_matrix": qml_cm,
            "classification_report": qml_clf_report
        },
        "classical_rf_metrics": {
            "accuracy": round(rf_acc, 4),
            "precision_weighted": round(rf_prec, 4),
            "recall_weighted": round(rf_rec, 4),
            "f1_weighted": round(rf_f1, 4)
        },
        "classical_lr_metrics": {
            "accuracy": round(lr_acc, 4),
            "precision_weighted": round(lr_prec, 4),
            "recall_weighted": round(lr_rec, 4),
            "f1_weighted": round(lr_f1, 4)
        }
    }

    meta_path = os.path.join("models", "qml_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Mirror to ml/ for package completeness
    with open(os.path.join("ml", "qml_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[+] Saved Quantum Weights -> models/quantum_weights.json & ml/quantum_weights.json", flush=True)
    print(f"[+] Saved Quantum Scaler  -> models/quantum_scaler.json & ml/quantum_scaler.json", flush=True)
    print(f"[+] Saved QML Metadata    -> {meta_path}", flush=True)

    # 7. Print Comparative Evaluation Table
    header = f"{'Model Architecture':<30} | {'Accuracy':<10} | {'Precision (W)':<14} | {'Recall (W)':<12} | {'F1-Score (W)':<12}"
    divider = "-" * len(header)
    print("\n" + divider, flush=True)
    print("       CLASSICAL ML vs. QUANTUM ML EMPIRICAL BENCHMARK TABLE", flush=True)
    print(divider, flush=True)
    print(header, flush=True)
    print(divider, flush=True)
    print(f"{'Classical (Random Forest)':<30} | {rf_acc:<10.4f} | {rf_prec:<14.4f} | {rf_rec:<12.4f} | {rf_f1:<12.4f}", flush=True)
    print(f"{'Classical (Logistic Reg)':<30} | {lr_acc:<10.4f} | {lr_prec:<14.4f} | {lr_rec:<12.4f} | {lr_f1:<12.4f}", flush=True)
    print(f"{'Quantum ML (PennyLane VQC)':<30} | {qml_acc:<10.4f} | {qml_prec:<14.4f} | {qml_rec:<12.4f} | {qml_f1:<12.4f}", flush=True)
    print(divider + "\n", flush=True)

    return metadata


if __name__ == "__main__":
    train_qml_model(epochs=10, batch_size=20, lr=0.06, train_samples=150, test_eval_samples=250)
