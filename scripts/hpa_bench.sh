#!/usr/bin/env bash
# П. 6 ДЗ 3: три прогона locust через Ingress + журнал HPA и kubectl top, потом ждём спада реплик.
# Всё пишется в hpa-bench/. Запуск из корня репо:  bash scripts/hpa_bench.sh
set -uo pipefail
OUT=hpa-bench; mkdir -p "$OUT"
HOST=http://scoring.localhost

# фоном: раз в 15 с состояние HPA и потребление подов, с отметкой времени
( while true; do
    echo "=== $(date +%T)"
    kubectl get hpa credit-scoring --no-headers
    kubectl top pods -l app=credit-scoring --no-headers 2>/dev/null
    sleep 15
  done ) > "$OUT/watch.log" 2>&1 &
WATCH=$!
trap 'kill $WATCH 2>/dev/null' EXIT

kubectl describe deploy/credit-scoring | grep -A3 -i "requests" > "$OUT/requests.txt"

for spec in "10 5 3m" "30 10 3m" "60 20 4m"; do
  set -- $spec
  echo "== $(date +%T) locust: $1 пользователей, $3" | tee -a "$OUT/runs.log"
  uv run locust -f locustfile.py --headless -u "$1" -r "$2" -t "$3" --host "$HOST" \
    --csv "$OUT/u$1" --only-summary >> "$OUT/runs.log" 2>&1
  echo "== $(date +%T) готово: $1" | tee -a "$OUT/runs.log"
  sleep 30   # пауза между прогонами
done

echo "== $(date +%T) нагрузка закончена, ждём спада реплик до 2 (до 8 минут)" | tee -a "$OUT/runs.log"
for i in $(seq 1 32); do
  r=$(kubectl get hpa credit-scoring -o jsonpath='{.status.currentReplicas}')
  [ "$r" = "2" ] && break
  sleep 15
done
echo "== $(date +%T) реплик: $(kubectl get hpa credit-scoring -o jsonpath='{.status.currentReplicas}')" | tee -a "$OUT/runs.log"

kubectl describe hpa credit-scoring > "$OUT/describe-hpa.txt"
echo "Готово, результаты в $OUT/"
