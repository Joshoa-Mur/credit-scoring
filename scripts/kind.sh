
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER=credit
IMAGE=credit-scoring:1.0

if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER"
fi
kubectl config use-context "kind-$CLUSTER"

docker build -t "$IMAGE" .
kind load docker-image "$IMAGE" --name "$CLUSTER"

kubectl apply -f k8s/
kubectl rollout status deployment/scoring-service --timeout=180s
kubectl get pods -l app=credit-scoring

kubectl port-forward svc/scoring-service 8080:80 >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT

echo "/ready через port-forward"
curl -sf --retry 30 --retry-all-errors --retry-delay 1 http://localhost:8080/ready
echo

echo "ответ модели через port-forward"
curl -s -X POST http://localhost:8080/v1/predict \
  -H "Content-Type: application/json" -d @request.json
echo