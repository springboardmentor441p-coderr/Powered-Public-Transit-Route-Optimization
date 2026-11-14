"""
Module 5: Model Selection & Training
Trains clustering (KMeans, DBSCAN) and classification (XGBoost, Random Forest) models.
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans, DBSCAN
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    silhouette_score, classification_report, confusion_matrix,
    accuracy_score, f1_score
)
import joblib
import os

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("⚠️  XGBoost not available, will use Random Forest only.")


def train_kmeans(X_scaled: np.ndarray, model_dir: str, output_dir: str,
                 k_range: range = range(2, 11)) -> tuple:
    """
    Train KMeans clustering with elbow method.
    """
    print("\n🔧 Training KMeans Clustering...")

    # Elbow method
    inertias = []
    silhouettes = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        sil = silhouette_score(X_scaled, labels)
        silhouettes.append(sil)
        print(f"   k={k}: Inertia={km.inertia_:.0f}, Silhouette={sil:.4f}")

    # Plot elbow curve
    plots_dir = os.path.join(output_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    ax1.plot(list(k_range), inertias, 'bo-', linewidth=2)
    ax1.set_xlabel('Number of Clusters (k)')
    ax1.set_ylabel('Inertia')
    ax1.set_title('Elbow Method', fontsize=14, fontweight='bold')

    ax2.plot(list(k_range), silhouettes, 'rs-', linewidth=2)
    ax2.set_xlabel('Number of Clusters (k)')
    ax2.set_ylabel('Silhouette Score')
    ax2.set_title('Silhouette Analysis', fontsize=14, fontweight='bold')

    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '11_kmeans_elbow_silhouette.png'), dpi=150)
    plt.close(fig)

    # Best k by silhouette
    best_k = list(k_range)[np.argmax(silhouettes)]
    print(f"\n   ✅ Best k = {best_k} (Silhouette = {max(silhouettes):.4f})")

    # Train final model
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10, max_iter=300)
    cluster_labels = kmeans.fit_predict(X_scaled)

    # Save model
    joblib.dump(kmeans, os.path.join(model_dir, 'kmeans_model.pkl'))
    print(f"   ✅ KMeans model saved (k={best_k})")

    return kmeans, cluster_labels, best_k


def train_dbscan(X_scaled: np.ndarray, model_dir: str, eps: float = 1.5,
                 min_samples: int = 3) -> tuple:
    """
    Train DBSCAN clustering.
    """
    print("\n🔧 Training DBSCAN Clustering...")

    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    db_labels = dbscan.fit_predict(X_scaled)

    n_clusters = len(set(db_labels)) - (1 if -1 in db_labels else 0)
    n_noise = list(db_labels).count(-1)

    print(f"   Clusters found: {n_clusters}")
    print(f"   Noise points: {n_noise}")

    if n_clusters > 1:
        mask = db_labels != -1
        sil = silhouette_score(X_scaled[mask], db_labels[mask])
        print(f"   Silhouette Score (excl. noise): {sil:.4f}")

    joblib.dump(dbscan, os.path.join(model_dir, 'dbscan_model.pkl'))
    print(f"   ✅ DBSCAN model saved")

    return dbscan, db_labels


def train_random_forest(X_train, X_test, y_train, y_test, le,
                        feature_names, model_dir, output_dir) -> RandomForestClassifier:
    """
    Train Random Forest classifier.
    """
    print("\n🔧 Training Random Forest Classifier...")

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    rf.fit(X_train, y_train)

    # Predictions
    y_pred = rf.predict(X_test)

    # Metrics
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='weighted')

    print(f"\n   Random Forest Results:")
    print(f"   Accuracy: {acc:.4f}")
    print(f"   F1-Score (weighted): {f1:.4f}")
    print(f"\n   Classification Report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    # Confusion Matrix
    plots_dir = os.path.join(output_dir, 'plots')
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=le.classes_, yticklabels=le.classes_, ax=ax)
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    ax.set_title('Random Forest - Confusion Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '12_rf_confusion_matrix.png'), dpi=150)
    plt.close(fig)

    # Feature Importance
    importances = pd.Series(rf.feature_importances_, index=feature_names).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    importances.plot(kind='barh', color='teal', ax=ax)
    ax.set_title('Random Forest - Feature Importance', fontsize=14, fontweight='bold')
    ax.set_xlabel('Importance')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '13_rf_feature_importance.png'), dpi=150)
    plt.close(fig)

    # Save model
    joblib.dump(rf, os.path.join(model_dir, 'random_forest_model.pkl'))
    print(f"   ✅ Random Forest model saved")

    return rf


def train_xgboost(X_train, X_test, y_train, y_test, le,
                  feature_names, model_dir, output_dir):
    """
    Train XGBoost classifier.
    """
    if not HAS_XGBOOST:
        print("   ⚠️ XGBoost not available, skipping.")
        return None

    print("\n🔧 Training XGBoost Classifier...")

    xgb = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        use_label_encoder=False,
        eval_metric='mlogloss'
    )
    xgb.fit(X_train, y_train)

    # Predictions
    y_pred = xgb.predict(X_test)

    # Metrics
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='weighted')

    print(f"\n   XGBoost Results:")
    print(f"   Accuracy: {acc:.4f}")
    print(f"   F1-Score (weighted): {f1:.4f}")
    print(f"\n   Classification Report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    # Confusion Matrix
    plots_dir = os.path.join(output_dir, 'plots')
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Greens',
                xticklabels=le.classes_, yticklabels=le.classes_, ax=ax)
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    ax.set_title('XGBoost - Confusion Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '14_xgb_confusion_matrix.png'), dpi=150)
    plt.close(fig)

    # Feature Importance
    importances = pd.Series(xgb.feature_importances_, index=feature_names).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    importances.plot(kind='barh', color='darkorange', ax=ax)
    ax.set_title('XGBoost - Feature Importance', fontsize=14, fontweight='bold')
    ax.set_xlabel('Importance')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, '15_xgb_feature_importance.png'), dpi=150)
    plt.close(fig)

    # Save model
    joblib.dump(xgb, os.path.join(model_dir, 'xgboost_model.pkl'))
    print(f"   ✅ XGBoost model saved")

    return xgb


def visualize_clusters(profiles: pd.DataFrame, cluster_labels: np.ndarray,
                       output_dir: str, method_name: str = 'KMeans'):
    """
    Visualize cluster assignments.
    """
    plots_dir = os.path.join(output_dir, 'plots')
    df = profiles.copy()
    df['cluster'] = cluster_labels

    # Cluster distribution
    fig, ax = plt.subplots(figsize=(8, 5))
    cluster_counts = df['cluster'].value_counts().sort_index()
    ax.bar(cluster_counts.index.astype(str), cluster_counts.values,
           color=plt.cm.Set2.colors[:len(cluster_counts)])
    ax.set_xlabel('Cluster')
    ax.set_ylabel('Number of Routes')
    ax.set_title(f'{method_name} - Cluster Distribution', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, f'16_{method_name.lower()}_cluster_distribution.png'), dpi=150)
    plt.close(fig)

    # Cluster profiles (mean of each feature per cluster)
    feature_cols = ['trip_count', 'unique_stops', 'route_length_km',
                    'peak_hour_trips', 'peak_ratio', 'stop_frequency']
    cluster_means = df.groupby('cluster')[feature_cols].mean()

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    for i, col in enumerate(feature_cols):
        ax = axes[i // 3, i % 3]
        cluster_means[col].plot(kind='bar', ax=ax, color=plt.cm.Set2.colors[:len(cluster_means)])
        ax.set_title(col, fontsize=11, fontweight='bold')
        ax.set_xlabel('Cluster')
        ax.tick_params(axis='x', rotation=0)
    plt.suptitle(f'{method_name} - Cluster Feature Profiles', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(os.path.join(plots_dir, f'17_{method_name.lower()}_cluster_profiles.png'), dpi=150)
    plt.close(fig)

    print(f"   ✅ {method_name} cluster visualizations saved")

    return df
