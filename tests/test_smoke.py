# детерминизм
def test_batch_and_single_agree(client , good_request):
    s1 = client.post("/v1/predict", json=good_request).json()['score']
    s2 = client.post("/v1/predict", json=good_request).json()['score']
    assert s1 == s2

def test_predict_smoke(client, good_request):
    r = client.post("/v1/predict", json=good_request)
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["score"] <= 1.0
    assert isinstance(body["default"], bool)
    assert body["latency_ms"] >= 0
    assert body["model_version"]


def test_predict_handles_missing_total_charges(client, good_request):
    r = client.post("/v1/predict", json={**good_request, "savings_status": None})
    assert r.status_code == 200


