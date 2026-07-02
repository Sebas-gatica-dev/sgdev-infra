#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/terraform"

action="${1:-plan}"
shift || true

case "$action" in
  init)
    terraform init "$@"
    ;;
  fmt)
    terraform fmt -recursive "$@"
    ;;
  validate)
    terraform init -backend=false
    terraform validate "$@"
    ;;
  plan)
    terraform init
    terraform plan "$@"
    ;;
  apply)
    terraform init
    terraform apply "$@"
    ;;
  destroy)
    terraform init
    terraform destroy "$@"
    ;;
  *)
    cat <<'USAGE'
Usage: ./scripts/terraform.sh <init|fmt|validate|plan|apply|destroy> [terraform args]

Examples:
  ./scripts/terraform.sh plan -var-file=terraform.tfvars
  ./scripts/terraform.sh apply -var-file=terraform.tfvars
USAGE
    exit 1
    ;;
esac
