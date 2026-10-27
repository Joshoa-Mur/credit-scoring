import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import catboost
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import sklearn
from catboost import CatBoostClassifier
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    PrecisionRecallDisplay,
    average_precision_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline

DATA_PATH = Path(os.getenv("DATA_PATH", "data/credit_g.csv"))
MODEL_NAME = os.getenv("MODEL_NAME", "credit-scoring")
EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "credit-scoring")
ITERATIONS = int(os.getenv("ITERATIONS", "500"))  # гиперпараметр, которым играем в гейте
MIN_GAIN = float(os.getenv("GATE_MIN_GAIN", "0.005"))
GATE_METRIC = "pr_auc"
SEED = 42

TARGET = "class"
COST_FN, COST_FP = 5, 1  # FN: пропустили "bad", FP: отказали "good"


def load_and_validate(path: Path) -> tuple[pd.DataFrame, pd.Series, list[str], list[str]]:
    df = pd.read_csv(path)
    if TARGET not in df.columns:
        raise ValueError(f"в данных нет таргета {TARGET!r}")
    if len(df) < 500:
        raise ValueError(f"слишком мало строк: {len(df)}")
    if not set(df[TARGET].unique()) <= {"good", "bad"}:
        raise ValueError(f"неожиданные значения таргета: {df[TARGET].unique()[:5]}")

    y = (df[TARGET] == "bad").astype(int)
    x = df.drop(columns=[TARGET])
    cat = [c for c in x.columns if not pd.api.types.is_numeric_dtype(x[c])]
    num = [c for c in x.columns if pd.api.types.is_numeric_dtype(x[c])]
    x[cat] = x[cat].astype(str)
    x[num] = x[num].astype(float)
    return x[cat + num], y, cat, num


def build_pipeline(cat: list[str], num: list[str]) -> Pipeline:
    prep = ColumnTransformer(
        [
            ("cat", SimpleImputer(strategy="constant", fill_value="missing"), cat),
            ("num", SimpleImputer(strategy="median"), num),
        ],
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")
    model = CatBoostClassifier(
        iterations=ITERATIONS,
        learning_rate=0.05,
        depth=4,
        cat_features=cat,
        random_seed=SEED,
        verbose=0,
        allow_writing_files=False,
        thread_count=1,
    )
    return Pipeline([("prep", prep), ("model", model)])


def cost(y_true: np.ndarray, proba: np.ndarray, thr: float) -> int:
    pred = (proba >= thr).astype(int)
    fn = int(((pred == 0) & (y_true == 1)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    return COST_FN * fn + COST_FP * fp


def pick_threshold(x: pd.DataFrame, y: pd.Series, cat: list[str], num: list[str]) -> float:
    """Порог по OOF-предсказаниям: минимум стоимости ошибок, как в ноутбуке."""
    # cross_val_predict не подходит: sklearn.clone ломает CatBoost с cat_features
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof = np.zeros(len(x))
    for tr, va in cv.split(x, y):
        fold = build_pipeline(cat, num).fit(x.iloc[tr], y.iloc[tr])
        oof[va] = fold.predict_proba(x.iloc[va])[:, 1]
    grid = np.round(np.arange(0.05, 0.96, 0.01), 2)
    return float(grid[int(np.argmin([cost(y.values, oof, t) for t in grid]))])


def plots(y_test: pd.Series, proba: np.ndarray, threshold: float):
    """Свой артефакт: PR-кривая и матрица ошибок при выбранном пороге."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    PrecisionRecallDisplay.from_predictions(y_test, proba, ax=ax1, name="CatBoost")
    ax1.set_title("PR-кривая (класс bad)")
    ConfusionMatrixDisplay.from_predictions(
        y_test, (proba >= threshold).astype(int), display_labels=["good", "bad"], ax=ax2,
        colorbar=False,
    )
    ax2.set_title(f"Матрица ошибок, порог {threshold}")
    fig.tight_layout()
    return fig


def champion_metric(client: MlflowClient) -> tuple[str | None, float | None]:
    try:
        mv = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        return None, None
    return mv.version, client.get_run(mv.run_id).data.metrics.get(GATE_METRIC)


def main() -> dict:
    data_md5 = hashlib.md5(DATA_PATH.read_bytes()).hexdigest()  # совпадает с md5 в .dvc
    x, y, cat, num = load_and_validate(DATA_PATH)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=SEED
    )

    threshold = pick_threshold(x_train, y_train, cat, num)
    pipeline = build_pipeline(cat, num).fit(x_train, y_train)
    proba = pipeline.predict_proba(x_test)[:, 1]
    metrics = {
        "pr_auc": float(average_precision_score(y_test, proba)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "test_cost": cost(y_test.values, proba, threshold),
        "threshold": threshold,
    }

    metadata = {
        "features": cat + num,  # порядок колонок для DataFrame в сервисе
        "cat_features": cat,
        "num_features": num,
        "threshold": threshold,  # default = proba_bad >= threshold
        "target": "bad (1) vs good (0)",
        "data_md5": data_md5,
        "data_rows": len(x),
        "n_train": len(x_train),
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "libs": {"scikit-learn": sklearn.__version__, "catboost": catboost.__version__},
    }

    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()
    with mlflow.start_run() as run:
        mlflow.log_params({
            "model": "CatBoostClassifier", "iterations": ITERATIONS, "learning_rate": 0.05,
            "depth": 4, "seed": SEED, "data": str(DATA_PATH), "data_md5": data_md5,
            "data_rows": len(x), "gate_metric": GATE_METRIC, "gate_min_gain": MIN_GAIN,
        })
        mlflow.log_metrics(metrics)
        mlflow.log_dict(metadata, "metadata.json")
        fig = plots(y_test, proba, threshold)
        mlflow.log_figure(fig, "pr_curve_confusion.png")
        plt.close(fig)
        # CatBoost внутри Pipeline skops сериализовать не умеет, поэтому cloudpickle
        info = mlflow.sklearn.log_model(
            pipeline, name="model", registered_model_name=MODEL_NAME,
            serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
            input_example=x_test.head(2),
        )
        version = info.registered_model_version

    old_version, old_metric = champion_metric(client)
    promoted = old_metric is None or metrics[GATE_METRIC] > old_metric + MIN_GAIN
    client.set_registered_model_alias(MODEL_NAME, "challenger", version)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, "champion", version)

    result = {
        "run_id": run.info.run_id, "version": version, "iterations": ITERATIONS,
        "data_md5": data_md5, GATE_METRIC: round(metrics[GATE_METRIC], 4),
        "champion_before": old_version,
        "champion_metric_before": None if old_metric is None else round(old_metric, 4),
        "min_gain": MIN_GAIN, "promoted": promoted,
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
