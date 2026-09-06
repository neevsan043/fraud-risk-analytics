import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
from pathlib import Path

# Paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
POWERBI_DIR = BASE_DIR / "powerbi"

def export_full_dataset_performance():
    print("Loading processed transaction data...")
    model_df = pd.read_csv(PROCESSED_DIR / "model_features.csv")
    context_df = pd.read_csv(PROCESSED_DIR / "transaction_features.csv")
    
    df = model_df.merge(context_df, on="transaction_id")
    X = df.drop(columns=["transaction_id", "class"])
    y = df["class"]
    txn_ids = df["transaction_id"]
    
    print("Fitting model with class weighting...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    ratio = (len(y_train) - sum(y_train)) / sum(y_train)
    
    model = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        scale_pos_weight=ratio,
        random_state=42
    )
    model.fit(X_train, y_train)
    
    print("Generating predictions across all transactions...")
    full_preds = model.predict(X)
    full_probs = model.predict_proba(X)[:, 1]
    
    tn, fp, fn, tp = confusion_matrix(y, full_preds).ravel()
    
    total = len(y)
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    f1 = 2 * (precision * recall) / (precision + recall)
    accuracy = (tp + tn) / total
    specificity = tn / (tn + fp)
    
    summary_df = pd.DataFrame([{
        "evaluation_scope": "Full Dataset (100%)",
        "total_transactions": total,
        "true_positives_tp": tp,
        "false_positives_fp": fp,
        "false_negatives_fn": fn,
        "true_negatives_tn": tn,
        "precision_pct": round(precision * 100, 2),
        "recall_pct": round(recall * 100, 2),
        "f1_score_pct": round(f1 * 100, 2),
        "accuracy_pct": round(accuracy * 100, 4),
        "specificity_pct": round(specificity * 100, 4)
    }])
    
    predictions_df = pd.DataFrame({
        "transaction_id": txn_ids,
        "actual_label": y.values,
        "predicted_label": full_preds,
        "fraud_probability": full_probs
    })
    
    def get_cm_category(row):
        if row["actual_label"] == 1 and row["predicted_label"] == 1:
            return "True Positive (TP)"
        elif row["actual_label"] == 0 and row["predicted_label"] == 1:
            return "False Positive (FP)"
        elif row["actual_label"] == 1 and row["predicted_label"] == 0:
            return "False Negative (FN)"
        else:
            return "True Negative (TN)"
            
    predictions_df["confusion_matrix_category"] = predictions_df.apply(get_cm_category, axis=1)
    
    summary_path = POWERBI_DIR / "full_dataset_performance_report.csv"
    preds_path = POWERBI_DIR / "full_dataset_predictions.csv"
    
    summary_df.to_csv(summary_path, index=False)
    predictions_df.to_csv(preds_path, index=False)
    
    print("Exports completed:")
    print(f"  -> Performance Report: {summary_path}")
    print(f"  -> Predictions Ledger: {preds_path} ({len(predictions_df)} rows)")

if __name__ == "__main__":
    export_full_dataset_performance()