"""Chronological performance-classification pipeline requiring independent observed labels.

No labels are inferred from GTFS, boarding totals, frequency or clustering. Imported
labels need a documented observation source; accepting a file does not certify its source.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

LABEL_FIELDS = ['bus_route', 'payment_date', 'performance_label', 'label_basis', 'source_reference']
NUMERIC = ['lag_14d', 'lag_21d', 'lag_28d', 'day_of_week', 'month']


def validate_labels(labels):
    if not set(LABEL_FIELDS) <= set(labels):
        raise ValueError('Label file requires: '+', '.join(LABEL_FIELDS))
    labels = labels[LABEL_FIELDS].copy()
    labels.payment_date = pd.to_datetime(labels.payment_date, errors='coerce')
    if labels.isna().any().any() or not labels.payment_date.eq(labels.payment_date.dt.normalize()).all():
        raise ValueError('Labels require complete normalized route/date records')
    if labels.duplicated(['bus_route', 'payment_date']).any():
        raise ValueError('Duplicate route/date labels')
    if not labels.performance_label.isin(['balanced', 'overcrowded']).all():
        raise ValueError('Unknown performance class')
    if not labels.label_basis.eq('independent_observed_load_assessment').all():
        raise ValueError('Labels must come from an independent observed-load assessment')
    if labels.source_reference.astype(str).str.strip().eq('').any():
        raise ValueError('Every label needs its observation source reference')
    return labels


def train_classifier(features, labels):
    labels = validate_labels(labels)
    if features.duplicated(['bus_route', 'payment_date']).any():
        raise ValueError('Feature keys must be unique')
    fields = ['bus_route', 'payment_date', *NUMERIC]
    available = features[fields].copy()
    available.payment_date = pd.to_datetime(available.payment_date)
    joined = labels.merge(available, on=['bus_route', 'payment_date'], how='left', indicator=True, validate='one_to_one')
    if joined['_merge'].ne('both').any():
        raise ValueError('Some observed labels have no exact route/date feature match')
    if joined[NUMERIC[:3]].notna().sum(axis=1).lt(2).any():
        raise ValueError('At least two released historical lags are required for every labeled target')
    dates = sorted(joined.payment_date.unique())
    if len(dates) < 50:
        raise ValueError('At least 50 distinct observed dates are required for chronological assessment')
    split = pd.Timestamp(dates[int(len(dates)*.8)])
    train = joined.loc[joined.payment_date.lt(split)].copy()
    test = joined.loc[joined.payment_date.ge(split)].copy()
    if train.performance_label.value_counts().reindex(['balanced', 'overcrowded'], fill_value=0).min() < 10:
        raise ValueError('Training requires at least ten independent labels from each class')
    transformer = ColumnTransformer([
        ('numeric', SimpleImputer(strategy='median', add_indicator=True), NUMERIC),
        ('route', OneHotEncoder(handle_unknown='ignore', sparse_output=False), ['bus_route'])])
    model = Pipeline([('features', transformer), ('classifier', RandomForestClassifier(
        n_estimators=200, min_samples_leaf=5, class_weight='balanced', random_state=42, n_jobs=1))])
    columns = ['bus_route', *NUMERIC]
    model.fit(train[columns], train.performance_label)
    predicted = model.predict(test[columns])
    baseline = DummyClassifier(strategy='most_frequent').fit(train[columns], train.performance_label)
    baseline_prediction = baseline.predict(test[columns])
    report = {'task': 'independent observed route/date performance labels',
              'status': 'retrospective_experiment; source and publication timing require independent verification',
              'training_end': str(train.payment_date.max().date()), 'test_start': str(split.date()),
              'test_end': str(test.payment_date.max().date()), 'train_rows': len(train), 'test_rows': len(test),
              'train_dates': int(train.payment_date.nunique()), 'test_dates': int(test.payment_date.nunique()),
              'features': columns, 'target_derived_features_used': False,
              'balanced_accuracy': balanced_accuracy_score(test.performance_label, predicted),
              'baseline_balanced_accuracy': balanced_accuracy_score(test.performance_label, baseline_prediction),
              'classification_report': classification_report(test.performance_label, predicted, zero_division=0, output_dict=True),
              'confusion_matrix': confusion_matrix(test.performance_label, predicted, labels=['balanced','overcrowded']).tolist(),
              'class_order': ['balanced', 'overcrowded'], 'operationally_accepted': False}
    outputs = test[['bus_route', 'payment_date', 'performance_label', 'source_reference']].copy()
    outputs['prediction'] = predicted
    outputs['baseline_prediction'] = baseline_prediction
    return model, report, outputs
