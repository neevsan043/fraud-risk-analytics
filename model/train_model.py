"""
Model training pipeline for transaction fraud detection.

Trains and evaluates baseline Logistic Regression and XGBoost classifiers
on PCA features and engineered transaction features, optimizing for
precision-recall AUC given the highly imbalanced class distribution.
"""
import sqlite3
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, precision_recall_curve, average_precision_score,
    confusion_matrix, roc_auc_score,
)
from xgboost import XGBClassifier
import joblib

CSV_DIR = "data/processed"
DB_PATH = "data/processed/fraud_analytics.db"
MODEL_VERSION = "v1_xgb_20260825"

def load_data():
    model_feat = pd.read_csv(f"{CSV_DIR}/model_features.csv")
    eng_feat = pd.read_csv(f"{CSV_DIR}/transaction_features.csv")
    df = model_feat.merge(eng_feat, on="transaction_id")
    y = df["class"]
    X = df.drop(columns=["transaction_id", "class"])
    return df["transaction_id"], X, y


def evaluate(name, y_test, y_pred, y_proba):
    print(f"\n=== {name} ===")
    print(classification_report(y_test, y_pred, target_names=["legit", "fraud"], digits=4))
    print("Confusion matrix [[TN FP][FN TP]]:")
    print(confusion_matrix(y_test, y_pred))
    print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.4f}")
    print(f"PR-AUC (average precision): {average_precision_score(y_test, y_proba):.4f}")


def main():
    txn_ids, X, y = load_data()

    X_train, X_test, y_train, y_test, id_train, id_test = train_test_split(
        X, y, txn_ids, test_size=0.25, stratify=y, random_state=42
    )
    print(f"Train: {X_train.shape}, fraud rate {y_train.mean():.4%}")
    print(f"Test:  {X_test.shape}, fraud rate {y_test.mean():.4%}")

    # ---- Baseline: Logistic Regression ----
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    logreg = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
    logreg.fit(X_train_s, y_train)
    lr_proba = logreg.predict_proba(X_test_s)[:, 1]
    lr_pred = (lr_proba >= 0.5).astype(int)
    evaluate("Logistic Regression (baseline, class_weight=balanced)", y_test, lr_pred, lr_proba)

    # ---- XGBoost with scale_pos_weight for imbalance ----
    pos = y_train.sum()
    neg = len(y_train) - pos
    scale_pos_weight = neg / pos
    print(f"\nXGBoost scale_pos_weight = {scale_pos_weight:.1f} (neg/pos ratio in train set)")

    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.08,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )
    xgb.fit(X_train, y_train)
    xgb_proba = xgb.predict_proba(X_test)[:, 1]
    xgb_pred = (xgb_proba >= 0.5).astype(int)
    evaluate("XGBoost (scale_pos_weight)", y_test, xgb_pred, xgb_proba)

    # Compute feature importances
    importances = pd.Series(xgb.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\nTop 10 feature importances (XGBoost):")
    print(importances.head(10))

    # ---- Score all transactions with final model ----
    print("\nScoring full dataset for fraud_flags table...")
    full_proba = xgb.predict_proba(X)[:, 1]
    full_pred = (full_proba >= 0.5).astype(int)
    flags = pd.DataFrame({
        "transaction_id": txn_ids,
        "fraud_score": full_proba.round(4),
        "predicted_label": full_pred,
        "model_version": MODEL_VERSION,
    })

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS fraud_flags")
    conn.execute("""
        CREATE TABLE fraud_flags (
            transaction_id INTEGER PRIMARY KEY,
            fraud_score REAL NOT NULL,
            predicted_label INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            scored_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
        )
    """)
    flags.to_sql("fraud_flags", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    print(f"Wrote {len(flags)} rows to fraud_flags. Flagged as fraud: {flags['predicted_label'].sum()}")

    # Save model artifacts
    joblib.dump(xgb, "model/xgb_model.joblib")
    joblib.dump(scaler, "model/scaler.joblib")
    importances.to_csv("model/feature_importances.csv", header=["importance"])
    print("Model saved to model/xgb_model.joblib")


if __name__ == "__main__":
    main()
