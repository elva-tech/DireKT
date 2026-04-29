#!/usr/bin/env python3
"""
Retrain model with current environment versions for compatibility.
"""

import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import sys

print("Loading training data...")
data = pd.read_csv('mcx_silver_ml_ready.csv')

# Select only numeric feature columns (exclude date/symbol columns and target)
exclude_cols = ['trade_date', 'symbol', 'expiry_date', 'close', 'high', 'low', 'open', 'target', 'return_next_n_pct']
feature_cols = [col for col in data.columns if col not in exclude_cols]

print(f"Using {len(feature_cols)} features: {feature_cols[:10]}...")

# Remove rows with NaN values
data_clean = data[feature_cols + ['target']].dropna()

X = data_clean[feature_cols].values.astype(float)
y = data_clean['target'].values

print(f"Training Random Forest with {X.shape[0]} samples and {X.shape[1]} features...")
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=15,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1,
    verbose=0
)

try:
    model.fit(X, y)
    print("✅ Model training complete")
except Exception as e:
    print(f"❌ Training failed: {e}")
    sys.exit(1)

# Save the model
try:
    with open('best_model_random_forest.pkl', 'wb') as f:
        pickle.dump(model, f)
    print(f"✅ Model saved successfully")
    print(f"   Classes: {list(model.classes_)}")
    print(f"   Features: {model.n_features_in_}")
    print(f"   File: best_model_random_forest.pkl")
except Exception as e:
    print(f"❌ Save failed: {e}")
    sys.exit(1)

print("\n✅ Model retrained and ready!")
