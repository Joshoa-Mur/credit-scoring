import logging

import psycopg
from psycopg.types.json import Jsonb

from credit_scoring.config import settings

log = logging.getLogger(__name__)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS predictions (
    id            BIGSERIAL PRIMARY KEY,
    request_id    UUID NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version TEXT NOT NULL,
    features      JSONB NOT NULL,
    score         DOUBLE PRECISION NOT NULL,
    latency_ms    DOUBLE PRECISION NOT NULL
)
"""

INSERT = """
INSERT INTO predictions (request_id, model_version, features, score, latency_ms)
VALUES (%s, %s, %s, %s, %s)
"""


def init() -> None:
    if not settings.database_url:
        log.warning("DATABASE_URL is not set: prediction logging is disabled")
        return
    try:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute(CREATE_TABLE)
    except Exception:
        log.exception("Could not initialize the predictions table")


def save_prediction(request_id, payload, score, model_version, latency_ms) -> None:
    if not settings.database_url:
        return
    try:
        with psycopg.connect(settings.database_url) as conn:
            conn.execute(INSERT, (request_id, model_version, Jsonb(payload), score, latency_ms))
    except Exception:
        log.exception("Could not save prediction %s", request_id)