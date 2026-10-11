import pytest
from fastapi.testclient import TestClient

from credit_scoring.service.app import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def good_request():
    return {
        "checking_status": "<0",
        "duration": 24,
        "credit_history": "existing paid",
        "purpose": "radio/tv",
        "credit_amount": 3000,
        "savings_status": "<100",
        "employment": "1<=X<4",
        "installment_commitment": 3,
        "personal_status": "male single",
        "other_parties": "none",
        "residence_since": 2,
        "property_magnitude": "car",
        "age": 35,
        "other_payment_plans": "none",
        "housing": "own",
        "existing_credits": 1,
        "job": "skilled",
        "num_dependents": 1,
        "own_telephone": "none",
        "foreign_worker": "yes",
    }        
    