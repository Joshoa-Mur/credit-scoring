def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "model_version" in body
    assert body["model_path"].endswith("credit_model.joblib")
    assert body["log_level"]


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200


def test_bad_age_is_422(client, good_request):
    r = client.post("/v1/predict", json={**good_request, "age": 10})
    assert r.status_code == 422


def test_extra_field_is_422(client, good_request):
    r = client.post("/v1/predict", json={**good_request, "hacker_field": 1})
    assert r.status_code == 422


def test_missing_field_is_422(client, good_request):
    row = dict(good_request)
    del row["housing"]
    assert client.post("/v1/predict", json=row).status_code == 422


def test_empty_body_is_422(client):
    assert client.post("/v1/predict", json={}).status_code == 422