set -euo pipefail
CLUSTER=${CLUSTER:-credit}
cd "$(dirname "$0")/.."

echo "== кластер $CLUSTER"
kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER" --config platform/kind-config.yaml
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo "== образ MLflow, если скачан заранее (docker pull), кладём прямо в узел"
# kind load docker-image падает на мультиплатформенных образах, если Docker Desktop хранит их в containerd
# ("content digest ... not found"), поэтому через архив одной платформы
ARCH=$(docker version --format '{{.Server.Arch}}')
TMP=$(mktemp -d)
for img in ghcr.io/mlflow/mlflow:v3.16.1; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    docker save --platform "linux/$ARCH" "$img" -o "$TMP/image.tar" \
      && kind load image-archive "$TMP/image.tar" --name "$CLUSTER" >/dev/null && echo "  $img"
  fi
done
rm -rf "$TMP"

echo "== MLflow"
kubectl apply -f platform/mlflow.yaml

echo "== Traefik и metrics-server"
helm repo add traefik https://traefik.github.io/charts >/dev/null 2>&1 || true
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install traefik traefik/traefik --version 41.6.0 \
  -n traefik --create-namespace -f platform/traefik-values.yaml --wait
helm upgrade --install metrics-server metrics-server/metrics-server --version 3.14.0 \
  -n kube-system -f platform/metrics-server-values.yaml --wait
kubectl apply -f platform/ingress.yaml

echo "== ждём MLflow"
kubectl -n mlops rollout status deploy/mlflow --timeout=10m

echo
echo "Готово:  http://mlflow.localhost"
kubectl get pods,ingress -A
