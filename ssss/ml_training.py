"""
MCX Silver Futures - ML Model Training Pipeline
===============================================
Trains classification models to predict profitable entry signals.

Models included:
  - Logistic Regression (baseline)
  - Random Forest (ensemble)
  - XGBoost (gradient boosting)
  - LightGBM (fast & efficient)

Evaluation metrics:
  - Precision (avoid false signals)
  - Recall (catch good opportunities)
  - ROC-AUC
  - F1-score
  - Confusion matrix
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, 
    roc_curve, precision_recall_curve, f1_score, accuracy_score
)
import logging
import warnings

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── CONFIG ──────────────────────────────────────────────────────────────────
ML_READY_CSV    = "mcx_silver_ml_ready.csv"
TEST_SIZE       = 0.2
RANDOM_STATE    = 42

# Features to exclude (non-predictive)
EXCLUDE_COLS = ['trade_date', 'symbol', 'expiry_date', 'close', 'high', 'low', 'open',
                'return_next_n_pct']  # target-correlated features


class SilverFuturesModel:
    """ML pipeline for silver futures trading signals."""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.scaler = StandardScaler()
        self.models = {}
        self.results = {}
    
    def load_data(self):
        """Load and prepare data."""
        log.info(f"Loading data from {self.csv_path}...")
        self.df = pd.read_csv(self.csv_path)
        
        # Handle missing values
        self.df = self.df.fillna(self.df.median(numeric_only=True))
        
        # Separate features and target
        X = self.df.drop(columns=EXCLUDE_COLS + ['target'], errors='ignore')
        y = self.df['target']
        
        log.info(f"Dataset shape: {X.shape}")
        log.info(f"Target distribution: {y.value_counts().to_dict()}")
        
        # Train-test split (temporal order for time series)
        split_idx = int(len(X) * (1 - TEST_SIZE))
        
        self.X_train = X.iloc[:split_idx]
        self.X_test = X.iloc[split_idx:]
        self.y_train = y.iloc[:split_idx]
        self.y_test = y.iloc[split_idx:]
        
        log.info(f"Train set: {self.X_train.shape[0]} | Test set: {self.X_test.shape[0]}")
        
        # Scale features
        self.X_train_scaled = self.scaler.fit_transform(self.X_train)
        self.X_test_scaled = self.scaler.transform(self.X_test)
        
        return self.X_train_scaled, self.X_test_scaled, self.y_train, self.y_test
    
    def train_logistic_regression(self):
        """Baseline model: Logistic Regression."""
        log.info("\n🔵 Training Logistic Regression...")
        
        model = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE, n_jobs=-1)
        model.fit(self.X_train_scaled, self.y_train)
        
        y_pred = model.predict(self.X_test_scaled)
        y_pred_proba = model.predict_proba(self.X_test_scaled)[:, 1]
        
        self.models['Logistic Regression'] = model
        self._evaluate_model('Logistic Regression', y_pred, y_pred_proba)
    
    def train_random_forest(self):
        """Ensemble model: Random Forest."""
        log.info("\n🟢 Training Random Forest...")
        
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            random_state=RANDOM_STATE,
            n_jobs=-1
        )
        model.fit(self.X_train, self.y_train)
        
        y_pred = model.predict(self.X_test)
        y_pred_proba = model.predict_proba(self.X_test)[:, 1]
        
        self.models['Random Forest'] = model
        self._evaluate_model('Random Forest', y_pred, y_pred_proba)
        
        # Feature importance
        self._plot_feature_importance(model, 'Random Forest')
    
    def train_xgboost(self):
        """Gradient boosting: XGBoost."""
        try:
            import xgboost as xgb
            log.info("\n🟡 Training XGBoost...")
            
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                eval_metric='logloss'
            )
            model.fit(self.X_train, self.y_train)
            
            y_pred = model.predict(self.X_test)
            y_pred_proba = model.predict_proba(self.X_test)[:, 1]
            
            self.models['XGBoost'] = model
            self._evaluate_model('XGBoost', y_pred, y_pred_proba)
            
            self._plot_feature_importance(model, 'XGBoost')
            
        except ImportError:
            log.warning("XGBoost not installed. Skipping...")
    
    def train_lightgbm(self):
        """Gradient boosting: LightGBM."""
        try:
            import lightgbm as lgb
            log.info("\n⚫ Training LightGBM...")
            
            model = lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                verbose=-1
            )
            model.fit(self.X_train, self.y_train)
            
            y_pred = model.predict(self.X_test)
            y_pred_proba = model.predict_proba(self.X_test)[:, 1]
            
            self.models['LightGBM'] = model
            self._evaluate_model('LightGBM', y_pred, y_pred_proba)
            
            self._plot_feature_importance(model, 'LightGBM')
            
        except ImportError:
            log.warning("LightGBM not installed. Skipping...")
    
    def _evaluate_model(self, model_name: str, y_pred, y_pred_proba):
        """Evaluate model performance."""
        
        accuracy = accuracy_score(self.y_test, y_pred)
        precision = (y_pred & self.y_test.values).sum() / y_pred.sum()
        recall = (y_pred & self.y_test.values).sum() / self.y_test.sum()
        f1 = f1_score(self.y_test, y_pred)
        auc = roc_auc_score(self.y_test, y_pred_proba)
        
        self.results[model_name] = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'auc': auc
        }
        
        log.info(f"\n  Accuracy:  {accuracy:.4f}")
        log.info(f"  Precision: {precision:.4f} (avoid false signals)")
        log.info(f"  Recall:    {recall:.4f} (catch opportunities)")
        log.info(f"  F1-Score:  {f1:.4f}")
        log.info(f"  ROC-AUC:   {auc:.4f}")
        
        # Confusion matrix
        cm = confusion_matrix(self.y_test, y_pred)
        log.info(f"\n  Confusion Matrix:")
        log.info(f"    TN={cm[0,0]}, FP={cm[0,1]}")
        log.info(f"    FN={cm[1,0]}, TP={cm[1,1]}")
    
    def _plot_feature_importance(self, model, model_name: str, top_n: int = 15):
        """Plot top N most important features."""
        try:
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                feature_names = self.X_train.columns
                
                indices = np.argsort(importances)[-top_n:]
                
                plt.figure(figsize=(10, 6))
                plt.title(f'{model_name} - Top {top_n} Features')
                plt.barh(range(len(indices)), importances[indices])
                plt.yticks(range(len(indices)), [feature_names[i] for i in indices])
                plt.xlabel('Importance')
                plt.tight_layout()
                plt.savefig(f'feature_importance_{model_name.lower().replace(" ", "_")}.png', dpi=100, bbox_inches='tight')
                plt.close()
                
                log.info(f"  📊 Feature importance plot saved")
        except:
            pass
    
    def plot_model_comparison(self):
        """Compare all trained models."""
        if not self.results:
            log.warning("No results to plot. Train models first.")
            return
        
        results_df = pd.DataFrame(self.results).T
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Model Performance Comparison', fontsize=16, fontweight='bold')
        
        metrics = ['accuracy', 'precision', 'recall', 'f1', 'auc']
        positions = [(0,0), (0,1), (1,0), (1,1)]
        
        for (i, j), metric in zip(positions[:len(metrics)-1], metrics[:4]):
            ax = axes[i, j]
            results_df[metric].plot(kind='barh', ax=ax, color='steelblue')
            ax.set_title(metric.upper())
            ax.set_xlim([0, 1])
            for idx, v in enumerate(results_df[metric]):
                ax.text(v + 0.02, idx, f'{v:.3f}', va='center', fontsize=9)
        
        # AUC plot
        ax = axes[1, 1]
        results_df['auc'].plot(kind='barh', ax=ax, color='coral')
        ax.set_title('ROC-AUC')
        ax.set_xlim([0, 1])
        for idx, v in enumerate(results_df['auc']):
            ax.text(v + 0.02, idx, f'{v:.3f}', va='center', fontsize=9)
        
        plt.tight_layout()
        plt.savefig('model_comparison.png', dpi=100, bbox_inches='tight')
        log.info("\n  📊 Model comparison plot saved as 'model_comparison.png'")
        plt.close()
    
    def save_best_model(self):
        """Save best performing model."""
        if not self.results:
            return
        
        best_model_name = max(self.results, key=lambda x: self.results[x]['f1'])
        best_model = self.models[best_model_name]
        
        import pickle
        with open(f'best_model_{best_model_name.lower().replace(" ", "_")}.pkl', 'wb') as f:
            pickle.dump(best_model, f)
        
        log.info(f"\n✅ Best model ({best_model_name}) saved")
        log.info(f"   F1-Score: {self.results[best_model_name]['f1']:.4f}")
    
    def run_full_pipeline(self):
        """Execute complete training pipeline."""
        log.info("="*70)
        log.info("🚀 MCX SILVER FUTURES - ML TRAINING PIPELINE")
        log.info("="*70)
        
        self.load_data()
        self.train_logistic_regression()
        self.train_random_forest()
        self.train_xgboost()
        self.train_lightgbm()
        
        log.info("\n" + "="*70)
        log.info("📊 MODEL PERFORMANCE SUMMARY")
        log.info("="*70)
        
        results_df = pd.DataFrame(self.results).T
        log.info("\n" + results_df.to_string())
        
        self.plot_model_comparison()
        self.save_best_model()
        
        log.info("\n✅ Training complete!")


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = SilverFuturesModel(ML_READY_CSV)
    pipeline.run_full_pipeline()
