"""Откуда сервис берёт модель.

Задан MODEL_NAME: из реестра MLflow по алиасу (models:/<имя>@<алиас>, по умолчанию champion).
Не задан: из файла MODEL_PATH, как раньше. Так тесты в CI идут без MLflow.
"""

import joblib

from credit_scoring.config import settings


def load_model() -> tuple[object, dict, str]:
    """Возвращает (pipeline, metadata, версия для /health и логов)."""
    if not settings.model_name:
        bundle = joblib.load(settings.model_path)
        return bundle["pipeline"], bundle["metadata"], bundle["metadata"]["version"]

    import mlflow  # только в режиме реестра: тестам с файлом mlflow не нужен
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    # алиас -> конкретный номер версии: его и покажем в /health
    mv = MlflowClient().get_model_version_by_alias(settings.model_name, settings.model_alias)
    pipeline = mlflow.sklearn.load_model(f"models:/{settings.model_name}/{mv.version}")
    meta = mlflow.artifacts.load_dict(f"runs:/{mv.run_id}/metadata.json")
    return pipeline, meta, f"{settings.model_name}-v{mv.version}"
