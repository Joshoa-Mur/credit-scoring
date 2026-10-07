import time
import uuid
from contextlib import asynccontextmanager

import joblib
import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from credit_scoring import db
from credit_scoring.config import settings


class Features(BaseModel):
    model_config = {"extra": "forbid"}

    checking_status: str
    duration: int = Field(ge=1, le=120)
    credit_history: str
    purpose: str
    credit_amount: float = Field(gt=0)
    savings_status: str | None = None
    employment: str
    installment_commitment: int = Field(ge=1, le=4)
    personal_status: str
    other_parties: str
    residence_since: int = Field(ge=1, le=4)
    property_magnitude: str
    age: int = Field(ge=18, le=100)
    other_payment_plans: str
    housing: str
    existing_credits: int = Field(ge=0, le=20)
    job: str
    num_dependents: int = Field(ge=0, le=20)
    own_telephone: str
    foreign_worker: str


class Prediction(BaseModel):
    score: float
    default: bool
    model_version: str
    request_id: str
    latency_ms: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = joblib.load(settings.model_path)
    app.state.pipeline = bundle["pipeline"]
    app.state.meta = bundle["metadata"]
    app.state.version = bundle["metadata"]["version"]
    db.init()

    yield

    app.state.pipeline = None


app = FastAPI(title="credit-scoring-service", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "model_version": getattr(app.state, "version", "unknown")}


@app.get("/ready")
def ready():
    if getattr(app.state, "pipeline", None) is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ready"}


@app.post("/v1/predict")
def predict(x: Features, bg: BackgroundTasks) -> Prediction:
    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())

    payload = x.model_dump()
    frame = (
        pd.DataFrame([payload])
        .reindex(columns=app.state.meta["features"])
        .replace({None: np.nan})
    )

    score = float(app.state.pipeline.predict_proba(frame)[0, 1])
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    bg.add_task(db.save_prediction, request_id, payload, score, app.state.version, latency_ms)

    default = score >= app.state.meta["threshold"]

    return Prediction(
        score=score,
        default=default,
        model_version=app.state.version,
        request_id=request_id,
        latency_ms=latency_ms,
    )