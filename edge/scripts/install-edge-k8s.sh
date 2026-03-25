#!/usr/bin/env bash
# install-edge-k8s.sh — Install Collibra Edge onto Docker Desktop Kubernetes
#
# Deploys the Collibra Edge Helm chart using the site-specific installer
# bundle extracted at installer/ in the edge project root.
#
# Prerequisites:
#   - Docker Desktop with Kubernetes enabled
#     (Docker Desktop → Settings → Kubernetes → Enable Kubernetes → Apply)
#   - Internet access to edge-docker-delivery.repository.collibra.io (port 443)
#
# Usage:
#   bash scripts/install-edge-k8s.sh [--dry-run] [--uninstall]

set -euo pipefail

EDGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER_DIR="${EDGE_DIR}/installer"
NAMESPACE="collibra-edge"

# ── Colour helpers ────────────────────────────────────────────────────────────
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*"; }
red()   { printf '\033[0;31m%s\033[0m\n' "$*"; exit 1; }
step()  { blue ""; blue "▶ $*"; }

DRY_RUN=""
UNINSTALL=""
for arg in "$@"; do
  case "$arg" in
    --dry-run)   DRY_RUN=1 ;;
    --uninstall) UNINSTALL=1 ;;
  esac
done

# ── Uninstall path ────────────────────────────────────────────────────────────
if [ -n "$UNINSTALL" ]; then
  step "Uninstalling Collibra Edge from namespace ${NAMESPACE}"
  helm uninstall collibra-edge -n "${NAMESPACE}" 2>/dev/null || true
  kubectl delete namespace "${NAMESPACE}" 2>/dev/null || true
  green "Uninstalled."
  exit 0
fi

# ── 1. Check prerequisites ────────────────────────────────────────────────────
step "Checking prerequisites"

if ! command -v brew >/dev/null 2>&1; then
  red "Homebrew not found. Install from https://brew.sh first."
fi

for tool in helm kubectl jq yq; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "  installing $tool via brew..."
    brew install "$tool"
  fi
  green "  $tool $(${tool} version --client --short 2>/dev/null || ${tool} --version 2>/dev/null | head -1)"
done

# ── 2. Verify Kubernetes is reachable ────────────────────────────────────────
step "Verifying Kubernetes cluster"

if ! kubectl cluster-info >/dev/null 2>&1; then
  echo ""
  red "Kubernetes cluster not reachable.

Enable Docker Desktop Kubernetes:
  Docker Desktop → Settings → Kubernetes → ☑ Enable Kubernetes → Apply & Restart

Then re-run this script."
fi

CONTEXT=$(kubectl config current-context)
green "  cluster: ${CONTEXT}"
kubectl get nodes --no-headers | while read line; do green "  node: $line"; done

# ── 3. Verify installer bundle ────────────────────────────────────────────────
step "Verifying installer bundle"

for f in properties.yaml site-values.yaml registries.yaml collibra-edge-helm-chart/collibra-edge; do
  [ -e "${INSTALLER_DIR}/${f}" ] || red "Missing: installer/${f} — re-extract the TGZ"
done

SITE_ID=$(yq '.global.siteId'     "${INSTALLER_DIR}/site-values.yaml")
PLATFORM=$(yq '.global.platformId' "${INSTALLER_DIR}/site-values.yaml")
VERSION=$(yq '.global.installerVersion' "${INSTALLER_DIR}/site-values.yaml")

green "  site-id  : ${SITE_ID}"
green "  platform : ${PLATFORM}"
green "  version  : ${VERSION}"

# ── 4. Namespace ──────────────────────────────────────────────────────────────
step "Namespace: ${NAMESPACE}"

if kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
  green "  already exists"
else
  [ -n "$DRY_RUN" ] && echo "  [dry-run] kubectl create namespace ${NAMESPACE}" \
    || kubectl create namespace "${NAMESPACE}"
  green "  created"
fi

# ── 5. Image pull secret (Collibra private registry) ─────────────────────────
step "Image pull secret (edge-repositories)"

REG_URI=$(yq '.configs[0].uri'      "${INSTALLER_DIR}/registries.yaml")
REG_USER=$(yq '.configs[0].username' "${INSTALLER_DIR}/registries.yaml")
REG_PASS=$(yq '.configs[0].password' "${INSTALLER_DIR}/registries.yaml")

if kubectl get secret edge-repositories -n "${NAMESPACE}" >/dev/null 2>&1; then
  green "  secret already exists"
else
  if [ -n "$DRY_RUN" ]; then
    echo "  [dry-run] kubectl create secret docker-registry edge-repositories ..."
  else
    kubectl create secret docker-registry edge-repositories \
      --namespace "${NAMESPACE}" \
      --docker-server="https://${REG_URI}" \
      --docker-username="${REG_USER}" \
      --docker-password="${REG_PASS}"
  fi
  green "  created"
fi

# ── 6. Edge secret (site credentials) ────────────────────────────────────────
step "Edge secret"

EDGE_SECRET_FILE="${INSTALLER_DIR}/resources/manifests/edge-secret.yaml"
if [ -f "${EDGE_SECRET_FILE}" ]; then
  if kubectl get secret edge-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
    green "  edge-secret already exists"
  else
    [ -n "$DRY_RUN" ] \
      && echo "  [dry-run] kubectl apply -f edge-secret.yaml" \
      || kubectl apply -f "${EDGE_SECRET_FILE}" -n "${NAMESPACE}"
    green "  applied"
  fi
else
  echo "  edge-secret.yaml not found — skipping (will be created by Helm)"
fi

# ── 7. Repo-creds secret (ArgoCD / edge-cd volume mount) ─────────────────────
step "Repo-creds secret (collibra-edge-repo-creds)"

REPO_CREDS_FILE="${INSTALLER_DIR}/resources/manifests/sc-collibra-edge-repo-creds.yaml"
if [ -f "${REPO_CREDS_FILE}" ]; then
  if kubectl get secret collibra-edge-repo-creds -n "${NAMESPACE}" >/dev/null 2>&1; then
    green "  collibra-edge-repo-creds already exists"
  else
    [ -n "$DRY_RUN" ] \
      && echo "  [dry-run] kubectl apply -f sc-collibra-edge-repo-creds.yaml" \
      || kubectl apply -f "${REPO_CREDS_FILE}" -n "${NAMESPACE}"
    green "  applied"
  fi
else
  echo "  sc-collibra-edge-repo-creds.yaml not found — skipping"
fi

# ── 9. Helm install ───────────────────────────────────────────────────────────
step "Helm install: collibra-edge (version ${VERSION})"

HELM_CHART="${INSTALLER_DIR}/collibra-edge-helm-chart/collibra-edge"
SITE_VALUES="${INSTALLER_DIR}/site-values.yaml"

if helm status collibra-edge -n "${NAMESPACE}" >/dev/null 2>&1; then
  echo "  already installed — running helm upgrade"
  CMD="helm upgrade collibra-edge ${HELM_CHART} \
    --namespace ${NAMESPACE} \
    --values ${SITE_VALUES} \
    --timeout 10m \
    --wait"
else
  CMD="helm install collibra-edge ${HELM_CHART} \
    --namespace ${NAMESPACE} \
    --values ${SITE_VALUES} \
    --timeout 10m \
    --wait"
fi

if [ -n "$DRY_RUN" ]; then
  echo "  [dry-run] ${CMD}"
  echo "  [dry-run] helm install --dry-run output:"
  helm install collibra-edge "${HELM_CHART}" \
    --namespace "${NAMESPACE}" \
    --values "${SITE_VALUES}" \
    --dry-run 2>&1 | head -40
else
  eval "$CMD"
  green "  Helm install complete"
fi

# ── 10. Status ────────────────────────────────────────────────────────────────
step "Edge pods"
kubectl get pods -n "${NAMESPACE}" 2>/dev/null || true

echo ""
green "Installation complete."
echo ""
echo "  Monitor pods:   kubectl get pods -n ${NAMESPACE} -w"
echo "  Edge logs:      kubectl logs -n ${NAMESPACE} -l app=edge-proxy -f"
echo "  Check DGC:      curl -sk https://localhost/api/edge/v1/status | python3 -m json.tool"
echo ""
echo "  Once pods are Running, check lutino.collibra.com → Settings → Edge → Sites"
echo "  Site ${SITE_ID} should show status: Installed"
