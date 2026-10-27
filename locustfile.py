"""Нагрузка на сервис через Ingress, для HPA (п. 6 ДЗ 3).

  uv run locust -f locustfile.py --headless -u 60 -r 20 -t 4m --host http://scoring.localhost
"""

import json
import random
from pathlib import Path

from locust import HttpUser, between, task

BASE = json.loads(Path(__file__).with_name("request.json").read_text())


class Client(HttpUser):
    wait_time = between(0.05, 0.2)

    @task
    def predict(self):
        # немного меняем числа, чтобы запросы не были одинаковыми
        body = dict(BASE, age=random.randint(20, 70), credit_amount=random.randint(500, 15000),
                    duration=random.randint(6, 60))
        self.client.post("/v1/predict", json=body, name="/v1/predict")
