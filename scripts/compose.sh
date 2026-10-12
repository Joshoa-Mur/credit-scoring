set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d --build --wait

echo "API грузит модель"
curl -sf --retry 30 --retry-all-errors --retry-delay 1 http://localhost:8000/ready
echo

echo "валидный запрос (ожидаем 200)"
curl -s -X POST http://localhost:8000/v1/predict \
  -H "Content-Type: application/json" -d @request.json
echo

echo "невалидный запрос (ожидаем 422)"
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://localhost:8000/v1/predict \
  -H "Content-Type: application/json" -d '{"age": 10}'

sleep 1  

echo "логи предсказаний в Postgres"
docker compose exec -T db psql -U postgres -d scoring -c \
  "SELECT request_id, status_code, score, latency_ms, created_at FROM predictions ORDER BY id DESC LIMIT 10;"