"""
Enrich the Kaggle credit-card-fraud dataset with synthetic business context
(customers, merchants, channel, geography) while preserving the REAL
transaction amounts, timestamps (offset), and fraud labels.

Why: the raw Kaggle set is PCA-anonymized with no PII at all, so it can't
demonstrate a masking/access-control story on its own. This keeps the real
V1-V28 features + Class label (genuine fraud signal) and layers realistic
business + customer data on top, mapped consistently (same customer_hash
reused across that customer's transactions).
"""
import hashlib
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

random.seed(42)
np.random.seed(42)
fake = Faker()
Faker.seed(42)

RAW_PATH = "data/raw/creditcard.csv"
OUT_DIR = "data/processed"
N_CUSTOMERS = 4000
N_MERCHANTS = 60

MERCHANT_CATEGORIES = [
    "Grocery", "Electronics", "Travel", "Restaurants", "Online Retail",
    "Fuel", "Utilities", "Entertainment", "Healthcare", "Apparel",
]
COUNTRIES = ["US", "GB", "DE", "FR", "IN", "CA", "AU", "SG", "NG", "BR"]
HOME_COUNTRY_WEIGHTS = [0.45, 0.12, 0.08, 0.07, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02]


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def build_customers(n):
    rows = []
    for i in range(n):
        natural_key = f"CUST-{i:06d}"
        card_num = fake.credit_card_number(card_type="visa")
        home_country = random.choices(COUNTRIES, weights=HOME_COUNTRY_WEIGHTS)[0]
        rows.append({
            "customer_id": i + 1,
            "customer_hash": sha256(natural_key),
            "full_name": fake.name(),
            "email": fake.email(),
            "card_number_masked": card_num[:4] + "-XXXX-XXXX-" + card_num[-4:],
            "card_number_hash": sha256(card_num),
            "billing_address": fake.address().replace("\n", ", "),
            "account_open_date": fake.date_between(start_date="-6y", end_date="-30d"),
            "home_country": home_country,
            "risk_tier": random.choices(["low", "medium", "high"], weights=[0.8, 0.15, 0.05])[0],
        })
    return pd.DataFrame(rows)


def build_merchants(n):
    rows = []
    for i in range(n):
        rows.append({
            "merchant_id": i + 1,
            "merchant_name": fake.company(),
            "category": random.choice(MERCHANT_CATEGORIES),
            "country": random.choices(COUNTRIES, weights=HOME_COUNTRY_WEIGHTS)[0],
        })
    return pd.DataFrame(rows)


def main():
    print("Loading raw Kaggle data...")
    raw = pd.read_csv(RAW_PATH)
    raw["transaction_id"] = raw.index + 1

    print(f"Generating {N_CUSTOMERS} synthetic customers and {N_MERCHANTS} merchants...")
    customers = build_customers(N_CUSTOMERS)
    merchants = build_merchants(N_MERCHANTS)

    # Assign transactions to customers with a skewed distribution (some
    # customers transact far more than others, like real life), and to
    # merchants uniformly-ish.
    cust_weights = np.random.exponential(scale=1.0, size=N_CUSTOMERS)
    cust_weights = cust_weights / cust_weights.sum()
    assigned_customers = np.random.choice(
        customers["customer_id"].values, size=len(raw), p=cust_weights
    )
    assigned_merchants = np.random.choice(merchants["merchant_id"].values, size=len(raw))
    channels = np.random.choice(
        ["online", "in_store", "atm"], size=len(raw), p=[0.55, 0.4, 0.05]
    )

    base_time = datetime(2026, 1, 1)
    raw["transaction_ts"] = raw["Time"].apply(lambda s: base_time + timedelta(seconds=float(s)))
    raw["customer_id"] = assigned_customers
    raw["merchant_id"] = assigned_merchants
    raw["channel"] = channels

    cust_home = customers.set_index("customer_id")["home_country"]
    merch_country = merchants.set_index("merchant_id")["country"]
    raw["home_country"] = raw["customer_id"].map(cust_home)
    raw["merchant_country"] = raw["merchant_id"].map(merch_country)

    # Fraudulent transactions are more likely to be foreign / online —
    # realistic pattern, and gives the model (and dashboard) a genuine
    # geography-based signal to surface.
    is_fraud = raw["Class"] == 1
    flip_foreign = np.random.rand(len(raw)) < np.where(is_fraud, 0.55, 0.06)
    raw.loc[flip_foreign, "device_country"] = raw.loc[flip_foreign].apply(
        lambda r: random.choice([c for c in COUNTRIES if c != r["home_country"]]), axis=1
    )
    raw["device_country"] = raw["device_country"].fillna(raw["home_country"])

    customers = customers.merge(
        raw.loc[raw["customer_id"].isin(customers["customer_id"]), ["customer_id"]]
        .drop_duplicates(), on="customer_id", how="left"
    )
    cust_hash_map = customers.set_index("customer_id")["customer_hash"]
    raw["customer_hash"] = raw["customer_id"].map(cust_hash_map)

    # ---- transactions table ----
    transactions = raw[[
        "transaction_id", "customer_hash", "merchant_id", "Amount",
        "transaction_ts", "channel", "device_country", "home_country",
    ]].rename(columns={"Amount": "amount"})
    transactions["currency"] = "USD"

    # ---- engineered features table ----
    raw_sorted = raw.sort_values(["customer_id", "transaction_ts"])
    raw_sorted["prev_ts"] = raw_sorted.groupby("customer_id")["transaction_ts"].shift(1)
    raw_sorted["gap_seconds"] = (raw_sorted["transaction_ts"] - raw_sorted["prev_ts"]).dt.total_seconds()

    amt_mean, amt_std = raw["Amount"].mean(), raw["Amount"].std()
    features = pd.DataFrame({
        "transaction_id": raw["transaction_id"],
        "amount_zscore": (raw["Amount"] - amt_mean) / amt_std,
        "is_foreign_txn": (raw["device_country"] != raw["home_country"]).astype(int),
        "hour_of_day": raw["transaction_ts"].dt.hour,
    })
    features = features.merge(
        raw_sorted[["transaction_id", "gap_seconds"]], on="transaction_id", how="left"
    )
    features["txns_last_1h"] = (features["gap_seconds"] < 3600).astype(int).fillna(0)
    features = features.drop(columns=["gap_seconds"])

    # ---- ground-truth fraud labels (kept separate, mirrors fraud_flags table
    #      shape but this is the LABEL, not a model prediction) ----
    labels = raw[["transaction_id", "Class"]].rename(columns={"Class": "actual_label"})

    # ---- raw model features (V1-V28) kept as its own file, referenced by
    #      transaction_id, so the "business" schema stays clean of the
    #      anonymized PCA columns ----
    model_features = raw[["transaction_id"] + [f"V{i}" for i in range(1, 29)] + ["amount", "Class"] if False else
                          ["transaction_id"] + [f"V{i}" for i in range(1, 29)]]
    model_features["amount"] = raw["Amount"]
    model_features["class"] = raw["Class"]

    print("Writing outputs...")
    customers.to_csv(f"{OUT_DIR}/customers.csv", index=False)
    merchants.to_csv(f"{OUT_DIR}/merchants.csv", index=False)
    transactions.to_csv(f"{OUT_DIR}/transactions.csv", index=False)
    features.to_csv(f"{OUT_DIR}/transaction_features.csv", index=False)
    labels.to_csv(f"{OUT_DIR}/labels.csv", index=False)
    model_features.to_csv(f"{OUT_DIR}/model_features.csv", index=False)

    print("Done.")
    print(f"customers: {customers.shape}, merchants: {merchants.shape}")
    print(f"transactions: {transactions.shape}, features: {features.shape}")
    print(f"fraud rate: {labels['actual_label'].mean():.4%}")


if __name__ == "__main__":
    main()
