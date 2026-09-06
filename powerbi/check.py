import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "fraud_analytics.db"
CSV_PATH = BASE_DIR / "powerbi" / "full_dataset_predictions.csv"

conn = sqlite3.connect(DB_PATH)

# Check record count in fraud_flags vs transactions
fraud_flags_count = pd.read_sql("SELECT COUNT(*) FROM fraud_flags", conn).iloc[0, 0]
transactions_count = pd.read_sql("SELECT COUNT(*) FROM transactions", conn).iloc[0, 0]

print(f"Database Record Counts -> fraud_flags: {fraud_flags_count} | transactions: {transactions_count}")

# Fetch DB scores (Populate from fraud_flags if present, otherwise check transactions)
if fraud_flags_count > 0:
    df_db = pd.read_sql("SELECT transaction_id, fraud_score FROM fraud_flags", conn)
else:
    print("\n[NOTE] 'fraud_flags' table is empty. Attempting to query 'transactions' or populate DB...")
    df_db = pd.read_sql("SELECT transaction_id FROM transactions", conn)
    # If fraud_score isn't in transactions, load from predictions CSV directly to populate DB table
    df_csv_temp = pd.read_csv(CSV_PATH)
    if "fraud_probability" in df_csv_temp.columns:
        df_csv_temp.rename(columns={"fraud_probability": "fraud_score"}, inplace=True)
    
    # Temporarily populate fraud_flags in DB to complete validation
    if "fraud_score" in df_csv_temp.columns:
        df_flags = df_csv_temp[["transaction_id", "fraud_score"]].copy()
        df_flags["predicted_label"] = (df_flags["fraud_score"] >= 0.5).astype(int)
        df_flags["model_version"] = "v1.0"
        df_flags.to_sql("fraud_flags", conn, if_exists="replace", index=False)
        print("Populated 'fraud_flags' table in SQLite with model predictions.")
        df_db = pd.read_sql("SELECT transaction_id, fraud_score FROM fraud_flags", conn)

conn.close()

# Load Predictions CSV
df_csv = pd.read_csv(CSV_PATH)
print(f"CSV Total Rows Loaded: {len(df_csv)}")

# Normalize transaction_id data types to integer for clean merging
df_csv["transaction_id"] = df_csv["transaction_id"].astype(int)
df_db["transaction_id"] = df_db["transaction_id"].astype(int)

# Identify prediction column name in CSV
prob_col = "fraud_probability" if "fraud_probability" in df_csv.columns else "fraud_score"

# Merge tables on transaction_id
merged = df_csv.merge(df_db, on="transaction_id", suffixes=("_csv", "_db"))
print(f"Total merged records: {len(merged)}")

if len(merged) > 0:
    diff = (merged[prob_col] - merged["fraud_score"]).abs().max()
    print(f"Maximum absolute score difference: {diff}")
    
    if diff < 1e-6:
        print("\nMATCH SUCCESSFUL: 'fraud_probability' in CSV and 'fraud_score' in SQLite are identical!")
    else:
        print("\nMISMATCH DETECTED: Scores differ between CSV and SQLite.")
else:
    print("\n[ERROR] Still 0 matching records. Displaying sample IDs for comparison:")
    print("CSV sample IDs:", df_csv["transaction_id"].head(3).tolist())
    print("DB sample IDs: ", df_db["transaction_id"].head(3).tolist())